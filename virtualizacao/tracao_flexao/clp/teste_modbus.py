"""
Teste rápido de leitura Modbus TCP do CLP virtual (Tração e Flexão).

Uso:
  1. Suba o simulador no COMMGR (driver Simulator -> Start).
  2. No ISPSoft, faça o download da lógica para o simulador e coloque em RUN.
  3. Rode:  python teste_modbus.py
     (opcional)  python teste_modbus.py 127.0.0.1 502 0 20

O objetivo é só provar que dá pra LER registradores de fora. Se aparecer uma lista
de numeros, o caminho Modbus esta aberto e podemos seguir pro mapa_registradores.md.
"""
import sys
from pymodbus.client import ModbusTcpClient

host  = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
port  = int(sys.argv[2]) if len(sys.argv) > 2 else 502
start = int(sys.argv[3]) if len(sys.argv) > 3 else 0
count = int(sys.argv[4]) if len(sys.argv) > 4 else 20

print(f"Conectando em {host}:{port} ...")
client = ModbusTcpClient(host, port=port, timeout=3)
if not client.connect():
    print("FALHOU ao conectar. O simulador (COMMGR) esta rodando e em RUN? A porta e 502?")
    sys.exit(1)

rr = client.read_holding_registers(address=start, count=count)
if rr.isError():
    print(f"Erro na leitura: {rr}")
    print("Dica: talvez esses enderecos nao existam. Tente outro 'start', ex.: python teste_modbus.py 127.0.0.1 502 4096 10")
else:
    print(f"OK! Holding registers {start}..{start+count-1}:")
    for i, v in enumerate(rr.registers):
        print(f"  addr {start+i:>5} = {v}")
client.close()
