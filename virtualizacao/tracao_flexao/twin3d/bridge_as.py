"""
Bridge do Twin 3D — AS300 Simulator (Modbus TCP)  <->  HTTP

Igual ao bridge.py, mas aponta pro **CLP AS real rodando no simulador do ISPSoft**
(lógica ST de tração e flexão), em vez do mock. Contrato HTTP idêntico — o twin3d.html
e um cliente Unity futuro não percebem a diferença.

Mapa Modbus do AS (D(n) -> holding register n, porta 10002):
  D0 modo(0/1/2)  D1 rodando  D2 ruptura
  D10 desloc x100mm  D12 forca N  D14 tensao x10MPa  D16 along x100%
  D18 modulo MPa  D20 forca_max N  D22 R2 x1000
  D50 = comando de entrada (1=tracao 2=flexao 3=parar 4=zerar)

Uso:
  1) ISPSoft: AS300 Simulator em RUN com o programa ST (COMMGR driver AS300_SIM Running)
  2) python bridge_as.py                  (sobe a ponte em http://127.0.0.1:8000)
  3) abra http://127.0.0.1:8000 no navegador
"""
import json, os, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from pymodbus.client import ModbusTcpClient

CLP_HOST, CLP_PORT = "127.0.0.1", 10002   # AS300 Simulator (Fase 7 fisico: trocar IP:porta)
SERVE_HOST = os.environ.get("SERVE_HOST", "127.0.0.1")
# 8000 colide com a API do MES e 8010 é o twin do Forno Mufla: use 8011 para rodar tudo junto.
SERVE_PORT = int(os.environ.get("SERVE_PORT", "8000"))
SLAVE = 1

# nome do campo -> (endereco D, divisor de escala)
TELE = {
    "deslocamento": (10, 100.0),   # x100 mm
    "forca":        (12, 1.0),     # N
    "tensao":       (14, 10.0),    # x10 MPa
    "alongamento":  (16, 100.0),   # x100 %
    "modulo":       (18, 1.0),     # MPa
    "forca_max":    (20, 1.0),     # N
    "r2":           (22, 1000.0),  # x1000
}
BITS = {"rodando": 1, "ruptura": 2}        # D como flag 0/1
MODO = 0                                    # D0
CMD_REG = 50                                # D50
COMANDOS = {"iniciar_tracao": 1, "iniciar_flexao": 2, "parar": 3, "zerar": 4}

_lock = threading.Lock()
_client = ModbusTcpClient(CLP_HOST, port=CLP_PORT, timeout=1)
STATE = {"conectado": False}


def _poller():
    while True:
        with _lock:
            try:
                if not _client.connected:
                    _client.connect()
                rr = _client.read_holding_registers(address=0, count=23, slave=SLAVE)
                if rr.isError():
                    raise IOError("read_holding_registers erro")
                regs = rr.registers
                data = {name: round(regs[addr] / div, 4) for name, (addr, div) in TELE.items()}
                for name, addr in BITS.items():
                    data[name] = bool(regs[addr])
                data["modo"] = regs[MODO]        # 0 idle / 1 tracao / 2 flexao
                data["conectado"] = True
                STATE.clear(); STATE.update(data)
            except Exception as e:
                STATE.clear(); STATE.update({"conectado": False, "erro": str(e)[:80]})
        time.sleep(0.05)


def _enviar_comando(acao):
    v = COMANDOS.get(acao)
    if v is None:
        return False
    with _lock:
        try:
            if not _client.connected:
                _client.connect()
            _client.write_register(address=CMD_REG, value=v, slave=SLAVE)
            return True
        except Exception:
            return False


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "twin3d.html"),
                        encoding="utf-8").read()
            self._send(200, html, "text/html; charset=utf-8")
        elif path == "/telemetria":
            with _lock:
                data = dict(STATE)
            self._send(200, json.dumps(data))
        else:
            self._send(404, '{"erro":"nao encontrado"}')

    def do_POST(self):
        path = urlparse(self.path).path
        if path.startswith("/comando/"):
            acao = path.split("/comando/", 1)[1]
            ok = _enviar_comando(acao)
            self._send(200 if ok else 400, json.dumps({"ok": ok, "acao": acao}))
        else:
            self._send(404, '{"erro":"nao encontrado"}')

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    threading.Thread(target=_poller, daemon=True).start()
    srv = ThreadingHTTPServer((SERVE_HOST, SERVE_PORT), Handler)
    srv.daemon_threads = True
    print(f"Twin 3D bridge (AS)  ->  http://{SERVE_HOST}:{SERVE_PORT}")
    print(f"  lendo o CLP AS em {CLP_HOST}:{CLP_PORT} (AS300 Simulator em RUN)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nencerrando bridge.")
