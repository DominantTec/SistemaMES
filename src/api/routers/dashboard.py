import asyncio
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

def build_topbar() -> dict:
    return {
        "title": "Monitoramento de Chão de Fábrica",
        "oeeGlobal": 10.4,
        "maquinasAtivas": 28,
        "maquinasTotal": 32,
        "dateTimeText": datetime.now().strftime("%d/%m/%Y - %H:%M:%S"),
        "userInitials": "BG",
    }

@router.get("/topbar")
def topbar():
    return build_topbar()

@router.websocket("/ws")  # fica em /api/dashboard/ws
async def ws_dashboard(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json({"type": "topbar", "data": build_topbar()})
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass