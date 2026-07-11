"""
Leitor dos resultados do ensaio via Modbus TCP — referência de decodificação pro MES.

Uso:
  python ler_resultados.py                 # só lê e mostra os resultados
  python ler_resultados.py iniciar         # manda M9 (inicia tração) e lê
  python ler_resultados.py parar | zera    # outros comandos
  (porta opcional no fim: python ler_resultados.py iniciar 5020)
"""
import sys, struct
from pymodbus.client import ModbusTcpClient

DBASE, MBASE = 0x1000, 0x0800
cmd  = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].isdigit() else None
port = int([a for a in sys.argv[1:] if a.isdigit()][0]) if any(a.isdigit() for a in sys.argv[1:]) else 502

c = ModbusTcpClient("127.0.0.1", port=port, timeout=3)
if not c.connect():
    print(f"Não conectou em 127.0.0.1:{port} — o mock_clp.py está rodando?"); sys.exit(1)

def rreal(dn):
    rr = c.read_holding_registers(address=DBASE + dn, count=2)
    lo, hi = rr.registers
    return struct.unpack("<f", struct.pack("<HH", lo, hi))[0]

def rword(dn):
    return c.read_holding_registers(address=DBASE + dn, count=1).registers[0]

def rcoil(mn):
    return bool(c.read_coils(address=MBASE + mn, count=1).bits[0])

if cmd == "iniciar": c.write_coil(MBASE + 9, True);   print("-> M9 (inicia tração) enviado")
if cmd == "parar":   c.write_coil(MBASE + 7, True);   print("-> M7 (parar) enviado")
if cmd == "zera":    c.write_coil(MBASE + 100, True); print("-> M100 (zera) enviado")

print("\n--- Estado ---")
print(f"  M2  rodando ...... {rcoil(2)}")
print(f"  M31 ruptura ...... {rcoil(31)}")
print("--- Telemetria (tração) ---")
print(f"  D600  Deslocamento ...... {rreal(600):8.3f} mm")
print(f"  D2000 Força ............. {rreal(2000):8.2f} N")
print(f"  D90   Força Atual (WORD)  {rword(90):8d}")
print(f"  D3000 Tensão ............ {rreal(3000):8.2f} MPa")
print(f"  D3006 Deformação ........ {rreal(3006):8.4f}")
print(f"  D3008 Alongamento ....... {rreal(3008):8.3f} %")
print(f"  D3002 Mód. Elasticidade . {rreal(3002):8.1f} MPa")
print(f"  D718  Força Máxima ...... {rreal(718):8.2f} N")
print(f"  D28   R² ................ {rreal(28):8.4f}")
c.close()
