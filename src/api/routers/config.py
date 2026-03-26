from typing import List
from fastapi import APIRouter
from pydantic import BaseModel

from api.services.queries import (
    get_all_machines, get_machine_config_data, update_machine_config,
    get_overview_turno, get_line_shifts, update_line_shifts, get_lines_df,
    update_producao_teorica, calcular_metas_op,
)

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/machines")
def list_machines():
    """Lista todas as máquinas cadastradas."""
    return get_all_machines()


@router.get("/machines/{machine_id}")
def get_config(machine_id: int):
    """Configuração completa de uma máquina."""
    return get_machine_config_data(machine_id)


class DiaCalendario(BaseModel):
    dia: str
    nome: str = ""
    inicio: str
    fim: str
    ativo: bool


class MachineConfigUpdate(BaseModel):
    meta: int
    peca: str
    producao_teorica: int = 0


@router.get("/turno/atual")
def turno_atual():
    """Retorna informações do turno em andamento para a sidebar."""
    return get_overview_turno()


@router.put("/machines/{machine_id}")
def save_config(machine_id: int, body: MachineConfigUpdate):
    """Salva meta, peça e produção teórica de uma máquina."""
    update_producao_teorica(machine_id, body.producao_teorica)
    return update_machine_config(machine_id, body.meta, body.peca)


@router.get("/lines/{line_id}/producao-teorica")
def get_line_producao_teorica(line_id: int):
    """Retorna a soma da produção teórica e preview de metas para uma linha."""
    from api.services.queries import get_producao_teorica_linha
    total = get_producao_teorica_linha(line_id)
    return {"producao_teorica_linha": total}


@router.get("/lines")
def list_lines():
    """Lista todas as linhas de produção."""
    df = get_lines_df()
    return [{"id": int(r["id_linha_producao"]), "nome": r["tx_name"]} for _, r in df.iterrows()]


@router.get("/lines/{line_id}/turnos")
def get_line_turnos(line_id: int):
    """Retorna o calendário de turnos de uma linha."""
    return get_line_shifts(line_id)


@router.put("/lines/{line_id}/turnos")
def save_line_turnos(line_id: int, body: list[DiaCalendario]):
    """Salva o calendário de turnos de uma linha."""
    return update_line_shifts(line_id, [d.model_dump() for d in body])
