import asyncio
import json

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from api.services.queries import (
    get_all_ordens,
    proximo_numero_op,
    create_ordem,
    update_ordem_status,
    delete_ordem,
    calcular_metas_op,
    recalcular_turno_ordens_ativas,
    ConflictError,
    STATUSES_VALIDOS,
)

router = APIRouter(prefix="/api/ordens", tags=["ordens"])


class CreateOrdemBody(BaseModel):
    numero_op: str
    linha_id: int
    peca: str
    peca_id: int = None
    quantidade: int
    prioridade: int = 0
    observacoes: str = ""


class UpdateStatusBody(BaseModel):
    status: str  # 'fila' | 'em_producao' | 'finalizado' | 'cancelado'


@router.get("")
def list_ordens():
    return get_all_ordens()


@router.get("/proximo-numero")
def next_number():
    return {"numero": proximo_numero_op()}


@router.get("/preview-metas")
def preview_metas(linha_id: int, quantidade: int, peca_id: int = None):
    """Retorna a distribuição de metas por turno para uma OP a ser criada."""
    return calcular_metas_op(linha_id, quantidade, peca_id)


@router.post("")
def create_ordem_endpoint(body: CreateOrdemBody):
    id_ordem = create_ordem(
        body.numero_op, body.linha_id, body.peca,
        body.quantidade,
        body.prioridade, body.observacoes,
        body.peca_id,
    )
    return {"id": id_ordem, "ok": True}


@router.patch("/{ordem_id}/status")
def update_status(ordem_id: int, body: UpdateStatusBody):
    if body.status not in STATUSES_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Status inválido: {body.status}")
    try:
        return update_ordem_status(ordem_id, body.status)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{ordem_id}")
def delete_ordem_endpoint(ordem_id: int):
    return delete_ordem(ordem_id)


@router.websocket("/ws")
async def ordens_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            try:
                recalcular_turno_ordens_ativas()
                data = get_all_ordens()
                await websocket.send_text(json.dumps(data, default=str))
            except WebSocketDisconnect:
                return
            except Exception:
                # Erro de DB — mantém conexão viva, tenta de novo no próximo tick
                pass
            await asyncio.sleep(2)
    except Exception:
        pass
