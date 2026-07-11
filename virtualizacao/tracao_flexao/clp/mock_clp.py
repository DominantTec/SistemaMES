"""
Mock CLP — Tração e Flexão  (servidor Modbus TCP em Python)

Por que existe: o simulador do DVP-SX2 (COMMGR) NÃO expõe Modbus TCP (o DVP não tem Ethernet
nativo). Então, para desenvolver o MES/twin contra o contrato REAL de registradores, este script
sobe um servidor Modbus TCP que:
  - expõe o mapa de `mapa_registradores.md` (blocos D3000/D3020, força, deslocamento, comandos M);
  - simula um ensaio plausível (região elástica → escoamento → ruptura).

Quando a máquina real entrar (Fase 7), um gateway RS485→TCP ocupa este mesmo lugar e o MES
não muda — é o Princípio 2 do ROADMAP (mesma interface pra simulado e real).

Convenção de endereçamento (padrão DVP, para o gateway real usar igual):
  - Registrador D(n)      -> holding register Modbus  4096 + n   (0x1000 + n), 0-based
  - Bit M(n)              -> coil Modbus              2048 + n   (0x0800 + n), 0-based
  - Valor REAL (float 32) -> 2 registradores consecutivos, WORD BAIXA primeiro (little-endian)

Uso:
  python mock_clp.py            # porta 502 (padrão do MES)
  python mock_clp.py 5020       # outra porta, se a 502 estiver ocupada/bloqueada
"""
import asyncio, struct, sys
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext
from pymodbus.server import StartAsyncTcpServer

HOST = "0.0.0.0"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 502
DBASE = 0x1000   # D0  -> 4096
MBASE = 0x0800   # M0  -> 2048

# ---- datastore (zero_mode: endereço == índice, sem o -1 do Modbus 1-based) ----
slave = ModbusSlaveContext(
    hr=ModbusSequentialDataBlock(0, [0] * 8192),   # holding registers (D)
    co=ModbusSequentialDataBlock(0, [0] * 4096),   # coils (M)
    di=ModbusSequentialDataBlock(0, [0] * 4096),
    ir=ModbusSequentialDataBlock(0, [0] * 8192),
)
context = ModbusServerContext(slaves=slave, single=True)

def set_real(dn, v):
    lo, hi = struct.unpack("<HH", struct.pack("<f", float(v)))
    slave.setValues(3, DBASE + dn, [lo, hi])

def set_word(dn, v):
    slave.setValues(3, DBASE + dn, [int(v) & 0xFFFF])

def get_real(dn):
    lo, hi = slave.getValues(3, DBASE + dn, 2)
    return struct.unpack("<f", struct.pack("<HH", lo, hi))[0]

def get_coil(mn):
    return bool(slave.getValues(1, MBASE + mn, 1)[0])

def set_coil(mn, v):
    slave.setValues(1, MBASE + mn, [1 if v else 0])

# ---- modelo de material (curva tensão × deformação simplificada) ----
E_SIM = 2000.0    # módulo de elasticidade simulado (MPa)
YIELD = 0.02      # deformação de escoamento
ULT   = 0.08      # deformação de ruptura
SPEED = 1.0       # mm/s (tempo do simulador)

def stress_of_strain(eps):
    if eps <= 0:      return 0.0
    if eps <= YIELD:  return E_SIM * eps                                  # elástico
    if eps <= ULT:    return E_SIM * YIELD + (eps - YIELD) * (E_SIM * 0.05)  # encruamento leve
    return 0.0                                                            # rompeu

class Sim:
    state = "IDLE"    # IDLE | TRACAO | FLEXAO | RUPTURED
    disp = 0.0
    peakF = 0.0

sim = Sim()

async def updater():
    dt = 0.1
    while True:
        area = get_real(2002);  area = area if area > 0 else 10.0   # D2002 Area_IHM
        L0   = get_real(2022);  L0   = L0   if L0   > 0 else 50.0   # D2022 Compr_Inicial

        if get_coil(100):                       # M100 Zera_desl_IHM
            sim.disp = 0.0; sim.peakF = 0.0; sim.state = "IDLE"
            set_coil(31, False); set_coil(100, False)
        if get_coil(7):                         # M7 Parar_IHM
            sim.state = "IDLE"; set_coil(7, False)
        if sim.state == "IDLE":
            if get_coil(9):    sim.state = "TRACAO"; sim.disp = 0.0; sim.peakF = 0.0; set_coil(9, False)
            elif get_coil(11): sim.state = "FLEXAO"; sim.disp = 0.0; sim.peakF = 0.0; set_coil(11, False)

        running = sim.state in ("TRACAO", "FLEXAO")
        if running:
            sim.disp += SPEED * dt

        eps    = sim.disp / L0
        stress = stress_of_strain(eps)          # MPa
        forceN = stress * area                  # N
        if running and eps > ULT:               # ruptura
            forceN = 0.0; stress = 0.0
            set_coil(31, True); sim.state = "RUPTURED"
        sim.peakF = max(sim.peakF, forceN)

        # ---- telemetria (tração) ----
        set_real(600, sim.disp);  set_real(3010, sim.disp)          # deslocamento
        set_real(2000, forceN);   set_real(3012, forceN)           # força (N)
        set_real(602, forceN / 9.80665)                             # força (kgf)
        set_word(90, max(0, min(65535, int(forceN))))              # Força Atual (WORD)
        set_real(2004, stress);   set_real(3000, stress)           # tensão
        set_real(2018, eps);      set_real(3006, eps)              # deformação
        set_real(2032, eps * 100); set_real(3008, eps * 100)       # alongamento %
        set_real(2008, E_SIM);    set_real(3002, E_SIM)            # módulo elasticidade
        set_real(24, E_SIM);      set_real(32, E_SIM)              # inclinação / módulo flexão
        set_real(28, 0.999 if eps > 0 else 0.0)                    # R²
        set_real(718, sim.peakF)                                    # força máxima (pico)
        set_real(2010, sim.peakF / area); set_real(3004, sim.peakF / area)  # tensão máxima

        # ---- espelho flexão ----
        if sim.state == "FLEXAO":
            set_real(3020, forceN); set_real(3024, stress); set_real(3028, E_SIM); set_real(3032, sim.disp)

        set_coil(2, running)                    # M2 Inicia (rodando)
        await asyncio.sleep(dt)

async def main():
    print(f"Mock CLP Tração/Flexão — Modbus TCP em {HOST}:{PORT}")
    print("  D(n) -> HR 4096+n | M(n) -> coil 2048+n | REAL = 2 regs (word baixa primeiro)")
    print("  Comandos: M9=inicia tração, M11=flexão, M7=parar, M100=zera")
    asyncio.create_task(updater())
    try:
        await StartAsyncTcpServer(context=context, address=(HOST, PORT))
    except OSError as e:
        print(f"ERRO ao abrir a porta {PORT}: {e}\nTente outra porta: python mock_clp.py 5020")

if __name__ == "__main__":
    asyncio.run(main())
