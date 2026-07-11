"""
Bridge do Twin 3D — Modbus TCP  <->  HTTP (telemetria + comandos)

Faz a ponte entre o mock/CLP (Modbus TCP) e o navegador (three.js). Um poller lê a
máquina ~20x/s pra um estado em memória; o navegador consulta /telemetria e dispara
/comando/<acao>. Serve também a página twin3d.html.

Contrato HTTP (o MESMO que um cliente Unity/metaverso pode consumir no futuro):
  GET  /                      -> página 3D
  GET  /telemetria            -> JSON do estado atual (ver TELE / status abaixo)
  POST /comando/<acao>        -> escreve o coil do comando; acao em COMANDOS

Uso:
  1) python ../clp/mock_clp.py            (sobe o CLP virtual em 127.0.0.1:502)
  2) python bridge.py                     (sobe a ponte em http://127.0.0.1:8000)
  3) abra http://127.0.0.1:8000 no navegador
"""
import json, os, struct, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from pymodbus.client import ModbusTcpClient

MOCK_HOST, MOCK_PORT = "127.0.0.1", 502
SERVE_HOST, SERVE_PORT = "127.0.0.1", 8000
DBASE, MBASE = 0x1000, 0x0800  # D(n)->4096+n ; M(n)->2048+n

# Telemetria: nome -> endereço do holding register (todos REAL = 2 words)
TELE = {
    "deslocamento": 7106,  # D3010 mm
    "forca":        7108,  # D3012 N
    "tensao":       7096,  # D3000 MPa
    "alongamento":  7104,  # D3008 %
    "modulo":       7098,  # D3002 MPa
    "forca_max":    4814,  # D718  N (pico)
    "r2":           4124,  # D28
}
STATUS = {"rodando": 2, "ruptura": 31}          # coils (M)
COMANDOS = {                                     # acao -> M (coil a escrever)
    "iniciar_tracao": 9, "iniciar_flexao": 11,
    "subir": 5, "descer": 6, "parar": 7, "zerar": 100,
}

_lock = threading.Lock()
_client = ModbusTcpClient(MOCK_HOST, port=MOCK_PORT, timeout=1)
STATE = {"conectado": False}


def _read_real(addr):
    r = _client.read_holding_registers(address=addr, count=2)
    if r.isError():
        return None
    lo, hi = r.registers
    return round(struct.unpack("<f", struct.pack("<HH", lo, hi))[0], 4)


def _read_coil(m):
    r = _client.read_coils(address=MBASE + m, count=1)
    if r.isError():
        return None
    return bool(r.bits[0])


def _poller():
    while True:
        with _lock:
            try:
                if not _client.connected:
                    _client.connect()
                data = {name: _read_real(addr) for name, addr in TELE.items()}
                for name, m in STATUS.items():
                    data[name] = _read_coil(m)
                data["conectado"] = True
                STATE.clear(); STATE.update(data)
            except Exception as e:
                STATE.clear(); STATE.update({"conectado": False, "erro": str(e)[:80]})
        time.sleep(0.05)


def _enviar_comando(acao):
    m = COMANDOS.get(acao)
    if m is None:
        return False
    with _lock:
        try:
            if not _client.connected:
                _client.connect()
            _client.write_coil(MBASE + m, True)
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
        pass  # silencia o log de acesso


if __name__ == "__main__":
    threading.Thread(target=_poller, daemon=True).start()
    srv = ThreadingHTTPServer((SERVE_HOST, SERVE_PORT), Handler)
    srv.daemon_threads = True
    print(f"Twin 3D bridge  ->  http://{SERVE_HOST}:{SERVE_PORT}")
    print(f"  lendo o CLP em {MOCK_HOST}:{MOCK_PORT} (rode o mock_clp.py antes)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nencerrando bridge.")
