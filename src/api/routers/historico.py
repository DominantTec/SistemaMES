from datetime import datetime
from fastapi import APIRouter, HTTPException, Query

from api.services.queries import get_historico_data

router = APIRouter(prefix="/api/historico", tags=["historico"])


@router.get("")
def get_historico(
    data_inicio: str = Query(..., description="ISO datetime, ex: 2024-01-15T00:00"),
    data_fim:    str = Query(..., description="ISO datetime, ex: 2024-01-15T23:59"),
):
    """Métricas históricas para o período solicitado."""
    try:
        dt_inicio = datetime.fromisoformat(data_inicio)
        dt_fim    = datetime.fromisoformat(data_fim)
    except ValueError:
        raise HTTPException(status_code=422, detail="Formato de data inválido. Use ISO 8601.")

    if dt_fim <= dt_inicio:
        raise HTTPException(status_code=422, detail="data_fim deve ser posterior a data_inicio.")

    return get_historico_data(dt_inicio, dt_fim)
