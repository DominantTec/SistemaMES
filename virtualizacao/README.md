# Virtualização — IHM + CLP digitais (antes do hardware físico)

> Parte da **Fase 1** do [`../ROADMAP.md`](../ROADMAP.md), pela ótica "digital-first".
> Aqui a gente **programa uma IHM e um CLP virtuais** que se comportam como os reais,
> desenvolve o PCP em cima deles, e depois carrega **o mesmo programa** no hardware físico.

---

## 🎯 O que é isto (e o que NÃO é)

Este espaço é para o **CLP/IHM virtual programável** — um soft-PLC que roda no seu PC,
com lógica (Ladder/ST) e telas de IHM, expondo um **servidor Modbus TCP**.

Não confundir com o `src/monitoramento/simulator.py`:

| | `simulator.py` (já existe) | Virtualização (esta pasta) |
|---|---|---|
| Escreve onde | Direto no **banco** (pula o Modbus) | Em **registradores Modbus** |
| Testa o caminho | Banco → API → tela | **Modbus → coletor → banco → API → tela** (caminho real) |
| Serve para | Popular dado em massa rápido | Validar/portar pro **hardware real** |
| Programável como CLP | Não (é script Python) | **Sim** (Ladder/ST + telas), igual ao equipamento |

Os dois convivem. Este é o que garante que "plugar o físico" (Fase 7) seja só trocar o IP.

---

## 🔌 O contrato: por que Modbus TCP é tudo que importa

O `monitoramento` conversa com QUALQUER máquina por uma única interface:

```
src/monitoramento/ihm_client.py   →  ModbusTcpClient(ip, port)
src/monitoramento/data_processor.py:
    read_holding_registers(endereço, count=1)   # lê cada grandeza
    write_registers(endereço, [valor])          # escreve a meta
```

O de/para "endereço Modbus → significado" fica na tabela **`tb_registrador`**
(`id_ihm`, `nu_endereco`, `tx_descricao`).

**Logo, o CLP virtual só precisa:** ser um servidor Modbus TCP, num IP:porta, com
holding registers nos endereços que a gente definir. O resto do sistema não sabe (nem
precisa saber) se é virtual ou físico.

O mapa de registradores da máquina piloto está em [`mapa_registradores.md`](mapa_registradores.md).

---

## 🗂️ Estrutura da pasta

```
virtualizacao/
├── README.md                # este arquivo
├── mapa_registradores.md    # o "contrato de dados" (endereços Modbus) da Tração e Flexão
├── clp/                     # projeto do CLP virtual (lógica Ladder/ST)
│   └── README.md
└── ihm/                     # projeto da IHM virtual (telas)
    └── README.md
```

---

## ▶️ Fluxo de trabalho pretendido

1. **Definir o contrato** — preencher `mapa_registradores.md` com as grandezas reais da
   Tração e Flexão (força, deslocamento, status, meta…) e seus endereços Modbus.
2. **Programar o CLP virtual** (`clp/`) — lógica que gera esses valores de forma plausível
   (rampa de força, curva até ruptura) e os expõe nos holding registers via Modbus TCP.
3. **Desenhar a IHM virtual** (`ihm/`) — telas do operador (start/stop, meta, leitura ao vivo).
4. **Cadastrar a máquina no PCP** — inserir a linha em `tb_ihm` apontando para
   `IP:porta` do soft-PLC, e os registradores em `tb_registrador` batendo com o mapa.
5. **Rodar o `monitoramento`** apontado pra essa IHM (`IHMS=<id>`) e ver o dado subir
   pelo caminho real até as telas do React.
6. **(Fase 7) Plugar o físico** — carregar o mesmo programa na IHM/CLP real e trocar só o
   `tx_ip_address` em `tb_ihm`.

---

## 🧰 Toolchain — **Delta** (decidido)

Ecossistema Delta, para que o mesmo projeto virtual porte direto pro hardware Delta real.
Requisito atendido: Delta é **nativamente Modbus TCP**.

| Programa | Papel | Onde entra |
|----------|-------|-----------|
| **ISPSoft** | Programar a lógica do CLP (Ladder/ST/FBD) — séries AS/DVP/AH | pasta `clp/` |
| **COMMGR** | Gerenciador de comunicação **+ simulador de CLP** (roda o CLP virtual no PC e o expõe como **servidor Modbus TCP**) | roda o `clp/` |
| **DOPSoft** | Programar as telas da IHM (série DOP) — tem **simulador** online/offline | pasta `ihm/` |

> Dica: prefira a **série AS** no ISPSoft — o simulador dela tem a melhor emulação de
> Ethernet/Modbus TCP. Os três são gratuitos (Delta Download Center / DIAStudio).
> Sucessores mais novos, se um dia quiser: DIADesigner (CLP) e DIAScreen (IHM).

### Loop de virtualização (confirmado funcionando)

```
ISPSoft (lógica)  ──►  COMMGR simulador  ──►  servidor Modbus TCP (localhost:502)
                                                 ▲                    ▲
                                                 │                    │
                        DOPSoft simulador (telas)┘   src/monitoramento (pymodbus) ┘
```

Tanto a IHM simulada quanto o `monitoramento` leem/escrevem os **mesmos registradores**
do CLP virtual. É o mesmo caminho que existirá no hardware real.

### Passo a passo

1. **ISPSoft** → criar projeto série AS, escrever a lógica do ensaio, mapear as grandezas do
   [`mapa_registradores.md`](mapa_registradores.md) em registradores D acessíveis por Modbus.
2. **COMMGR** → criar um driver **Simulator**, dar Start → sobe o CLP virtual como servidor
   Modbus TCP. Confirmar que Ethernet/Modbus TCP está habilitado.
3. **Teste rápido** (antes de mexer no MES): rodar um `read_holding_registers` com `pymodbus`
   (já está no `requirements.txt`) apontando pro IP:502 do simulador. Se ler → caminho aberto.
4. **DOPSoft** → desenhar as telas, apontar o controlador para o CLP (Modbus TCP), rodar o simulador.
5. **Cadastrar no MES** → `tb_ihm` com o IP:502 do simulador + `tb_registrador` batendo com o mapa.
6. **Rodar `src/monitoramento`** com `IHMS=<id>` e ver o dado subir até o React.

> ⚠️ **Endereçamento**: no Modbus da Delta os holding registers são "4x" (base 400001,
> 1-based), mas o `pymodbus` usa endereço **0-based**. Ex.: `400001` na Delta = `address=0`
> no `read_holding_registers`. Alinhe isso ao preencher `nu_endereco` em `tb_registrador`.
```

