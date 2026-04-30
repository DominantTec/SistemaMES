import asyncio
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from api.services.queries import (
    get_os_manutencao,
    create_os_manual,
    iniciar_atendimento_os,
    concluir_os,
    cancelar_os,
    get_manutencao_stats,
    get_manutentores_ihm,
    detectar_os_manutencao_throttled,
)

router = APIRouter(prefix="/api/manutencao", tags=["manutencao"])


class CreateOSBody(BaseModel):
    id_ihm: int
    nome_ihm: Optional[str] = ""
    id_linha: Optional[int] = None
    nome_linha: Optional[str] = ""
    motivo_abertura: Optional[str] = "Chamado manual"
    manutentor: Optional[str] = ""


class IniciarBody(BaseModel):
    manutentor: Optional[str] = ""


class ConcluirBody(BaseModel):
    problema: Optional[str] = ""
    solucao: Optional[str] = ""
    manutentor: Optional[str] = ""


class CancelarBody(BaseModel):
    motivo: Optional[str] = ""


@router.get("")
def list_os(
    status:     Optional[str] = None,
    linha_id:   Optional[int] = None,
    maquina_id: Optional[int] = None,
    limite:     int = 200,
):
    return get_os_manutencao(status=status, linha_id=linha_id,
                              maquina_id=maquina_id, limite=limite)


@router.get("/stats")
def manutencao_stats():
    return get_manutencao_stats()


@router.get("/manutentores/{ihm_id}")
def manutentores(ihm_id: int):
    return get_manutentores_ihm(ihm_id)


@router.post("")
def create_os(body: CreateOSBody):
    id_os = create_os_manual(body.model_dump())
    return {"id_os": id_os, "ok": True}


@router.patch("/{os_id}/iniciar")
def iniciar(os_id: int, body: IniciarBody):
    iniciar_atendimento_os(os_id, body.manutentor or "")
    return {"ok": True}


@router.patch("/{os_id}/concluir")
def concluir(os_id: int, body: ConcluirBody):
    concluir_os(os_id, body.problema or "", body.solucao or "", body.manutentor or "")
    return {"ok": True}


@router.patch("/{os_id}/cancelar")
def cancelar(os_id: int, body: CancelarBody):
    cancelar_os(os_id, body.motivo or "")
    return {"ok": True}


@router.websocket("/ws")
async def manutencao_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            detectar_os_manutencao_throttled()
            data = {
                "os_list": get_os_manutencao(limite=200),
                "stats":   get_manutencao_stats(),
            }
            await websocket.send_json(data)
            await asyncio.sleep(4)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
