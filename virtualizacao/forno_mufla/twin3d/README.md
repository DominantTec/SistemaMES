# Twin 3D — Forno Mufla

Mesmo molde do twin da Tração e Flexão: `twin3d.html` (three.js) + bridge Python que serve a
página e expõe telemetria/comandos por HTTP. **Não há CLP nem ISPSoft** nesta máquina: a
simulação inteira vive num servidor Modbus TCP em Python (`../clp/mock_clp_forno.py`).

## Arquitetura — uma fonte de verdade só
```
navegador (three.js) ──HTTP──► bridge.py ──Modbus──► mock_clp_forno.py ◄──Modbus── coletor MES
   twin3d.html         telemetria/comando  poller 20Hz      :5030                    (container)
                                                              │
                                                              └──► tb_log_registrador ──► API ──► dashboard
```
O bridge **não tem física nenhuma** — só traduz Modbus↔HTTP. Isso é de propósito: o coletor do
MES lê o mesmo servidor Modbus, então o que você vê no 3D e o que aparece no dashboard **não
podem divergir**. Se a física morasse no bridge, o MES precisaria de um caminho paralelo que não
validaria nada do pipeline real.

## Como rodar
```
# 1) CLP virtual (a máquina)
python ../clp/mock_clp_forno.py

# 2) ponte do 3D
python bridge.py

# 3) abra
http://127.0.0.1:8010
```
**▶ Aquecer** leva a câmara a 540 °C; as resistências ficam incandescentes, a amostra esquenta com
atraso, começa a calcinar (perde massa) e solta voláteis. **❋ Ventoinha** liga a exaustão: o rotor
gira, dispersa a fumaça e aumenta as perdas térmicas (o controle compensa com mais potência).
**⟲ Zerar** volta tudo ao ambiente.

Simulação **20x acelerada** (`SPEED` no mock): ~3 min de relógio até o patamar.

## O que está representado
| Elemento 3D | Significa |
|---|---|
| Gaiola de perfis + carcaça | estrutura do forno |
| Paredes translúcidas | permitem ver a câmara de qualquer ângulo (não é vidro real) |
| 6 serpentinas laterais | resistências — emissivo segue potência/temperatura |
| Bloco sobre o prato | corpo de prova — incandesce e **encolhe** conforme perde massa |
| Balança + haste + prato | termobalança de carregamento inferior (tipo TGA), com display ao vivo |
| Chaminé + ventoinha | exaustão; as partículas **são** os voláteis liberados |
| Gráfico lateral | calorimetria: câmara, amostra, setpoint e potência × tempo |

## Modelo (mock)

**Térmico** — primeira ordem com controle **PI** (proporcional + integral, anti-windup):
```
duty   = clamp(KP·erro + KI·∫erro dt, 0, 1),   erro = SP - T
P      = P_MAX · duty
dT/dt  = (P - k·(T - T_amb) - h·(T - Ts)) / C_cam
dTs/dt = h·(T - Ts) / (m·c)
```
O termo integral **não é enfeite**: só com proporcional o forno estabiliza em ~524 °C (droop de
16 °C) e nunca entra no patamar — e com a ventoinha ligada empacava em ~414 °C.

**Balança / perda ao fogo** — calcinação por Arrhenius:
```
d(alpha)/dt = A·exp(-Ea/(R·Ts))·(1 - alpha)     # avanço da reação, 0..1
massa       = m_inicial - m_volatil · alpha     # m_volatil = 8% de m_inicial
```
A **fumaça é a taxa de perda de massa** (`dm/dt`) — não é enfeite independente: as partículas
param quando os voláteis acabam. Reage entre ~400 e 540 °C e completa durante o patamar.

`P_MAX=3000 W`, `C_cam=9000 J/K`, `k=3,2 W/K` (+1,5 com ventoinha), amostra `500 g` de alumina,
`c=900 J/(kg·K)`, `h=30 W/K`, `KP=1/30`, `KI=6e-4`, `Ea=100 kJ/mol`, `A=11400 1/s`.

Números plausíveis, **não calibrados**. Validado: patamar em **540,3 °C** com peso de
**500 → 460,7 g** (perda de 7,86%, convergindo pros 8% de voláteis).

## Contrato da API
Base: `http://127.0.0.1:8010`

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/telemetria` | JSON do estado atual |
| POST | `/comando/<acao>` | `iniciar`, `parar`, `ventoinha` (toggle), `zerar` → escreve D50 |

```json
{ "modo": 2, "tempo": 3290, "temperatura": 540.3, "temp_amostra": 540.4, "setpoint": 540.0,
  "potencia": 1626, "duty": 0.542, "energia_kj": 8103, "q_amostra_kj": 213.7, "taxa": 0.0,
  "peso_inicial_g": 500.0, "peso_atual_g": 460.7, "perda_massa_pct": 7.86, "fumaca": 0.061,
  "ventoinha": false, "rodando": true, "patamar": true, "conectado": true }
```
`modo`: 0=ocioso · 1=aquecendo · 2=patamar · 3=resfriando.

## Mapa Modbus
Ver o cabeçalho de `../clp/mock_clp_forno.py` e `../cadastro_mes.sql`. Resumo: `D(n)` →
holding register `n` direto, words 16 bits **sem sinal** escaladas (o MES aplica `nu_divisor`).
Comando em `D50`. A taxa de aquecimento (°C/min) **não é registrador** — seria negativa no
resfriamento e word Modbus não tem sinal; ela é derivada no bridge e na API.

## Próximos passos
- Rampa/patamar programáveis (hoje o setpoint é fixo em 540 °C).
- Documentar as funcionalidades (como em `../../tracao_flexao/funcionalidades/`).
- Quando houver CLP: escrever a lógica e trocar o mock pelo IP real — nada mais muda.
