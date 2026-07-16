"""
Mock CLP — Forno Mufla  (servidor Modbus TCP em Python)

Por que existe: o forno ainda não tem CLP nem lógica no ISPSoft. Este script sobe um
servidor Modbus TCP que simula a máquina inteira (modelo térmico + balança) e expõe o
mapa de registradores. Assim, DUAS coisas leem a MESMA fonte de verdade:

    twin3d/bridge.py  (HTTP p/ o 3D)  ─┐
                                       ├──► mock_clp_forno.py  (Modbus TCP :5030)
    src/monitoramento (coletor do MES) ┘

O coletor grava em tb_log_registrador e a API monta os dashboards — exatamente o mesmo
caminho da máquina real. Na Fase 7, um CLP físico ocupa este lugar e nada mais muda.

Contrato de endereçamento (estilo AS300, ver ../twin3d/README.md):
  - D(n) -> holding register n DIRETO (sem o offset 4096 da convenção DVP)
  - inteiros 16 bits SEM SINAL, escalados (o MES aplica nu_divisor p/ voltar à unidade)
  - comando: escreve D50 (1=iniciar 2=parar 3=ventoinha 4=zerar); o CLP zera após tratar

Nada de valores negativos nos registradores: Modbus word é sem sinal e o coletor lê como
unsigned. A taxa de aquecimento (que pode ser negativa) NÃO é registrador — a API deriva
da série de temperatura.

Uso:
  python mock_clp_forno.py           # porta 5030
  python mock_clp_forno.py 5031      # outra porta
"""
import asyncio, math, sys
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext
from pymodbus.server import StartAsyncTcpServer

HOST = "0.0.0.0"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5030

# ---------- parâmetros do modelo térmico ----------
DT = 0.05            # passo de parede (s)
SPEED = 20.0         # aceleração da simulação (20 s de forno por 1 s real)
T_AMB = 25.0         # °C
SETPOINT = 540.0     # °C — patamar do ensaio
P_MAX = 3000.0       # W — potência das resistências
C_CAM = 9000.0       # J/K — massa térmica da câmara + refratário
K_LOSS = 3.2         # W/K — perdas para o ambiente
K_FAN = 1.5          # W/K — perdas extras com a ventoinha ligada
C_ESP = 900.0        # J/(kg·K) — calor específico da amostra (alumina)
H_AM = 30.0          # W/K — acoplamento câmara <-> corpo de prova
KP = 1 / 30.0        # duty por °C de erro (banda proporcional de 30 °C)
KI = 6e-4            # termo integral — zera o droop no patamar
I_MAX = 1 / KI       # anti-windup: mantém KI*integral dentro de [0,1]
TOL_PATAMAR = 5.0    # °C

# ---------- parâmetros da balança / perda ao fogo ----------
M_INICIAL = 500.0    # g — massa inicial do corpo de prova
FRAC_VOLATIL = 0.08  # 8% da massa é volátil (umidade + ligante) e queima no ensaio
EA = 100_000.0       # J/mol — energia de ativação da calcinação
R_GAS = 8.314        # J/(mol·K)
A_ARR = 11_400.0     # 1/s — fator pré-exponencial (calibra p/ reagir entre ~400 e 540 °C)

# ---- datastore (zero_mode: endereço == índice) ----
slave = ModbusSlaveContext(
    hr=ModbusSequentialDataBlock(0, [0] * 512),
    co=ModbusSequentialDataBlock(0, [0] * 512),
    di=ModbusSequentialDataBlock(0, [0] * 512),
    ir=ModbusSequentialDataBlock(0, [0] * 512),
)
context = ModbusServerContext(slaves=slave, single=True)


def set_word(dn, v):
    """Grava um inteiro sem sinal, saturando em 0..65535 (word Modbus)."""
    slave.setValues(3, dn, [max(0, min(int(round(v)), 65535))])


def get_word(dn):
    return int(slave.getValues(3, dn, 1)[0])


class Sim:
    tempo = 0.0
    temperatura = T_AMB
    temp_amostra = T_AMB
    massa = M_INICIAL       # g — massa atual na balança
    alpha = 0.0             # 0..1 — avanço da calcinação (fração do volátil já liberada)
    dmdt = 0.0              # g/s — taxa de perda de massa (vira "fumaça" no 3D)
    integ = 0.0
    duty = 0.0
    potencia = 0.0
    energia_kj = 0.0
    rodando = False
    ventoinha = False


sim = Sim()

# Massa volátil total (g) — o que pode ser perdido no ensaio inteiro.
M_VOLATIL = M_INICIAL * FRAC_VOLATIL


def _zerar():
    sim.tempo = 0.0
    sim.temperatura = T_AMB
    sim.temp_amostra = T_AMB
    sim.massa = M_INICIAL
    sim.alpha = 0.0
    sim.dmdt = 0.0
    sim.integ = 0.0
    sim.duty = 0.0
    sim.potencia = 0.0
    sim.energia_kj = 0.0
    sim.rodando = False
    sim.ventoinha = False


