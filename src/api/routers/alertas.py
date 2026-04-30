import asyncio
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from api.services.queries import (
    get_alertas,
    get_alertas_stats,
    reconhecer_alerta,
    resolver_alerta,
    get_alertas_config,
    save_alerta_config,
    delete_alerta_config,
    toggle_alerta_config,
    detectar_alertas_throttled,
)

router = APIRouter(prefix="/api/alertas", tags=["alertas"])


class ReconhecerBody(BaseModel):
    reconhecido_por: str = "Operador"


class ResolverBody(BaseModel):
    resolucao: Optional[str] = None


class AlertaConfigBody(BaseModel):
    id: Optional[int] = None
    tipo: str
    nome: str
    descricao: Optional[str] = ""
    limiar: float
    severidade: str = "aviso"
    id_linha: Optional[int] = None
    ativo: bool = True


@router.get("")
def list_alertas(
    status:     Optional[str] = None,
    severidade: Optional[str] = None,
    linha_id:   Optional[int] = None,
    tipo:       Optional[str] = None,
    limite:     int = 200,
):
    return get_alertas(status=status, severidade=severidade,
                       linha_id=linha_id, tipo=tipo, limite=limite)


@router.get("/stats")
def alertas_stats():
    return get_alertas_stats()


@router.patch("/{alerta_id}/reconhecer")
def reconhecer(alerta_id: int, body: ReconhecerBody):
    reconhecer_alerta(alerta_id, body.reconhecido_por)
    return {"ok": True}


@router.patch("/{alerta_id}/resolver")
def resolver(alerta_id: int, body: ResolverBody):
    resolver_alerta(alerta_id, body.resolucao)
    return {"ok": True}


@router.get("/config")
def list_config():
    return get_alertas_config()


@router.post("/config")
def create_config(body: AlertaConfigBody):
    id_cfg = save_alerta_config(body.model_dump())
    return {"id": id_cfg, "ok": True}


@router.put("/config/{config_id}")
def update_config(config_id: int, body: AlertaConfigBody):
    save_alerta_config({**body.model_dump(), "id": config_id})
    return {"ok": True}


@router.delete("/config/{config_id}")
def delete_config(config_id: int):
    delete_alerta_config(config_id)
    return {"ok": True}


@router.patch("/config/{config_id}/toggle")
def toggle_config(config_id: int, ativo: bool):
    toggle_alerta_config(config_id, ativo)
    return {"ok": True}


@router.websocket("/ws")
async def alertas_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            detectar_alertas_throttled()
            data = {
                "alertas": get_alertas(limite=200),
                "stats":   get_alertas_stats(),
            }
            await websocket.send_json(data)
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
