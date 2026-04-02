from datetime import datetime
from fastapi import APIRouter, HTTPException, Query

from api.services.queries import (
    get_historico_data,
    get_historico_linha_detalhe,
    get_historico_maquina_detalhe,
    get_ordens_funil,
)

router = APIRouter(prefix="/api/historico", tags=["historico"])


def _parse_dates(data_inicio: str, data_fim: str):
    try:
        dt_inicio = datetime.fromisoformat(data_inicio)
        dt_fim    = datetime.fromisoformat(data_fim)
    except ValueError:
        raise HTTPException(status_code=422, detail="Formato de data inválido. Use ISO 8601.")
    if dt_fim <= dt_inicio:
        raise HTTPException(status_code=422, detail="data_fim deve ser posterior a data_inicio.")
    return dt_inicio, dt_fim


@router.get("")
def get_historico(
    data_inicio: str = Query(...),
    data_fim:    str = Query(...),
):
    """Métricas históricas consolidadas por linha para o período."""
    dt_inicio, dt_fim = _parse_dates(data_inicio, data_fim)
    return get_historico_data(dt_inicio, dt_fim)


@router.get("/ordens")
def get_funil_ordens(
    data_inicio: str = Query(...),
    data_fim:    str = Query(...),
):
    """Funil de ordens de produção no período."""
    dt_inicio, dt_fim = _parse_dates(data_inicio, data_fim)
    return get_ordens_funil(dt_inicio, dt_fim)


@router.get("/linha/{linha_id}")
def get_linha_detalhe(
    linha_id:    int,
    data_inicio: str = Query(...),
    data_fim:    str = Query(...),
):
    """Detalhe de uma linha de produção no período: OEE por máquina, produção hora a hora, turnos e ordens."""
    dt_inicio, dt_fim = _parse_dates(data_inicio, data_fim)
    result = get_historico_linha_detalhe(linha_id, dt_inicio, dt_fim)
    if not result:
        raise HTTPException(status_code=404, detail=f"Linha {linha_id} não encontrada.")
    return result


@router.get("/maquina/{maquina_id}")
def get_maquina_detalhe(
    maquina_id:  int,
    data_inicio: str = Query(...),
    data_fim:    str = Query(...),
):
    """Detalhe de uma máquina no período: OEE, produção hora a hora, pareto de paradas."""
    dt_inicio, dt_fim = _parse_dates(data_inicio, data_fim)
    result = get_historico_maquina_detalhe(maquina_id, dt_inicio, dt_fim)
    if not result:
        raise HTTPException(status_code=404, detail=f"Máquina {maquina_id} não encontrada.")
    return result
