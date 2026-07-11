# Mapa de Registradores — Tração e Flexão

> **Contrato de dados** entre o CLP (DVP-SX2) e o PCP. Mesmo formato da tabela `tb_registrador`.
> **Nomes confirmados** pelo export oficial da Device Comment List do ISPSoft
> (`clp/comentarios_dispositivos.txt` / `.xlsx`, 2026-07-10). Os **tipos** (WORD/DWORD/REAL)
> ainda são inferidos da ladder (instruções `D...`/`...R` = 32 bits/float) — alta confiança.
> **Falta só** o offset `D → Modbus` (Etapa 2, via `teste_modbus.py` no simulador).

## ⚠️ Convenção de endereçamento Modbus (definida e validada no mock)

> ⚑ O simulador do DVP-SX2 **não expõe Modbus TCP** (DVP não tem Ethernet nativo). Por isso a
> simulação da camada Modbus é feita pelo **`clp/mock_clp.py`** (servidor Modbus TCP em Python
> com o mapa abaixo). Na Fase 7, um **gateway RS485→TCP** ocupa o mesmo lugar, com esta convenção.

- **Registrador `D(n)` → holding register `4096 + n`** (padrão DVP, `0x1000 + n`), 0-based.
  Ex.: `D3000` → endereço Modbus `7096`. É este número que vai em `tb_registrador.nu_endereco`.
- **Bit `M(n)` → coil `2048 + n`** (`0x0800 + n`). Comandos são coils graváveis.
- **Valor REAL (float 32 bits) = 2 registradores**, **word baixa primeiro** (little-endian).
  Decodificar: `struct.unpack("<f", struct.pack("<HH", reg_lo, reg_hi))`.
  Referência de leitura pronta em **`clp/ler_resultados.py`**.
- WORD (16 bits, ex. `D90`) = 1 registrador.

---

## 📤 TELEMETRIA — o PCP LÊ (R)

### Resultados do ensaio de TRAÇÃO — bloco "gráfico" `D3000` (REAL)
| Device | Nome | Unidade | Origem (cálculo) |
|--------|------|---------|------------------|
| `D3000` | Tensão | Pa/MPa | `D2004` = Força_N / Área |
| `D3002` | Módulo de Elasticidade | MPa | `D2008` = Tensão / Deformação |
| `D3004` | Tensão Máxima | Pa/MPa | `D2010` = Força_max_N / Área |
| `D3006` | Deformação | — / % | `D2018` = ΔL / L0 |
| `D3008` | Alongamento | % | `D2032` = (Lf/L0) × 100 |
| `D3010` | Deslocamento | mm | `D600` (DESLOC_REAL) |
| `D3012` | Força (Newton) | N | `D2000` — força no gráfico de tração |

### Resultados do ensaio de FLEXÃO — bloco "gráfico" `D3020` (REAL)
| Device | Nome | Unidade | Origem |
|--------|------|---------|--------|
| `D3020` | Força | N | `D622` (F_N) |
| `D3022` | Momento de Inércia | — | `D628` (FB MOMENTO_INERCIA) |
| `D3024` | Tensão de Flexão | Pa/MPa | `D632` (FB TENSÃO_DE_FLEXÃO) |
| `D3026` | Deformação Superficial | — | `D634` (FB DEFORMAÇÃO_SUPERFICIAL) |
| `D3028` | Módulo de Flexão | MPa | `D636` (FB MÓDULO_DE_FLEXÃO) |
| `D3030` | Momento Máximo | — | `D638` (FB MOMENTO_MAXIMO) |
| `D3032` | Deslocamento (flexão) | mm | `D598` (DESLOC_REAL_flexão) |

### Leituras "ao vivo" (durante o ensaio)
| Device | Nome | Tipo | Observação |
|--------|------|------|------------|
| `D90` | Força Atual | WORD | saída do SCLP (célula escalada) |
| `D602` | Força_Kgf | REAL | força atual em kgf |
| `D2000` | Força_Newton | REAL | força atual em N (D92 × 9,806) |
| `D600` | Deslocamento real (tração) | REAL | mm |
| `D598` | Deslocamento real (flexão) | REAL | mm |
| `D1030` | Contador de pulsos | DWORD | posição bruta do motor (PV Y0) |
| `D650` | Valor_tarado (força já com tara) | REAL | força "real" usada nos picos |

