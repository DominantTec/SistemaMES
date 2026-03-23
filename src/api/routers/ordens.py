import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from api.services.queries import (
    get_all_ordens,
    proximo_numero_op,
    create_ordem,
    update_ordem_status,
    delete_ordem,
)

router = APIRouter(prefix="/api/ordens", tags=["ordens"])


class CreateOrdemBody(BaseModel):
    numero_op: str
    linha_id: int
    peca: str
    quantidade: int
    meta_hora: int
    prioridade: int = 0
    observacoes: str = ""


class UpdateStatusBody(BaseModel):
    status: str  # 'fila' | 'em_producao' | 'finalizado'


@router.get("")
def list_ordens():
    return get_all_ordens()


@router.get("/proximo-numero")
def next_number():
    return {"numero": proximo_numero_op()}


@router.post("")
def create_ordem_endpoint(body: CreateOrdemBody):
    id_ordem = create_ordem(
        body.numero_op, body.linha_id, body.peca,
        body.quantidade, body.meta_hora,
        body.prioridade, body.observacoes,
    )
    return {"id": id_ordem, "ok": True}


@router.patch("/{ordem_id}/status")
def update_status(ordem_id: int, body: UpdateStatusBody):
    return update_ordem_status(ordem_id, body.status)


@router.delete("/{ordem_id}")
def delete_ordem_endpoint(ordem_id: int):
    return delete_ordem(ordem_id)


@router.websocket("/ws")
async def ordens_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = get_all_ordens()
            await websocket.send_text(json.dumps(data, default=str))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
