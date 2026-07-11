# Mapa de Registradores — Máquina de Tração e Flexão (contrato de dados)

> Este é o **contrato** entre o CLP virtual (ou físico) e o PCP. É o mesmo formato da
> tabela `tb_registrador` do banco. Enquanto as grandezas reais da máquina não estiverem
> confirmadas, isto é um **TEMPLATE** — ajuste endereços, escalas e itens conforme o ensaio.

## Convenções

- **Tipo**: todos são *holding registers* (função Modbus 03 leitura / 06 e 16 escrita).
- **Palavra de 16 bits** (0–65535). Valores com decimais ou > 65535 usam **fator de escala**
  (ex.: força em N × 10 → 1 registrador guarda décimos de N) ou **2 registradores** (32 bits).
- **Sentido**: `R` = PCP lê da máquina (telemetria) · `W` = PCP escreve na máquina (config).

## Registradores

| Endereço | tx_descricao        | Sentido | Unidade / Escala        | Observação                                  |
|---------:|---------------------|:-------:|-------------------------|---------------------------------------------|
| 0        | `status`            | R       | código                  | Ex.: 0=parada, 49=ensaiando, 52=manutenção  |
| 1        | `forca`             | R       | N (× 10 → décimos de N)  | Força instantânea aplicada                   |
| 2        | `deslocamento`      | R       | mm (× 100 → centésimos) | Deslocamento do travessão                    |
| 3        | `forca_maxima`      | R       | N (× 10)                | Pico de força no ensaio corrente             |
| 4        | `ruptura`           | R       | bool (0/1)              | 1 quando detectou ruptura                    |
| 5        | `contador_ensaios`  | R       | unid.                   | Nº de corpos de prova ensaiados              |
| 6        | `meta`              | R/W     | unid.                   | Meta de ensaios (o PCP escreve aqui)         |
| 7        | `cod_operador`      | R       | código                  | Operador logado na IHM                       |
| 8        | `comando_iniciar`   | W       | bool (0/1)              | (opcional) PCP dispara início do ensaio      |

> A curva **força × deslocamento** para os KPIs (ROADMAP Fase 2) é reconstruída no banco
> a partir do histórico de `forca` e `deslocamento` gravado em `tb_log_registrador` — não
> precisa de registrador próprio.

## Como isto vira linhas no banco

Para cada item acima, uma linha em `tb_registrador` (`id_ihm` = a máquina cadastrada em
`tb_ihm`, `nu_endereco` = a coluna Endereço, `tx_descricao` = a coluna tx_descricao). É esse
de/para que o `data_processor.read_registers()` percorre para saber o que ler.
