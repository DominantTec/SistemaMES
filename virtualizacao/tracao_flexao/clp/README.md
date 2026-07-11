# CLP — Tração e Flexão (projeto ISPSoft do parceiro)

Projeto **real** do CLP da máquina de Tração e Flexão. **Não é para reprogramar** — é para
abrir, rodar em simulação e extrair o contrato Modbus.

## Arquivos

- `Projeto_tração_flexão0707202.isp` — projeto ISPSoft (binário)
- `Projeto_tração_flexão0707202.bak` — backup (idêntico ao `.isp`)
- `Projeto_tração_flexão0707202.ini` — config em texto (CPU, comunicação, lista de POUs)

**CPU:** código `000F` (confirmar o modelo exato ao abrir → anotar aqui: `__________`).
**Comunicação real:** Ethernet, IP `192.168.11.10`, porta `12346`, station 1.

## Como rodar em simulação

1. **ISPSoft** → abrir o `.isp`. Verificar o **modelo da CPU** e se há **simulador** para ela.
   - Preferência do ecossistema é série **AS** (melhor emulação de Ethernet/Modbus TCP).
   - Se a CPU não tiver simulador, avaliar apontar a lógica pra uma CPU AS equivalente **só
     para simular** (sem alterar o projeto que vai pro hardware real).
2. **COMMGR** → criar driver **Simulator** → **Start**. Sobe o CLP virtual como **servidor
   Modbus TCP** (`localhost:502`).
3. **Teste rápido com `pymodbus`** (já está no `requirements.txt` do projeto) — provar que dá
   pra ler de fora antes de tocar no MES:

```python
from pymodbus.client import ModbusTcpClient

c = ModbusTcpClient("127.0.0.1", port=502)
c.connect()
rr = c.read_holding_registers(address=0, count=10)   # ajuste address/count ao mapa
print(rr.registers if not rr.isError() else rr)
c.close()
```

Se isso imprimir uma lista de números → **caminho aberto**, pode seguir pra IHM e pro mapa.

## Extrair o contrato

No ISPSoft, exportar a **tabela de símbolos globais em CSV** e preencher
[`../mapa_registradores.md`](../mapa_registradores.md). Esse de/para é o que liga o CLP virtual
ao MES, ao twin 3D e, na Fase 7, à máquina real (trocando só o IP).

> **Toolchain: Delta.** Loop completo em [`../../README.md`](../../README.md).