### Picos do ensaio (HOLD_TARA) e módulo de flexão (regressão)
| Device | Nome | Tipo | Observação |
|--------|------|------|------------|
| `D718` | Força Máxima (pico, tração) | REAL | pico da força |
| `D722` | Força máxima (flexão) | REAL | pico flexão |
| `D642` | Tensão Máxima (flexão) | REAL | pico de tensão |
| `D610` | Deslocamento máx / comprimento final | REAL | usado na deformação |
| `D604`/`D606` | Deslocamento máx (flexão) | REAL | |
| `D24` | Inclinação da Reta (slope m) | REAL | regressão força×desloc |
| `D26` | R (correlação) | REAL | |
| `D28` | R² (coef. de correlação) | REAL | qualidade do ajuste |
| `D46` | LIMITE PARA R² | REAL | **limiar configurável** (0,990) da trava |
| `D32`/`D34` | Módulo de flexão (por regressão) | REAL | trava quando R²≥0,990 |
| `D12`–`D22` | Somatórias (X, Y, X², Y², XY, contador) | DWORD | base da regressão |

### Status / eventos (bits M) — o PCP LÊ (R)
| Bit | Nome | Significado |
|-----|------|-------------|
| `M30` | Material íntegro | força passou do limite (carregado) |
| `M31` | Material sofreu ruptura | rompeu → dispara parada |
| `M21` | SOBRECARGA | força > 75% da célula *(rotina Disabled)* |
| `M44` | Trava de captura | R²≥0,990 → congela o módulo |
| `M17` | Trigger de captura | pulsa a cada ~passo de deslocamento (amostra a curva) |

## 📥 SETPOINTS / CONFIG — o PCP/IHM ESCREVE (W)

| Device | Nome | Ensaio | Observação |
|--------|------|--------|------------|
| `D412` | Desl_Prog_IHM | ambos | deslocamento alvo (mm) → vira pulsos em D400/D406 |
| `D408` | Vel_Prog_IHM | ambos | velocidade programada → vira D508 |
| `D414` | Limite_Desl_IHM | ambos | limite de deslocamento |
| `D2002` | Área da seção | tração | área do corpo de prova |
| `D2022` | Comprimento inicial (L0) | tração | |
| `D610` | Comprimento final | tração | medido/entrada |
| `D434` | Espessura/altura (h) | flexão | |
| `D436` | Largura (b) | flexão | |
| `D438` | Vão (L) | flexão | |
| `D422` | IHM_VAL_CELU | — | calibração/escala da célula |
| `D100`–`D103` | Parâmetros de escala da célula | — | max/min em ponto e escala |
| `D2006` | Limite de força (ruptura) | ambos | limiar que define carga/ruptura |
| `D2034` | Porcent_desloc (vel. baixa inicial) | tração | % do desloc. em baixa velocidade (região elástica) |

## 🎛️ COMANDOS (bits M) — o PCP/IHM ESCREVE (W)

| Bit | Nome | Ação |
|-----|------|------|
| `M5` | Subir_IHM | move cabeçote pra cima |
| `M6` | Descer_IHM | move cabeçote pra baixo |
| `M7` | Parar_IHM | para / reset |
| `M9` | Inicia_IHM_Tracao | inicia ensaio de tração |
| `M11` | Inicia_IHM_Flexao | inicia ensaio de flexão |
| `M100` | Zera_desl_IHM | zera o deslocamento (tara de posição) |
| `M101` | IHM_TARA_BALAN | tara a força (zera o peso atual) |
| `M34` | Continua_teste | segue o teste após ruptura |
| `M14` | ANULA LINHA | (config) habilita a troca de velocidade elástica |

## 🟢 STATUS (bits M) — o PCP LÊ (R)
| Bit | Nome | Significado |
|-----|------|-------------|
| `M2` | Inicia | ensaio em andamento |
| `M4` / `M8` | Selec_Subida / Selec_Descida | direção selecionada |
| `M31` | Material sofreu ruptura | corpo de prova rompeu |
| `M32` / `M33` | Bit captura tração / flexão | modo do ensaio |

## 🔌 I/O físico (na Fase 7, hardware real)
| Ponto | Nome |
|-------|------|
| `X0` | Emergência |
| `X1` | Fim de curso inferior |
| `X2` | Fim de curso superior |
| `Y0` / `Y1` | Pulso / direção do motor de passo |

---

## Registradores especiais do módulo analógico (SX2) — não são telemetria
`D1115` (config canal analógico), `D1118` (tempo de amostragem), `D1110` (valor médio),
`D1120` (formato COM2 RS-485), `D1343` (rampa accel/decel do pulso), `D95` (erro COM2).

## Próximos passos pra fechar o contrato
1. **Exportar a tabela de símbolos do ISPSoft (CSV)** → confirma tipos (WORD/DWORD/REAL) e nomes.
2. **`teste_modbus.py`** contra o simulador → descobrir o **offset D→Modbus real** e a ordem de words dos floats.
3. Marcar quais desses viram linha em `tb_registrador` (provavelmente os blocos `D3000`/`D3020` + força/deslocamento ao vivo + os comandos M).
