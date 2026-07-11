# Mapa de Registradores — Prensa (protótipo de validação)

> **Contrato de dados** entre o CLP virtual (ou físico) e o PCP. Mesmo formato da tabela
> `tb_registrador` do banco. Esta é a **máquina mais simples que exercita todas as camadas**
> da plataforma — um pistão que desce e sobe num intervalo configurável.
> A esteira e a `meta` entram depois, com o loop já validado.

## Convenções

- **Tipo**: todos são *holding registers* (função Modbus 03 leitura / 06 e 16 escrita).
- **Palavra de 16 bits** (0–65535). Decimais/valores grandes usariam fator de escala — aqui não precisa.
- **Sentido**: `R` = PCP lê da máquina (telemetria) · `W` = PCP escreve na máquina (config/comando).

## Registradores

| Endereço | tx_descricao   | Sentido | Escala           | Observação                              |
|---------:|----------------|:-------:|------------------|-----------------------------------------|
| 0        | `status`       | R       | código           | 0=parada, 1=rodando                     |
| 1        | `posicao`      | R       | % (0=topo, 100=fundo) | posição do cabeçote — anima gráfico e 3D |
| 2        | `contador`     | R       | unid.            | ciclos/prensadas produzidas             |
| 3        | `intervalo_s`  | R/W     | segundos         | tempo entre ciclos (**o PCP escreve**)  |
| 4        | `comando`      | W       | código           | 1=iniciar, 2=parar                       |

> 5 registradores. É o mínimo que fecha o ciclo completo: telemetria (`status`, `posicao`,
> `contador`), um analógico em movimento (`posicao`), uma **escrita de config** (`intervalo_s`)
> e um **comando** (`comando`). O passo de escrita é o que costuma ser esquecido — está aqui de propósito.

## Os dois blocos do Ladder (ISPSoft)

Manter mentalmente separados — só o **Controlador** vai pro hardware físico (Fase 7):

**Controlador** (lógica real da máquina):
- `comando==1` → liga bit interno `M_rodando`, `status=1`
- `comando==2` → desliga `M_rodando`, `status=0`
- Timer com preset = `intervalo_s`; enquanto `M_rodando`, ao estourar → dispara um curso e `contador +1`

**Planta simulada** (só existe no virtual — desabilitar na Fase 7, quando entram os sensores reais):
- ao disparar o curso, `posicao` sobe 0→100→0 alguns pontos por scan, dando movimento visível

## Como isto vira linhas no banco

Uma linha em `tb_registrador` por item acima (`id_ihm` = a prensa cadastrada em `tb_ihm`,
`nu_endereco` = a coluna Endereço, `tx_descricao` = a coluna tx_descricao). É esse de/para que
o `data_processor.read_registers()` percorre para saber o que ler.

> ⚠️ **Endereçamento**: no Modbus da Delta os holding registers são "4x" (400001, 1-based),
> mas o `pymodbus` é **0-based**. `400001` na Delta = `address=0` aqui. Alinhe ao preencher `nu_endereco`.
