from typing import List
from fastapi import APIRouter
from pydantic import BaseModel

from api.services.queries import get_all_machines, get_machine_config_data, update_machine_config, get_overview_turno

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
    calendario: List[DiaCalendario]


@router.get("/turno/atual")
def turno_atual():
    """Retorna informações do turno em andamento para a sidebar."""
    return get_overview_turno()


@router.put("/machines/{machine_id}")
def save_config(machine_id: int, body: MachineConfigUpdate):
    """Salva meta, peça e calendário de funcionamento."""
    return update_machine_config(
        machine_id,
        body.meta,
        body.peca,
        [d.model_dump() for d in body.calendario],
    )