def _tratar_comando():
    """D50: 1=iniciar 2=parar 3=ventoinha(toggle) 4=zerar. Zera após tratar (handshake)."""
    cmd = get_word(50)
    if cmd == 0:
        return
    if cmd == 1:
        sim.rodando = True
    elif cmd == 2:
        sim.rodando = False
    elif cmd == 3:
        sim.ventoinha = not sim.ventoinha
    elif cmd == 4:
        _zerar()
    set_word(50, 0)


def _passo(dt):
    # ---- controle PI com anti-windup ----
    erro = SETPOINT - sim.temperatura
    if sim.rodando:
        sim.integ = max(0.0, min(sim.integ + erro * dt, I_MAX))
        sim.duty = max(0.0, min(KP * erro + KI * sim.integ, 1.0))
    else:
        sim.integ = 0.0
        sim.duty = 0.0
    sim.potencia = P_MAX * sim.duty

    # ---- balanço térmico ----
    massa_kg = sim.massa / 1000.0
    k = K_LOSS + (K_FAN if sim.ventoinha else 0.0)
    perdas = k * (sim.temperatura - T_AMB)
    q_am = H_AM * (sim.temperatura - sim.temp_amostra)
    sim.temperatura += (sim.potencia - perdas - q_am) * dt / C_CAM
    sim.temp_amostra += q_am * dt / (massa_kg * C_ESP)
    sim.energia_kj += sim.potencia * dt / 1000.0

    # ---- calcinação (Arrhenius): perda de massa do corpo de prova ----
    # d(alpha)/dt = A·exp(-Ea/RT)·(1-alpha)  -> sigmoide de perda ao fogo
    tk = sim.temp_amostra + 273.15
    kt = A_ARR * math.exp(-EA / (R_GAS * tk))
    dalpha = kt * (1.0 - sim.alpha) * dt
    dalpha = min(dalpha, 1.0 - sim.alpha)          # nunca passa de 100% do volátil
    sim.alpha += dalpha
    sim.dmdt = (M_VOLATIL * dalpha) / dt if dt > 0 else 0.0
    sim.massa = M_INICIAL - M_VOLATIL * sim.alpha

    sim.tempo += dt


def _publicar():
    patamar = sim.rodando and abs(SETPOINT - sim.temperatura) <= TOL_PATAMAR
    if sim.rodando:
        modo = 2 if patamar else 1
    else:
        modo = 3 if sim.temperatura > T_AMB + 2 else 0

    perda_pct = (M_INICIAL - sim.massa) / M_INICIAL * 100.0
    # fumaça 0..1000: taxa de perda normalizada (o 3D usa p/ dosar as partículas)
    fumaca = min(sim.dmdt / 0.05, 1.0) if sim.dmdt > 0 else 0.0

    set_word(0,  modo)                       # 0 idle 1 aquecendo 2 patamar 3 resfriando
    set_word(1,  1 if sim.rodando else 0)
    set_word(2,  1 if sim.ventoinha else 0)
    set_word(3,  1 if patamar else 0)
    set_word(10, sim.temperatura * 10)       # x10  -> °C
    set_word(12, sim.temp_amostra * 10)      # x10  -> °C
    set_word(14, SETPOINT * 10)              # x10  -> °C
    set_word(16, sim.potencia)               #      -> W
    set_word(18, sim.duty * 1000)            # x1000 -> 0..1
    set_word(20, sim.energia_kj)             #      -> kJ
    set_word(30, M_INICIAL * 10)             # x10  -> g  (peso inicial / tara da amostra)
    set_word(32, sim.massa * 10)             # x10  -> g  (peso atual na balança)
    set_word(34, perda_pct * 100)            # x100 -> %  (perda ao fogo)
    set_word(36, fumaca * 1000)              # x1000 -> 0..1 (taxa de liberação de voláteis)
    set_word(40, sim.tempo)                  #      -> s (tempo de ensaio)


async def updater():
    while True:
        _tratar_comando()
        _passo(DT * SPEED)
        _publicar()
        await asyncio.sleep(DT)


async def main():
    _zerar()
    _publicar()
    print(f"Mock CLP Forno Mufla — Modbus TCP em {HOST}:{PORT}")
    print(f"  setpoint {SETPOINT:.0f} °C · simulacao {SPEED:.0f}x · amostra {M_INICIAL:.0f} g")
    print("  D(n) -> holding register n direto | words sem sinal, escaladas")
    print("  Comando D50: 1=iniciar 2=parar 3=ventoinha 4=zerar")
    asyncio.create_task(updater())
    try:
        await StartAsyncTcpServer(context=context, address=(HOST, PORT))
    except OSError as e:
        print(f"ERRO ao abrir a porta {PORT}: {e}\nTente outra: python mock_clp_forno.py 5031")


if __name__ == "__main__":
    asyncio.run(main())
