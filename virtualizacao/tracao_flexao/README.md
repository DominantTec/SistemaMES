# Virtualização — Tração e Flexão (máquina piloto real)

> Parte da **Fase 1** do [`../../ROADMAP.md`](../../ROADMAP.md), pela ótica "digital-first".
> **Diferença da prensa:** aqui os projetos **já existem** (CLP em ISPSoft + IHM em DOPSoft,
> feitos pelo parceiro). A gente **não programa do zero** — a gente **carrega e roda** os
> projetos reais em simulação. É a lógica de verdade da máquina rodando no PC.

---

## ✅ Estado da camada de dados (2026-07-10)

1. **Nomes dos registradores confirmados** — export da Device Comment List do ISPSoft em
   `clp/comentarios_dispositivos.txt`/`.xlsx`; mapa oficializado em `mapa_registradores.md`.
2. **Simulador DVP não expõe Modbus TCP** (confirmado: porta 10002 = protocolo Delta, não Modbus;
   502 recusa). Decisão: simular a camada Modbus com **`clp/mock_clp.py`** (servidor Modbus TCP
   em Python, com o mapa real e ensaio plausível) — **testado e funcionando**. A validação da
   *ladder real* fica no monitoramento online do ISPSoft (separado, não precisa de Modbus).

### Como usar o mock + rodar no MES
```
python clp/mock_clp.py                 # sobe o Modbus TCP em 127.0.0.1:502
python clp/ler_resultados.py iniciar   # manda M9 e lê os resultados (outro terminal)
```
Para o MES coletar de verdade:
1. Rodar **`cadastro_mes.sql`** no banco `MES_Core` (cria linha + máquina apontando pro mock +
   registradores). Ele devolve o `id_ihm` cadastrado.
2. Setar a env `IHMS` do `monitoramento` incluindo esse `id_ihm`, subir o mock e rodar o coletor.

O coletor já lê **REAL (float 32 bits)**: `tb_registrador.nu_qtd_words = 2` → lê 2 words e
decodifica float (suporte adicionado em `data_processor.py` / `_core.py` / `init.sql`).

> Pendente / próximo: aplicar a **renomeação dos POUs/FBs** no ISPSoft ([`renomear_pous.md`](renomear_pous.md))
> e validar a ladder real no monitoramento online do ISPSoft.

---

## 📦 O que já temos (arquivos do parceiro)

| Pasta | Arquivo | Ferramenta | Estado |
|-------|---------|-----------|--------|
| `clp/` | `Projeto_tração_flexão0707202.isp` (+`.bak`, `.ini`) | **ISPSoft** | binário; abre só no ISPSoft |
| `ihm/` | `Programa maquina de tração e flexão 02.07.2026 - betin.dpa` | **DOPSoft** | binário; abre só no DOPSoft |

> ⚠️ Os `.isp` e `.dpa` são **binários comprimidos** — não dá pra ler a ladder nem as telas
> fora das ferramentas Delta. O único texto legível é o `.ini`, que revelou a arquitetura abaixo.

## 🧩 Arquitetura do programa do CLP (extraída do `.ini`)

CPU Delta código `000F` · conexão **Ethernet** (IP alvo `192.168.11.10`, porta `12346`, station 1).
Programa dividido em **10 módulos (POUs)**:

| Módulo (POU) | Papel |
|---|---|
| `Celula_de_Carga` | leitura de força (célula de carga) |
| `CONTROL_MOTOR_PASSO` | atuação / movimento (motor de passo) |
| `MODULO_DE_FLEXAO_PARCIAL` / `NOVO_MODULO_DE_FLEXAO` | lógica do ensaio de flexão |
| `Parada_Ruptura` | detecção de ruptura do corpo de prova |
| `Regressao_Linear_M` | regressão linear (cálculo do "M" = módulo/inclinação) |
| `Coeficiente_de_correlacao` | estatística (R da regressão) |
| `SOMATORIAS` / `Formulas` | somatórias e fórmulas do cálculo |
| `DevCom` | comunicação com dispositivos |

> Observação estratégica: metade dos módulos é **matemática** (regressão, correlação, somatórias).
> São fortes candidatos a, no futuro, migrar do CLP para o software — ver a seção
> "🔮 Evolução futura" do ROADMAP. **Por enquanto, deixa tudo no CLP** e só espelha os valores.

---

## ▶️ Como começar (primeira etapa: rodar a simulação)

O objetivo desta etapa é **ver a lógica da máquina rodando** e conseguir **ler um registrador
por Modbus TCP** de fora. Só isso já destrava todo o resto.

1. **Abrir o projeto no ISPSoft** → confirmar o **modelo exato da CPU** (código `000F`) e se o
   **simulador** dela é suportado. Anotar o modelo aqui e em [`clp/README.md`](clp/README.md).
2. **Rodar o simulador** (COMMGR → driver *Simulator* → Start). O CLP virtual vira **servidor
   Modbus TCP** em `localhost:502`.
3. **Teste rápido com `pymodbus`** (script pronto em [`clp/README.md`](clp/README.md)) — se ler
   qualquer holding register, o caminho está aberto.
4. **Abrir a IHM no DOPSoft** e rodar o **simulador** apontando pro CLP virtual — operar o ensaio.
5. **Extrair o contrato Modbus** → no ISPSoft, exportar a **tabela de símbolos (CSV)** e
   preencher [`mapa_registradores.md`](mapa_registradores.md). É o de/para que liga tudo.

Depois disso: cadastrar no MES (`tb_ihm` + `tb_registrador`) e rodar o `monitoramento` —
igual ao fluxo da prensa (ver [`../README.md`](../README.md)).

---

## 🗂️ Estrutura da pasta

```
tracao_flexao/
├── README.md                # este arquivo
├── mapa_registradores.md    # o contrato Modbus — A PREENCHER com o export do ISPSoft
├── clp/                     # projeto ISPSoft do parceiro (.isp/.bak/.ini) + como rodar
│   └── README.md
└── ihm/                     # projeto DOPSoft do parceiro (.dpa) + como rodar
    └── README.md
```

> Toolchain e loop de virtualização completos: [`../README.md`](../README.md).
