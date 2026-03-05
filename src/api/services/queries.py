from datetime import datetime
from typing import List, Dict, Any, Optional

from api.services.db import run_query, run_query_update


# =========================
# QUERIES / FUNÇÕES REUTILIZÁVEIS
# (NÃO COLOCAR ROTAS AQUI)
# =========================

def get_lines_df():
    df = run_query("""
        SELECT id_linha_producao, tx_name
        FROM dbo.tb_linha_producao
        ORDER BY id_linha_producao
    """)
    return df

def get_machines_by_line_df(line_id: int):
    df = run_query("""
        SELECT id_ihm, tx_name
        FROM dbo.tb_ihm
        WHERE id_linha_producao = :line_id
        ORDER BY id_ihm
    """, {"line_id": line_id})
    return df


def get_machine_timeline(machine_id: int, data_inicio: Optional[Any] = None, data_fim: Optional[Any] = None):
    """Retorna a linha do tempo de uma IHM filtrada no tempo ou não."""
    if not data_inicio or not data_fim:
        df_registradores = run_query("""
            SELECT * FROM tb_log_registrador
            WHERE id_ihm = :id
        """, {"id": machine_id})
    else:
        df_registradores = run_query("""
            SELECT * FROM tb_log_registrador
            WHERE id_ihm = :id
              AND dt_created_at >= :data_inicio
              AND dt_created_at <= :data_fim
        """, {"id": machine_id, "data_inicio": data_inicio, "data_fim": data_fim})

    df_ihms = run_query("""
        SELECT id_ihm, tx_name
        FROM tb_ihm
    """)

    df_depara_registradores = run_query("""
        SELECT id_registrador, tx_descricao
        FROM tb_registrador
    """)

    if len(df_registradores) > 2:
        df_registradores = df_registradores.merge(df_ihms, how="left", on="id_ihm")
        df_registradores = df_registradores.merge(df_depara_registradores, how="left", on="id_registrador")

        df_registradores = df_registradores[["tx_name", "tx_descricao", "dt_created_at", "nu_valor_bruto"]]
        del df_ihms, df_depara_registradores

        df_registradores = df_registradores.pivot_table(
            index=["tx_name", "dt_created_at"],
            columns="tx_descricao",
            values="nu_valor_bruto",
            aggfunc="first",
        ).reset_index()

        df_registradores = df_registradores.sort_values("dt_created_at")
        df_registradores.reset_index(drop=True, inplace=True)

        depara_status_maquina = {
            0: "Parada",
            1: "Passar Padrão",
            49: "Produzindo",
            4: "Limpeza",
            51: "Aguardando Manutentor",
            52: "Máquina em manutenção",
            50: "Maquina Liberada",
            53: "Alteração de Parâmetros",
        }

        if "status_maquina" in df_registradores.columns:
            df_registradores["status_maquina"] = df_registradores["status_maquina"].map(depara_status_maquina)

    return df_registradores


def get_machine_shifts(machine_id: int, data_inicio: Optional[Any] = None, data_fim: Optional[Any] = None):
    """Usando o id de uma IHM, retorna os turnos de uma linha de produção filtrado por data ou não."""
    if not data_inicio or not data_fim:
        df_funcionamento = run_query("""
            SELECT * FROM tb_turnos
            WHERE id_linha_producao = (SELECT id_linha_producao FROM tb_ihm WHERE id_ihm = :id)
        """, {"id": machine_id})
    else:
        df_funcionamento = run_query("""
            SELECT * FROM tb_turnos
            WHERE id_linha_producao = (SELECT id_linha_producao FROM tb_ihm WHERE id_ihm = :id)
              AND dt_inicio >= :data_inicio
              AND dt_fim <= :data_fim
        """, {"id": machine_id, "data_inicio": data_inicio, "data_fim": data_fim})

    df_ihms = run_query("""
        SELECT id_ihm, tx_name, id_linha_producao
        FROM tb_ihm
    """)

    df_funcionamento = df_funcionamento.merge(df_ihms, how="left", on="id_linha_producao")
    return df_funcionamento


def get_possible_pieces(machine_id: int) -> list:
    """Retorna as peças possiveis em uma determinada IHM."""
    try:
        resultado = run_query("""
            SELECT tx_peca
            FROM tb_depara_peca
            WHERE id_ihm = :id
        """, {"id": machine_id})

        if resultado["tx_peca"].to_list() == []:
            return ["PEÇA TEMP", "PEÇA 1", "SEM PEÇAS PARA DEPARA"]
        return resultado["tx_peca"].to_list()
    except Exception:
        return ["PEÇA TEMP", "PEÇA 1"]


def get_selected_piece(machine_id: int, data_ref: Optional[Any] = None) -> str:
    """Retorna a peça seleciona antes da data informada."""
    try:
        if not data_ref:
            cod_peca = run_query("""
                SELECT *
                FROM tb_log_registrador
                WHERE id_registrador = (
                    SELECT id_registrador
                    FROM tb_registrador
                    WHERE id_ihm = :id AND tx_descricao='modelo_peça'
                )
                ORDER BY dt_created_at DESC
            """, {"id": machine_id})["nu_valor_bruto"].tolist()[0]

            resultado = run_query("""
                SELECT tx_peca
                FROM tb_depara_peca
                WHERE id_ihm = :id AND nu_cod_peca = :nu_cod_peca
            """, {"id": machine_id, "nu_cod_peca": cod_peca})["tx_peca"].tolist()
        else:
            cod_peca = run_query("""
                SELECT *
                FROM tb_log_registrador
                WHERE id_registrador = (
                    SELECT id_registrador
                    FROM tb_registrador
                    WHERE id_ihm = :id AND tx_descricao='modelo_peça'
                )
                  AND dt_created_at <= :data
                ORDER BY dt_created_at DESC
            """, {"id": machine_id, "data": data_ref})["nu_valor_bruto"].tolist()[0]

            resultado = run_query("""
                SELECT tx_peca
                FROM tb_depara_peca
                WHERE id_ihm = :id AND nu_cod_peca = :nu_cod_peca
            """, {"id": machine_id, "nu_cod_peca": cod_peca})["tx_peca"].tolist()

        return "PEÇA TEMP" if resultado == [] else resultado[0]
    except Exception:
        return "PEÇA TEMP"


def get_meta(machine_id: int, data_ref: Optional[Any] = None) -> int:
    """Retorna a meta antes da data informada."""
    try:
        if not data_ref:
            resultado = run_query("""
                SELECT *
                FROM tb_log_registrador
                WHERE id_registrador = (
                    SELECT id_registrador
                    FROM tb_registrador
                    WHERE id_ihm = :id AND tx_descricao='meta'
                )
                ORDER BY dt_created_at DESC
            """, {"id": machine_id})
        else:
            resultado = run_query("""
                SELECT *
                FROM tb_log_registrador
                WHERE id_registrador = (
                    SELECT id_registrador
                    FROM tb_registrador
                    WHERE id_ihm = :id AND tx_descricao='meta'
                )
                  AND dt_created_at <= :data
                ORDER BY dt_created_at DESC
            """, {"id": machine_id, "data": data_ref})

        return int(resultado["nu_valor_bruto"].tolist()[0])
    except Exception:
        return 1


def get_meta_register(machine_id: int) -> int:
    """Retorna o registro referente a meta naquela IHM."""
    try:
        resultado = run_query("""
            SELECT nu_endereco
            FROM tb_registrador
            WHERE id_ihm = :id AND tx_descricao='meta'
        """, {"id": machine_id})

        return resultado["nu_endereco"].tolist()[0]
    except Exception:
        return -1


