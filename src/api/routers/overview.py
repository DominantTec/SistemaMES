import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.services.queries import get_overview_data

router = APIRouter(prefix="/api/overview", tags=["overview"])


@router.get("")
def get_overview():
    """Snapshot atual da visão geral (HTTP)."""
    return get_overview_data()


@router.websocket("/ws")
async def ws_overview(websocket: WebSocket):
    """Stream em tempo real da visão geral (WebSocket — atualiza a cada 2s)."""
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(get_overview_data())
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass