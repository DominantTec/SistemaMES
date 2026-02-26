import asyncio
from typing import Optional
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from api.services.queries import get_machine_timeline

router = APIRouter(prefix="/api/machines", tags=["machines"])

@router.get("/{machine_id}/timeline")
def api_machine_timeline(
    machine_id: int,
    data_inicio: Optional[str] = Query(default=None),
    data_fim: Optional[str] = Query(default=None),
):
    df = get_machine_timeline(machine_id, data_inicio=data_inicio, data_fim=data_fim)
    try:
        return df.to_dict(orient="records")
    except Exception:
        return df

@router.websocket("/ws/{machine_id}/timeline")  # fica em /api/machines/ws/{id}/timeline
async def ws_machine_timeline(websocket: WebSocket, machine_id: int):
    await websocket.accept()
    try:
        while True:
            df = get_machine_timeline(machine_id)
            data = df.to_dict(orient="records") if hasattr(df, "to_dict") else df
            await websocket.send_json({"type": "machine_timeline", "machineId": machine_id, "data": data})
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass