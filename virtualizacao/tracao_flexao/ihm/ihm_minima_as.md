# IHM mínima para o AS atual (demo das 3 telas)

> **Objetivo:** uma IHM enxuta no DOPSoft, casada com o **mapa compacto do POU ST**
> que roda hoje no AS300 Simulator, só pra fechar a demo *MES + Twin 3D + IHM* em
> paralelo. **Descartável** — quando o parceiro migrar a ladder REAL pro AS
> (mapa rico: D3000/D3020, M5–M11…), reaproveita-se o `.dpa` original do parceiro,
> não esta IHM. Ver `renomear_pous.md` e o estado em memória.
>
> Por que uma IHM nova e não a do parceiro: a `.dpa` do parceiro foi desenhada
> contra o mapa **DVP** (telemetria em D3000/D3020, comandos M5/M6/M7/M9/M11). O AS
> de hoje NÃO é essa ladder portada — é o POU ST genérico, com mapa totalmente
> diferente. Cada objeto da IHM do parceiro cairia num registrador errado.

---

## Passo 0 — Como a IHM conecta no AS (destrava tudo; testar ANTES de desenhar)

O AS300 Simulator responde **Modbus TCP em `127.0.0.1:10002`** (não é a 502 padrão).
Duas rotas possíveis; comece pela **Rota B**.

### Rota B — DOPSoft como mestre Modbus TCP  ✅ recomendada
- No DOPSoft, criar um *Link* do tipo controlador **"Modbus TCP/IP"** (driver genérico).
- IP `127.0.0.1`, porta **10002**, Station/Unit `1` (0/255 também funcionam no sim).
- Rodar **Online Simulation** (não a offline — a offline simula o CLP por dentro e
  não sai pra rede).
- Endereçamento: os objetos referenciam **holding register `4x`** (ver tabela abaixo).
- Vantagem: é o MESMO canal que o `bridge_as.py` (twin) e o coletor do MES já usam.
  Multi-cliente Modbus TCP já validado → IHM + twin + MES leem o sim ao mesmo tempo.

### Rota A — driver nativo Delta AS (fallback)
- *Link* do tipo **"Delta AS Series"** conectando via COMMGR/Ethernet ao simulador.
- Endereçamento por nome de device: `D0`, `D10`, `D50`… direto (sem offset).
- Só usar se a Rota B não fechar. Depende da integração DOPSoft↔COMMGR, menos previsível.

> **Off-by-one (atenção):** Delta usa `4x` **1-based** (`400001`), pymodbus é **0-based**
> (`address=0`). O `bridge_as` lê `D0` em `address=0`. Logo **D(n) = 4x referência (n+1)**.
> Se ao conectar os valores vierem "deslocados de 1 casa", ajuste ±1 na base do driver.

---

## Mapa dos objetos (mapa AS de hoje)

Fonte da verdade: `twin3d/bridge_as.py`. `D(n) → holding register n`. Escala = divisor.

### Displays (leitura)
| Objeto DOPSoft | Rota A (device) | Rota B (4x 1-based) | Escala p/ exibir | Formato |
|---|---|---|---|---|
| Modo (texto multi-estado) | `D0` | `400001` | — (0=Parado, 1=Tração, 2=Flexão) | texto |
| Lâmpada "Rodando" | `D1` | `400002` | 0/1 | indicador |
| Lâmpada/alarme "Ruptura" | `D2` | `400003` | 0/1 | indicador (vermelho) |
| Deslocamento | `D10` | `400011` | ÷100 → mm | 2 casas |
| Força | `D12` | `400013` | ×1 → N | 0 casas |
| Tensão | `D14` | `400015` | ÷10 → MPa | 1 casa |
| Alongamento | `D16` | `400017` | ÷100 → % | 2 casas |
| Módulo | `D18` | `400019` | ×1 → MPa | 0 casas |
| Força máx. | `D20` | `400021` | ×1 → N | 0 casas |
| R² | `D22` | `400023` | ÷1000 | 3 casas |

> **Escala no display:** no Numeric Display do DOPSoft use o campo de *scaling/proporção*
> (ganho) — ex. ganho `0.01` p/ D10, `0.1` p/ D14, `0.001` p/ D22 — ou ajuste "Decimal Pt.".
> Assim a IHM mostra unidade de engenharia sem tocar no CLP (mesma lógica do `nu_divisor`
> que o coletor do MES usa).

### Botões (escrita em `D50` = comando; o CLP consome zerando D50)
| Botão | Ação (Set Word / constante) | Valor |
|---|---|---|
| **Tração** | escreve em `D50` (Rota B: `400051`) | `1` |
| **Flexão** | escreve em `D50` | `2` |
| **Parar** | escreve em `D50` | `3` |
| **Zerar** | escreve em `D50` | `4` |

> Use botão do tipo **Set Constant / Set Word** (escrita momentânea de valor). Não precisa
> "manter" — o POU ST lê D50, executa e zera D50 sozinho no próximo scan.

---

## Layout sugerido (1 tela)
```
┌──────────────────────────────────────────────┐
│  ENSAIO DE TRAÇÃO E FLEXÃO        [●Rodando]   │
│  Modo: <Tração/Flexão/Parado>    [●RUPTURA]    │
├──────────────────────────────────────────────┤
│  Deslocamento: __.__ mm     Força:   ___ N     │
│  Tensão:       __._ MPa     F.máx:   ___ N     │
│  Along.:       __.__ %      Módulo:  ___ MPa   │
│  R²: _.___                                     │
├──────────────────────────────────────────────┤
│   [ TRAÇÃO ]  [ FLEXÃO ]  [ PARAR ]  [ ZERAR ] │
└──────────────────────────────────────────────┘
```

---

## Como subir a demo das 3 telas
1. **COMMGR**: Add → "AS300 Simulator" → **Start**.
2. **ISPSoft**: Download + **Run** do POU ST (`clp/programa_as_st.txt`).
3. **Twin** (PowerShell): `$env:SERVE_PORT = "8010"; python twin3d/bridge_as.py` → http://127.0.0.1:8010
4. **MES**: coletor (`IHMS=8 python src/monitoramento/main.py`) + API (:8000) + frontend (:5173).
5. **IHM**: DOPSoft → Online Simulation (Rota B, Modbus TCP 127.0.0.1:10002).

Você inicia/para pela IHM (escreve D50) → o AS executa a lógica real → o mesmo bloco D
é lido pelo twin (vê a máquina animar) e pelo coletor (grava no MES). Um CLP, três clientes.

## Pendências / a validar
- [ ] **Rota B conecta?** Confirmar se a Online Simulation do DOPSoft abre mestre Modbus TCP
      em porta não-padrão (10002). É o teste destravante.
- [ ] Off-by-one da base 4x (ver aviso acima).
- [ ] Concorrência: IHM (Modbus) + twin (Modbus) + coletor (Modbus) simultâneos no sim
      — multi-cliente já validado no projeto, mas confirmar com a IHM junto.
