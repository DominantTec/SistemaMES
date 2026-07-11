# Twin 3D — Tração e Flexão (protótipo)

Protótipo isolado (Opção A) para **visualizar e controlar** a máquina por um desenho 3D,
lendo/escrevendo no CLP via Modbus. Geometria **representativa** — a modelagem
fiel (Unity/metaverso) vem depois e reaproveita o mesmo contrato de API abaixo.

Há **dois bridges** com o MESMO contrato HTTP — o front não muda:
- **`bridge_as.py`** (recomendado) → lê o **CLP AS real rodando no simulador do ISPSoft**
  (lógica ST em `../clp/programa_as_st.txt`), Modbus TCP em `127.0.0.1:10002`, mapa inteiro-escalado.
- **`bridge.py`** (legado/fallback) → lê o **mock em Python** (`../clp/mock_clp.py`), Modbus em `:502`.

## Como rodar (caminho AS — lógica real, sem hardware)
```
# 1) ISPSoft: AS300 Simulator em RUN com programa_as_st.txt
#    (COMMGR: Add -> Type "AS300 Simulator" -> Start ; ISPSoft: Download + Run)

# 2) ponte Modbus<->HTTP
python bridge_as.py

# 3) abra no navegador
http://127.0.0.1:8000
```
Clique **▶ Tração** (cabeçote sobe, corpo de prova estica/muda de cor e rompe) ou **▶ Flexão**
(viga sobre dois apoios, punção descendo, viga fletindo e trincando no centro). **⟲ Zerar** reinicia.
A animação alterna sozinha pelo campo `modo` da telemetria (1=tração, 2=flexão).

## Como rodar (caminho mock — legado)
```
python ../clp/mock_clp.py     # terminal 1 (CLP virtual em :502)
python bridge.py              # terminal 2
```

## Arquitetura
```
navegador (three.js)  ──HTTP──►  bridge.py  ──Modbus TCP──►  mock_clp.py (CLP virtual)
   twin3d.html          telemetria/comando      poller 20Hz        127.0.0.1:502
```
O `bridge.py` mantém um estado em memória (poller lê a máquina ~20x/s) e expõe HTTP. O 3D
consulta a telemetria a 10Hz e interpola pra animar suave.

## Contrato da API (reaproveitável — ex.: cliente Unity no futuro)
Base: `http://127.0.0.1:8000`

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/telemetria` | JSON do estado atual (campos abaixo) |
| POST | `/comando/<acao>` | dispara um comando (escreve o coil no CLP) |

**Telemetria (`GET /telemetria`)** — valores de engenharia float + `modo` (0=idle 1=tração 2=flexão):
```json
{ "modo": 1, "deslocamento": 2.4, "forca": 428.0, "tensao": 42.8, "alongamento": 4.8,
  "modulo": 2000.0, "forca_max": 428.0, "r2": 0.999,
  "rodando": true, "ruptura": false, "conectado": true }
```

**Comandos (`POST /comando/<acao>`)**: `iniciar_tracao`, `iniciar_flexao`, `parar`, `zerar`.
No `bridge_as.py` cada um escreve o registrador de comando `D50` (1/2/3/4); no `bridge.py` (mock)
escreve o coil M correspondente.

> Como tudo passa por Modbus, este mesmo bridge/contrato serve para a **máquina real** na Fase 7
> (troca `CLP_HOST/CLP_PORT` no `bridge_as.py` pelo IP do AS físico — Modbus provável na 502).
> Segurança: comando é supervisório; emergência permanece hardwired (NR-12).

## Próximos passos
- Curva força × deslocamento ao vivo na tela.
- Portar para dentro do MES (Opção B) e, no futuro, modelagem fiel em Unity (metaverso).
