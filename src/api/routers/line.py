import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.services.queries import get_line_detail, get_lines_df

router = APIRouter(prefix="/api/lines", tags=["line-detail"])


@router.get("")
def list_lines():
    """Retorna todas as linhas de produção cadastradas."""
    df = get_lines_df()
    return df.rename(columns={"id_linha_producao": "id", "tx_name": "nome"}).to_dict(orient="records")


@router.get("/{line_id}/detail")
def get_line_detail_route(line_id: int):
    """Snapshot completo de uma linha de produção (HTTP)."""
    return get_line_detail(line_id)


@router.websocket("/{line_id}/ws")
async def ws_line_detail(websocket: WebSocket, line_id: int):
    """Stream em tempo real de uma linha (WebSocket — atualiza a cada 2s)."""
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(get_line_detail(line_id))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass