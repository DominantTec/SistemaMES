from services.db import run_query
from typing import List, Dict, Any
import streamlit as st


@st.cache_data(ttl=10)
def get_active_lines() -> List[Dict[str, Any]]:
    return run_query("""
        SELECT id, nome
        FROM linhas_producao
        ORDER BY id
    """)


@st.cache_data(ttl=10)
def get_active_machines(line_id: int) -> List[Dict[str, Any]]:
    return run_query("""
        SELECT id, nome_maquina
        FROM ihms
        WHERE id_linha_producao = :id
        ORDER BY id
    """, {"id": line_id})


@st.cache_data(ttl=2)
def get_metrics_machine(machine_id: int) -> Dict[str, Any]:
    rows = run_query("""
        SELECT TOP 1
            status_maquina,
            meta,
            produzido,
            reprovado,
            total_produzido,
            operador,
            manutentor,
            datahora
        FROM maqteste_status_geral
        WHERE id_ihm = :id
        ORDER BY datahora DESC
    """, {"id": machine_id})

    if len(rows) == 0:
        return {
            "status_maquina": "sem status",
            "meta": "--",
            "produzido": 0,
            "reprovado": 0,
            "total_produzido": 0,
            "operador": "--",
            "manutentor": "--",
        }

    return rows.loc[0].to_dict()
