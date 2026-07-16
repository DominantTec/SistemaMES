"""
Bridge do Twin 3D — Forno Mufla:  Modbus TCP <-> HTTP (telemetria + comandos)

Ponte FINA: não tem física nenhuma. A simulação inteira mora no mock Modbus
(../clp/mock_clp_forno.py), que é a ÚNICA fonte de verdade — o coletor do MES lê
o mesmo servidor Modbus, então o 3D e os dashboards nunca divergem.

  navegador (three.js) ──HTTP──► bridge.py ──Modbus──► mock_clp_forno.py ◄──Modbus── coletor MES
     twin3d.html         telemetria/comando   poller 20Hz      :5030                    (docker)

Contrato HTTP (inalterado — o front não muda):
  GET  /                 -> página 3D
  GET  /telemetria       -> JSON do estado atual
  POST /comando/<acao>   -> escreve D50 no CLP; acao em COMANDOS

Uso:
  1) python ../clp/mock_clp_forno.py    (CLP virtual em :5030)
  2) python bridge.py                   (ponte em http://127.0.0.1:8010)
"""
import json, os, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from pymodbus.client import ModbusTcpClient

CLP_HOST = os.environ.get("CLP_HOST", "127.0.0.1")
CLP_PORT = int(os.environ.get("CLP_PORT", "5030"))
SERVE_HOST = os.environ.get("SERVE_HOST", "127.0.0.1")
# 8010 = forno. A API do MES ocupa a 8000 e o twin da Tração usa 8011 (ver
# ../../tracao_flexao/twin3d/bridge_as.py) — os três rodam juntos sem colidir.
SERVE_PORT = int(os.environ.get("SERVE_PORT", "8010"))

T_AMB = 25.0
C_ESP = 900.0        # J/(kg·K) — mesmo calor específico do mock, p/ derivar Q absorvido

# nome -> (endereço D, divisor de escala)
TELE = {
    "modo":            (0,  1),
    "rodando":         (1,  1),
    "ventoinha":       (2,  1),
    "patamar":         (3,  1),
    "temperatura":     (10, 10),
    "temp_amostra":    (12, 10),
    "setpoint":        (14, 10),
    "potencia":        (16, 1),
    "duty":            (18, 1000),
    "energia_kj":      (20, 1),
    "peso_inicial_g":  (30, 10),
    "peso_atual_g":    (32, 10),
    "perda_massa_pct": (34, 100),
    "fumaca":          (36, 1000),
    "tempo":           (40, 1),
}
COMANDOS = {"iniciar": 1, "parar": 2, "ventoinha": 3, "zerar": 4}   # valor escrito em D50
CMD_ADDR = 50

_lock = threading.Lock()
_client = ModbusTcpClient(CLP_HOST, port=CLP_PORT, timeout=1)
STATE = {"conectado": False}
_ultimo = {"t": None, "temp": None}   # p/ derivar a taxa (°C/min)


def _poller():
    while True:
        with _lock:
            try:
                if not _client.connected:
                    _client.connect()
                # bloco único 0..40 — uma leitura por ciclo em vez de 15
                r = _client.read_holding_registers(address=0, count=41)
                if r.isError():
                    raise IOError("leitura Modbus falhou")
                regs = r.registers

                data = {}
                for nome, (addr, div) in TELE.items():
                    data[nome] = round(regs[addr] / div, 4) if div != 1 else regs[addr]
                for b in ("rodando", "ventoinha", "patamar"):
                    data[b] = bool(data[b])

                # Derivados (não ocupam registrador):
                massa_kg = data["peso_atual_g"] / 1000.0
                data["q_amostra_kj"] = round(
                    massa_kg * C_ESP * (data["temp_amostra"] - T_AMB) / 1000.0, 3)

                # taxa °C/min a partir de duas leituras (o registrador seria negativo às vezes,
                # e word Modbus é sem sinal — por isso a taxa é derivada aqui)
                t, temp = data["tempo"], data["temperatura"]
                if _ultimo["t"] is not None and t > _ultimo["t"]:
                    data["taxa"] = round((temp - _ultimo["temp"]) / (t - _ultimo["t"]) * 60.0, 2)
                else:
                    data["taxa"] = 0.0
                if _ultimo["t"] is None or t - _ultimo["t"] >= 5 or t < _ultimo["t"]:
                    _ultimo["t"], _ultimo["temp"] = t, temp

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
            _client.write_register(CMD_ADDR, v)
            return True
        except Exception:
            return False


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")   # edições no twin3d.html aparecem no F5
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
    print(f"Forno Mufla — twin 3D  ->  http://{SERVE_HOST}:{SERVE_PORT}")
    print(f"  lendo o CLP em {CLP_HOST}:{CLP_PORT} (rode o mock_clp_forno.py antes)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nencerrando bridge.")