def get_metrics_machine(machine_id: int, data_inicio: Optional[Any] = None, data_fim: Optional[Any] = None) -> Dict[str, Any]:
    """Retorna as principais informações de uma IHM para um dado periodo de tempo."""
    try:
        df_registradores = get_machine_timeline(machine_id, data_inicio=data_inicio, data_fim=data_fim)
        df_shifts = get_machine_shifts(machine_id, data_inicio=data_inicio, data_fim=data_fim)

        first_register = df_registradores[df_registradores["dt_created_at"] == df_registradores["dt_created_at"].min()]
        last_register = df_registradores[df_registradores["dt_created_at"] == df_registradores["dt_created_at"].max()]

        status = last_register["status_maquina"].to_list()[0] if "status_maquina" in last_register.columns else "-"
        operador = last_register["operador"].to_list()[0] if "operador" in last_register.columns else "-"
        manutentor = last_register["manutentor"].to_list()[0] if "manutentor" in last_register.columns else "-"
        engenheiro = last_register["engenheiro"].to_list()[0] if "engenheiro" in last_register.columns else "-"

        lista_qtd_aprovado = []
        lista_qtd_reprovado = []
        lista_qtd_total = []
        lista_produzido = []
        lista_esperado = []

        status_antigo = ""
        inicio = None
        inicio_qtd_aprovado = None
        inicio_qtd_reprovado = None
        inicio_qtd_total = None
        inicio_teorico = None

        fim = None
        fim_qtd_aprovado = None
        fim_qtd_reprovado = None
        fim_qtd_total = None
        fim_teorico = None

        for _, row in df_registradores.iterrows():
            working_day = df_shifts[
                (df_shifts["dt_inicio"].dt.date == row["dt_created_at"].date()) &
                (df_shifts["id_ihm"] == machine_id)
            ]

            if working_day.empty:
                status_antigo = row.get("status_maquina", status_antigo)
                continue

            if status_antigo != "Produzindo" and row["status_maquina"] == "Produzindo":
                if row["dt_created_at"] < working_day["dt_fim"].to_list()[0]:
                    inicio = working_day["dt_inicio"].to_list()[0] if row["dt_created_at"] < working_day["dt_inicio"].to_list()[0] else row["dt_created_at"]
                    inicio_qtd_aprovado = row.get("produzido")
                    inicio_qtd_reprovado = row.get("reprovado")
                    inicio_qtd_total = row.get("total_produzido")
                    inicio_teorico = working_day["dt_inicio"].to_list()[0]

            elif (
                (status_antigo == "Produzindo" and row["status_maquina"] != "Produzindo") or
                (status_antigo == "Produzindo" and row["status_maquina"] == "Produzindo" and row["dt_created_at"] == last_register["dt_created_at"].to_list()[0])
            ):
                if row["dt_created_at"] > working_day["dt_inicio"].to_list()[0]:
                    fim = working_day["dt_fim"].to_list()[0] if row["dt_created_at"] > working_day["dt_fim"].to_list()[0] else row["dt_created_at"]
                    fim_qtd_aprovado = row.get("produzido")
                    fim_qtd_reprovado = row.get("reprovado")
                    fim_qtd_total = row.get("total_produzido")
                    fim_teorico = working_day["dt_fim"].to_list()[0]

            if inicio and fim:
                if inicio.day == fim.day:
                    if (inicio, fim) not in lista_produzido:
                        lista_produzido.append((inicio, fim))
                    if (inicio_teorico, fim_teorico) not in lista_esperado:
                        lista_esperado.append((inicio_teorico, fim_teorico))

                    lista_qtd_aprovado.append((inicio_qtd_aprovado, fim_qtd_aprovado))
                    lista_qtd_reprovado.append((inicio_qtd_reprovado, fim_qtd_reprovado))
                    lista_qtd_total.append((inicio_qtd_total, fim_qtd_total))

                inicio_qtd_aprovado = inicio_qtd_reprovado = inicio_qtd_total = None
                fim_qtd_aprovado = fim_qtd_reprovado = fim_qtd_total = None
                inicio = inicio_teorico = None
                fim = fim_teorico = None

            status_antigo = row["status_maquina"]

        tempo_produzido = sum([(b - a).total_seconds() for a, b in lista_produzido])
        tempo_programado = sum([(b - a).total_seconds() for a, b in lista_esperado])

        produzido = sum([(b - a) for a, b in lista_qtd_aprovado if a is not None and b is not None])
        reprovado = sum([(b - a) for a, b in lista_qtd_reprovado if a is not None and b is not None])
        total = sum([(b - a) for a, b in lista_qtd_total if a is not None and b is not None])

        disponibilidade = tempo_produzido / tempo_programado if tempo_programado else 0

        meta = (tempo_programado // 1) if tempo_programado else 1
        performance = (int(total) / meta) if meta else 0
        qualidade = (int(produzido) / int(total)) if total else 0

        oee = disponibilidade * performance * qualidade

        return {
            "status_maquina": status,
            "oee": round(100 * oee, 2),
            "disponibilidade": round(100 * disponibilidade, 2),
            "performance": round(100 * performance, 2),
            "qualidade": round(100 * qualidade, 2),
            "meta": meta,
            "produzido": produzido,
            "reprovado": reprovado,
            "total_produzido": total,
            "operador": operador,
            "manutentor": manutentor,
            "engenheiro": engenheiro,
        }
    except Exception:
        return {
            "status_maquina": "-",
            "oee": "-",
            "disponibilidade": "-",
            "performance": "-",
            "qualidade": "-",
            "meta": "-",
            "produzido": "-",
            "reprovado": "-",
            "total_produzido": "-",
            "operador": "-",
            "manutentor": "-",
            "engenheiro": "-",
        }


def get_alerts_ihm(id_ihm: int, data_inicio: Optional[Any] = None, data_fim: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Retorna os alertas de uma IHM para um dado periodo de tempo."""
    # TODO: implementar query real
    return [
        {"dt_created_at": "2024-01-01 08:00:00", "tx_descricao": "alerta_1", "nu_valor_bruto": 1},
        {"dt_created_at": "2024-01-01 09:00:00", "tx_descricao": "alerta_2", "nu_valor_bruto": 1},
        {"dt_created_at": "2024-01-01 10:00:00", "tx_descricao": "alerta_3", "nu_valor_bruto": 1},
    ]


# =========================
# VISÃO GERAL (MOCK)
# Substitua o corpo destas funções pelos dados reais quando estiver pronto.
# =========================

def get_overview_topbar() -> dict:
    """KPIs globais e eventos recentes para a topbar da Visão Geral."""
    return {
        "titulo": "Monitoramento de Chão de Fábrica",
        "oee_global": 78.4,
        "maquinas_ativas": 28,
        "maquinas_total": 32,
        "data_hora": datetime.now().strftime("%d/%m/%Y - %H:%M:%S"),
        "user_initials": "BG",
        "eventos_recentes": [
            {"hora": "14:32", "maquina": "CUSI_02", "descricao": "Parada de setup iniciada"},
            {"hora": "14:28", "maquina": "MAQ_24",  "descricao": "Retorno de operação"},
            {"hora": "14:15", "maquina": "MAQ_26",  "descricao": "Falha de comunicação Driver 12"},
        ],
    }


def get_overview_turno() -> dict:
    """Informações do turno atual."""
    return {
        "nome": "T2",
        "encerra_em": "04:32h",
        "progresso_pct": 68,
    }


def get_overview_linhas() -> list:
    """Lista de linhas de produção com suas máquinas e métricas."""
    return [
        {
            "id": 1,
            "nome": "LINHA 505",
            "meta_hora": 850,
            "realizado": 812,
            "realizado_pct": 95,
            "maquinas": [
                {
                    "id": 1, "nome": "CUSI_01", "status": "Produzindo", "op": "OP #9281",
                    "oee": 29.8, "disponibilidade": 100.0, "qualidade": 100.0, "performance": 29.8,
                    "produzido": 386, "meta": 597,
                },
                {
                    "id": 2, "nome": "MAQ_34", "status": "Produzindo", "op": None,
                    "oee": 52.7, "disponibilidade": 58.0, "qualidade": 90.0, "performance": 63.0,
                    "produzido": 371, "meta": 554,
                },
                {
                    "id": 3, "nome": "MAQ_26", "status": "Produzindo", "op": None,
                    "oee": 80.3, "disponibilidade": 88.0, "qualidade": 91.0, "performance": 92.0,
                    "produzido": 568, "meta": 600,
                },
                {
                    "id": 4, "nome": "MAQ_03", "status": "Produzindo", "op": None,
                    "oee": 74.0, "disponibilidade": 92.0, "qualidade": 79.0, "performance": 85.0,
                    "produzido": 498, "meta": 530,
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
                    "id": 5, "nome": "PMAQ_37", "status": "Aguardando Manutentor", "op": None,
                    "oee": 58.0, "disponibilidade": 86.0, "qualidade": 66.0, "performance": 72.0,
                    "produzido": 517, "meta": 626,
                },
                {
                    "id": 6, "nome": "MAQ_10", "status": "Parada", "op": None,
                    "oee": 16.2, "disponibilidade": 17.0, "qualidade": 90.0, "performance": 19.0,
                    "produzido": 178, "meta": 434,
                },
                {
                    "id": 7, "nome": "MAQ_08", "status": "Produzindo", "op": None,
                    "oee": 51.0, "disponibilidade": 59.0, "qualidade": 85.0, "performance": 65.0,
                    "produzido": 252, "meta": 456,
                },
                {
                    "id": 8, "nome": "MAQ_37", "status": "Produzindo", "op": None,
                    "oee": 73.8, "disponibilidade": 80.0, "qualidade": 91.0, "performance": 83.0,
                    "produzido": 359, "meta": 534,
                },
                {
                    "id": 9, "nome": "MAQ_28", "status": "Limpeza", "op": None,
                    "oee": 40.8, "disponibilidade": 64.0, "qualidade": 88.0, "performance": 52.0,
                    "produzido": 305, "meta": 282,
                },
                {
                    "id": 10, "nome": "MAQ_59", "status": "Máquina em manutenção", "op": None,
                    "oee": 28.6, "disponibilidade": 53.0, "qualidade": 53.0, "performance": 40.0,
                    "produzido": 143, "meta": 300,
                },
            ],
        },
    ]


def get_overview_data() -> dict:
    """Payload completo da tela de Visão Geral."""
    return {
        "topbar":      get_overview_topbar(),
        "turno_atual": get_overview_turno(),
        "linhas":      get_overview_linhas(),
    }