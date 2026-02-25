from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional
from services.db import run_query

app = FastAPI(title="PCP API")

# =========================
# CORS (essencial pro front)
# =========================
# Em dev, deixa liberado. Em prod, restrinja para o domínio do front.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # DEV: libera tudo
    allow_credentials=False,      # se usar cookies/auth, mude pra True e não use "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Helpers
# =========================
def build_topbar() -> dict:
    return {
        "title": "Monitoramento de Chão de Fábrica",
        "oeeGlobal": 10.4,
        "maquinasAtivas": 28,
        "maquinasTotal": 32,
        "dateTimeText": datetime.now().strftime("%d/%m/%Y - %H:%M:%S"),
        "userInitials": "BG",
    }

def get_machine_timeline(machine_id: int, data_inicio=None, data_fim=None):
    """Retorna a linha do tempo de uma IHM filtrada no tempo ou não."""
    if not data_inicio or not data_fim:
        df_registradores = run_query("""
            SELECT * FROM tb_log_registrador
            WHERE id_ihm = :id
        """, {'id': machine_id})
    else:
        df_registradores = run_query("""
            SELECT * FROM tb_log_registrador
            WHERE id_ihm = :id
            AND dt_created_at >= :data_inicio
            AND dt_created_at <= :data_fim
        """, {'id': machine_id, 'data_inicio': data_inicio, 'data_fim': data_fim})

    df_ihms = run_query("""
        SELECT
            id_ihm,
            tx_name
        FROM tb_ihm
    """)

    df_depara_registradores = run_query("""
        SELECT
            id_registrador,
            tx_descricao
        FROM tb_registrador
    """)

    if len(df_registradores) > 2:
        df_registradores = df_registradores.merge(df_ihms, how='left', on='id_ihm')
        df_registradores = df_registradores.merge(df_depara_registradores, how='left', on='id_registrador')
        df_registradores = df_registradores[['tx_name', 'tx_descricao', 'dt_created_at', 'nu_valor_bruto']]

        del df_ihms, df_depara_registradores

        df_registradores = df_registradores.pivot_table(
            index=['tx_name', 'dt_created_at'],
            columns='tx_descricao',
            values='nu_valor_bruto',
            aggfunc='first'
        ).reset_index()

        df_registradores = df_registradores.sort_values('dt_created_at')
        df_registradores.reset_index(drop=True, inplace=True)

        depara_status_maquina = {
            0: 'Parada',
            1: 'Passar Padrão',
            49: 'Produzindo',
            4: 'Limpeza',
            51: 'Aguardando Manutentor',
            52: 'Máquina em manutenção',
            50: 'Maquina Liberada',
            53: 'Alteração de Parâmetros',
        }

        # Observação: essa coluna só existirá se existir um registrador com tx_descricao == "status_maquina"
        if 'status_maquina' in df_registradores.columns:
            df_registradores['status_maquina'] = df_registradores['status_maquina'].map(depara_status_maquina)

    return df_registradores

# =========================
# HTTP Endpoints
# =========================
@app.get("/health")
def health():
    return {"ok": True, "now": datetime.now().isoformat()}

@app.get("/api/dashboard/topbar")
def topbar():
    return build_topbar()

@app.get("/api/lines")
def get_lines():
    df = run_query("""
        SELECT id_linha_producao AS id, tx_name AS name
        FROM dbo.tb_linha_producao
        ORDER BY id_linha_producao
    """)
    return df.to_dict(orient="records")

@app.get("/api/lines/{line_id}/machines")
def get_machines_by_line(line_id: int):
    df = run_query("""
        SELECT id_ihm AS id, tx_name AS name
        FROM dbo.tb_ihm
        WHERE id_linha_producao = :line_id
        ORDER BY id_ihm
    """, {"line_id": line_id})
    return df.to_dict(orient="records")

# Timeline via HTTP (útil para carga inicial e/ou debug)
@app.get("/api/machines/{machine_id}/timeline")
def api_machine_timeline(
    machine_id: int,
    data_inicio: Optional[str] = Query(default=None),
    data_fim: Optional[str] = Query(default=None),
):
    df = get_machine_timeline(machine_id, data_inicio=data_inicio, data_fim=data_fim)
    # Se df vier vazio/pequeno, ainda assim devolve o que tiver
    try:
        return df.to_dict(orient="records")
    except Exception:
        # Caso run_query não retorne DataFrame em algum cenário
        return df

# =========================
# WebSocket
# =========================
@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            payload = {"type": "topbar", "data": build_topbar()}
            await websocket.send_json(payload)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass

# WebSocket em "tempo real" para timeline da máquina
# (na prática: polling no banco e push no socket; sem refresh de tela)
@app.websocket("/ws/machines/{machine_id}/timeline")
async def ws_machine_timeline(websocket: WebSocket, machine_id: int):
    await websocket.accept()
    try:
        while True:
            df = get_machine_timeline(machine_id)
            data = df.to_dict(orient="records") if hasattr(df, "to_dict") else df
            await websocket.send_json({"type": "machine_timeline", "machineId": machine_id, "data": data})
            await asyncio.sleep(1)  # intervalo de atualização (mantido simples por enquanto)
    except WebSocketDisconnect:
        pass