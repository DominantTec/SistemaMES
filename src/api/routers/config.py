from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

from fastapi import HTTPException

from api.services.queries import (
    get_all_machines, get_machine_config_data, update_machine_config,
    get_overview_turno, get_line_shifts, update_line_shifts, get_lines_df,
    update_producao_teorica, calcular_metas_op,
    get_pecas_by_linha, create_peca, delete_peca,
    get_rota_peca, update_rota_peca,
    get_machines_by_line_df, update_machine_tipo,
    get_historico_turnos, get_proximos_turnos,
    abrir_turno_manual, fechar_turno_manual,
    link_modelo_to_linhas,
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
    id_modelo: Optional[int] = None
    dia: str
    nome: str = ""
    inicio: str
    fim: str
    ativo: bool
    linha_ids: List[int] = []


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


@router.get("/lines/{line_id}/turnos/historico")
def get_turnos_historico(line_id: int, limit: int = 20):
    """Retorna o histórico de ocorrências de turno de uma linha."""
    return get_historico_turnos(line_id, limit)


@router.get("/lines/{line_id}/turnos/proximos")
def get_turnos_proximos(line_id: int):
    """Retorna os próximos turnos para gestão (em_andamento + agendados + últimos finalizados)."""
    return get_proximos_turnos(line_id)


@router.post("/turnos/{ocorrencia_id}/iniciar")
def iniciar_turno(ocorrencia_id: int):
    """Gerente inicia manualmente um turno agendado."""
    try:
        return abrir_turno_manual(ocorrencia_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/turnos/{ocorrencia_id}/finalizar")
def finalizar_turno(ocorrencia_id: int):
    """Gerente finaliza manualmente um turno em andamento."""
    try:
        return fechar_turno_manual(ocorrencia_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Vínculos N:N turno-modelo ↔ linhas ────────────────────────────────────────

class LinhasVinculadasUpdate(BaseModel):
    linha_ids: List[int]


@router.get("/turno-modelos/{modelo_id}/linhas")
def get_modelo_linhas(modelo_id: int):
    """Retorna os IDs das linhas vinculadas a um template de turno."""
    from api.services.queries._core import run_query as _rq, _ensure_schema as _es
    _es()
    df = _rq(
        "SELECT id_linha_producao FROM dbo.tb_turno_modelo_linha WHERE id_modelo = :mid",
        {"mid": modelo_id},
    )
    return {"linha_ids": [int(r["id_linha_producao"]) for _, r in df.iterrows()]}


@router.put("/turno-modelos/{modelo_id}/linhas")
def update_modelo_linhas(modelo_id: int, body: LinhasVinculadasUpdate):
    """Vincula um template de turno a múltiplas linhas (N:N)."""
    try:
        return link_modelo_to_linhas(modelo_id, body.linha_ids)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class PecaCreate(BaseModel):
    nome: str


class RotaStep(BaseModel):
    id_ihm: int
    producao_teorica: int = 0


class RotaUpdate(BaseModel):
    steps: list[RotaStep]


class MaquinaTipoUpdate(BaseModel):
    tipo: str


@router.put("/machines/{machine_id}/tipo")
def save_machine_tipo(machine_id: int, body: MaquinaTipoUpdate):
    """Atualiza o tipo da máquina (agrupa máquinas intercambiáveis)."""
    update_machine_tipo(machine_id, body.tipo)
    return {"ok": True}


@router.get("/lines/{line_id}/machines")
def get_line_machines(line_id: int):
    """Lista as máquinas de uma linha."""
    df = get_machines_by_line_df(line_id)
    return [
        {"id": int(r["id_ihm"]), "nome": r["tx_name"], "tipo_maquina": r["tx_tipo_maquina"]}
        for _, r in df.iterrows()
    ]


@router.get("/lines/{line_id}/pecas")
def list_pecas(line_id: int):
    return get_pecas_by_linha(line_id)


@router.post("/lines/{line_id}/pecas")
def add_peca(line_id: int, body: PecaCreate):
    peca_id = create_peca(line_id, body.nome)
    return {"id": peca_id, "nome": body.nome, "rota": []}


@router.delete("/pecas/{peca_id}")
def remove_peca(peca_id: int):
    delete_peca(peca_id)
    return {"ok": True}


@router.get("/pecas/{peca_id}/rota")
def get_peca_rota(peca_id: int):
    return get_rota_peca(peca_id)


@router.put("/pecas/{peca_id}/rota")
def save_peca_rota(peca_id: int, body: RotaUpdate):
    update_rota_peca(peca_id, [s.model_dump() for s in body.steps])
    return {"ok": True}
