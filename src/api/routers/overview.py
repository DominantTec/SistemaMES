import asyncio
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/overview", tags=["overview"])

# ---------------------------------------------------------------------------
# MOCK DATA — estrutura idêntica ao que o backend real vai entregar
# Quando os dados reais estiverem prontos, basta trocar as funções abaixo
# pelos calls reais em queries.py
# ---------------------------------------------------------------------------

def _build_overview_data() -> dict:
    """
    Retorna o payload completo da tela de Visão Geral.
    Estrutura:
      - topbar: KPIs globais + eventos recentes
      - turno_atual: turno em andamento
      - linhas: lista de linhas, cada uma com suas máquinas e métricas
    """
    return {
        "topbar": {
            "titulo": "Monitoramento de Chão de Fábrica",
            "oee_global": 78.4,
            "maquinas_ativas": 28,
            "maquinas_total": 32,
            "data_hora": datetime.now().strftime("%d/%m/%Y - %H:%M:%S"),
            "user_initials": "BG",
            "eventos_recentes": [
                {
                    "hora": "14:32",
                    "maquina": "CUSI_02",
                    "descricao": "Parada de setup iniciada"
                },
                {
                    "hora": "14:28",
                    "maquina": "MAQ_24",
                    "descricao": "Retorno de operação"
                },
                {
                    "hora": "14:15",
                    "maquina": "MAQ_26",
                    "descricao": "Falha de comunicação Driver 12"
                },
            ],
        },
        "turno_atual": {
            "nome": "T2",
            "encerra_em": "04:32h",
            "progresso_pct": 68,
        },
        "linhas": [
            {
                "id": 1,
                "nome": "LINHA 505",
                "meta_hora": 850,
                "realizado": 812,
                "realizado_pct": 95,
                "maquinas": [
                    {
                        "id": 1,
                        "nome": "CUSI_01",
                        "status": "Produzindo",
                        "op": "OP #9281",
                        "oee": 29.8,
                        "disponibilidade": 100.0,
                        "qualidade": 100.0,
                        "performance": 29.8,
                        "produzido": 386,
                        "meta": 597,
                    },
                    {
                        "id": 2,
                        "nome": "MAQ_34",
                        "status": "Produzindo",
                        "op": None,
                        "oee": 52.7,
                        "disponibilidade": 58.0,
                        "qualidade": 90.0,
                        "performance": 63.0,
                        "produzido": 371,
                        "meta": 554,
                    },
                    {
                        "id": 3,
                        "nome": "MAQ_26",
                        "status": "Produzindo",
                        "op": None,
                        "oee": 80.3,
                        "disponibilidade": 88.0,
                        "qualidade": 91.0,
                        "performance": 92.0,
                        "produzido": 568,
                        "meta": 600,
                    },
                    {
                        "id": 4,
                        "nome": "MAQ_03",
                        "status": "Produzindo",
                        "op": None,
                        "oee": 74.0,
                        "disponibilidade": 92.0,
                        "qualidade": 79.0,
                        "performance": 85.0,
                        "produzido": 498,
                        "meta": 530,
                    },
                ],
            },
            {
                "id": 2,
                "nome": "LINHA 504",
                "meta_hora": 1200,
                "realizado": 1150,
                "realizado_pct": 98,
                "maquinas": [
                    {
                        "id": 5,
                        "nome": "PMAQ_37",
                        "status": "Aguardando Manutentor",
                        "op": None,
                        "oee": 58.0,
                        "disponibilidade": 86.0,
                        "qualidade": 66.0,
                        "performance": 72.0,
                        "produzido": 517,
                        "meta": 626,
                    },
                    {
                        "id": 6,
                        "nome": "MAQ_10",
                        "status": "Parada",
                        "op": None,
                        "oee": 16.2,
                        "disponibilidade": 17.0,
                        "qualidade": 90.0,
                        "performance": 19.0,
                        "produzido": 178,
                        "meta": 434,
                    },
                    {
                        "id": 7,
                        "nome": "MAQ_08",
                        "status": "Produzindo",
                        "op": None,
                        "oee": 51.0,
                        "disponibilidade": 59.0,
                        "qualidade": 85.0,
                        "performance": 65.0,
                        "produzido": 252,
                        "meta": 456,
                    },
                    {
                        "id": 8,
                        "nome": "MAQ_37",
                        "status": "Produzindo",
                        "op": None,
                        "oee": 73.8,
                        "disponibilidade": 80.0,
                        "qualidade": 91.0,
                        "performance": 83.0,
                        "produzido": 359,
                        "meta": 534,
                    },
                    {
                        "id": 9,
                        "nome": "MAQ_28",
                        "status": "Limpeza",
                        "op": None,
                        "oee": 40.8,
                        "disponibilidade": 64.0,
                        "qualidade": 88.0,
                        "performance": 52.0,
                        "produzido": 305,
                        "meta": 282,
                    },
                    {
                        "id": 10,
                        "nome": "MAQ_59",
                        "status": "Máquina em manutenção",
                        "op": None,
                        "oee": 28.6,
                        "disponibilidade": 53.0,
                        "qualidade": 53.0,
                        "performance": 40.0,
                        "produzido": 143,
                        "meta": 300,
                    },
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------

@router.get("")
def get_overview():
    """Snapshot atual da visão geral (HTTP)."""
    return _build_overview_data()


@router.websocket("/ws")
async def ws_overview(websocket: WebSocket):
    """Stream em tempo real da visão geral (WebSocket — atualiza a cada 2s)."""
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(_build_overview_data())
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass