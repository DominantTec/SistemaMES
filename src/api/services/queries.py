from datetime import datetime, date, time, timedelta
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
        lista_duracao_turno = []  # duração total de cada turno (sem capping em agora)

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

        agora = datetime.utcnow()

        for _, row in df_registradores.iterrows():
            # Filtra o turno exato que contém o timestamp deste registro
            current_shift = df_shifts[
                (df_shifts["dt_inicio"].dt.date == row["dt_created_at"].date()) &
                (df_shifts["id_ihm"] == machine_id) &
                (df_shifts["dt_inicio"] <= row["dt_created_at"]) &
                (df_shifts["dt_fim"]   >= row["dt_created_at"])
            ]

            if current_shift.empty:
                status_antigo = row.get("status_maquina", status_antigo)
                continue

            shift_inicio = current_shift["dt_inicio"].to_list()[0]
            shift_fim    = current_shift["dt_fim"].to_list()[0]

            if status_antigo != "Produzindo" and row["status_maquina"] == "Produzindo":
                if row["dt_created_at"] < shift_fim:
                    inicio = shift_inicio if row["dt_created_at"] < shift_inicio else row["dt_created_at"]
                    inicio_qtd_aprovado = row.get("produzido")
                    inicio_qtd_reprovado = row.get("reprovado")
                    inicio_qtd_total = row.get("total_produzido")
                    inicio_teorico = shift_inicio

            elif (
                (status_antigo == "Produzindo" and row["status_maquina"] != "Produzindo") or
                (status_antigo == "Produzindo" and row["status_maquina"] == "Produzindo" and row["dt_created_at"] == last_register["dt_created_at"].to_list()[0])
            ):
                if row["dt_created_at"] > shift_inicio:
                    fim = shift_fim if row["dt_created_at"] > shift_fim else row["dt_created_at"]
                    fim_qtd_aprovado = row.get("produzido")
                    fim_qtd_reprovado = row.get("reprovado")
                    fim_qtd_total = row.get("total_produzido")
                    fim_teorico = shift_fim

            if inicio and fim:
                if inicio.day == fim.day:
                    if (inicio, fim) not in lista_produzido:
                        lista_produzido.append((inicio, fim))
                    # Usa o tempo decorrido até agora (não o turno inteiro)
                    # para que disponibilidade comece em 100% e só caia em paradas
                    fim_decorrido = min(fim_teorico, agora)
                    if (inicio_teorico, fim_decorrido) not in lista_esperado:
                        lista_esperado.append((inicio_teorico, fim_decorrido))
                    if (inicio_teorico, fim_teorico) not in lista_duracao_turno:
                        lista_duracao_turno.append((inicio_teorico, fim_teorico))

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

        disponibilidade = min(1.0, tempo_produzido / tempo_programado) if tempo_programado else 1.0

        meta = get_meta(machine_id)
        # Meta proporcional ao tempo decorrido: evita OEE=0 no início do turno.
        # Ex: meta=1000 peças/turno, turno=8h, decorrido=1h → meta_proporcional=125
        duracao_turno = sum([(b - a).total_seconds() for a, b in lista_duracao_turno])
        meta_proporcional = meta * (tempo_programado / duracao_turno) if duracao_turno else 0
        performance = min(1.0, int(total) / meta_proporcional) if meta_proporcional > 0 else 1.0
        qualidade = min(1.0, int(produzido) / int(total)) if total else 1.0

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
    """Retorna mudanças de status e motivo de parada de uma IHM."""
    params: Dict[str, Any] = {"id_ihm": id_ihm}
    filtro_data = ""
    if data_inicio and data_fim:
        filtro_data = "AND lr.dt_created_at >= :data_inicio AND lr.dt_created_at <= :data_fim"
        params["data_inicio"] = data_inicio
        params["data_fim"] = data_fim

    df = run_query(f"""
        SELECT TOP 50
            lr.dt_created_at,
            r.tx_descricao,
            lr.nu_valor_bruto
        FROM dbo.tb_log_registrador lr
        JOIN dbo.tb_registrador r ON r.id_registrador = lr.id_registrador
        WHERE lr.id_ihm = :id_ihm
          AND r.tx_descricao IN ('status_maquina', 'motivo_parada')
          {filtro_data}
        ORDER BY lr.dt_created_at DESC
    """, params)

    return df.to_dict(orient="records")


# =========================
# DETALHE DE MÁQUINA
# =========================

def get_machine_detail(machine_id: int) -> dict:
    """Payload completo da tela de detalhe de uma máquina específica."""
    df_ihm = run_query("""
        SELECT i.id_ihm, i.tx_name, l.tx_name AS linha_nome
        FROM dbo.tb_ihm i
        JOIN dbo.tb_linha_producao l ON l.id_linha_producao = i.id_linha_producao
        WHERE i.id_ihm = :id
    """, {"id": machine_id})

    if df_ihm.empty:
        return {"erro": f"Máquina {machine_id} não encontrada"}

    ihm     = df_ihm.iloc[0]
    metrics = get_metrics_machine(machine_id)
    peca    = get_selected_piece(machine_id)

    op_nome  = _resolve_nome(metrics.get("operador"),   machine_id, "tb_depara_operador",  "nu_cod_operador",   "tx_operador")
    man_nome = _resolve_nome(metrics.get("manutentor"), machine_id, "tb_depara_manutentor", "nu_cod_manutentor", "tx_manutentor")

    # --- logs de status para calcular paradas e índices ---
    depara_status_txt = {
        0: "Parada", 1: "Passar Padrão", 4: "Limpeza",
        49: "Produzindo", 50: "Maquina Liberada",
        51: "Aguardando Manutentor", 52: "Máquina em manutenção",
        53: "Alteração de Parâmetros",
    }

    df_logs = run_query("""
        SELECT lr.dt_created_at, lr.nu_valor_bruto, r.tx_descricao
        FROM dbo.tb_log_registrador lr
        JOIN dbo.tb_registrador r ON r.id_registrador = lr.id_registrador
        WHERE lr.id_ihm = :id
          AND r.tx_descricao IN ('status_maquina', 'motivo_parada')
        ORDER BY lr.dt_created_at
    """, {"id": machine_id})

    paradas: List[Dict[str, Any]] = []
    tempos_parada_s: List[float] = []

    if not df_logs.empty:
        df_status = df_logs[df_logs["tx_descricao"] == "status_maquina"]
        df_motivo = df_logs[df_logs["tx_descricao"] == "motivo_parada"]
        rows      = df_status[["dt_created_at", "nu_valor_bruto"]].values.tolist()

        inicio_parada = None
        status_ant    = None

        for dt, cod in rows:
            cod = int(cod)
            if status_ant == 49 and cod != 49:
                inicio_parada = dt
            elif status_ant != 49 and cod == 49 and inicio_parada is not None:
                dur_s = (dt - inicio_parada).total_seconds()
                tempos_parada_s.append(dur_s)
                h, r = divmod(int(dur_s), 3600)

                motivo = None
                if not df_motivo.empty:
                    df_m = df_motivo[df_motivo["dt_created_at"] >= inicio_parada]
                    if not df_m.empty:
                        motivo = _resolve_nome(
                            df_m.iloc[0]["nu_valor_bruto"], machine_id,
                            "tb_depara_motivo_parada", "nu_cod_motivo_parada", "tx_motivo_parada",
                        )

                paradas.append({
                    "inicio":  inicio_parada.strftime("%H:%M"),
                    "motivo":  motivo or depara_status_txt.get(status_ant, "-"),
                    "duracao": f"{h}h {r // 60:02d}m" if h else f"{r // 60}m",
                    "status":  depara_status_txt.get(status_ant, "-"),
                })
                inicio_parada = None
            status_ant = cod

    # --- MTBF / MTTR (simplificado a partir dos logs disponíveis) ---
    def fmt_hm(seconds: float) -> str:
        h, r = divmod(int(max(0, seconds)), 3600)
        return f"{h}h {r // 60:02d}m"

    num_paradas = len(paradas)
    mttr_s = sum(tempos_parada_s) / num_paradas if num_paradas else 0

    if not df_logs.empty and num_paradas:
        janela_s  = (df_logs["dt_created_at"].max() - df_logs["dt_created_at"].min()).total_seconds()
        mtbf_s    = (janela_s - sum(tempos_parada_s)) / num_paradas
    else:
        mtbf_s = 0

    return {
        "id":              machine_id,
        "nome":            ihm["tx_name"],
        "linha":           ihm["linha_nome"],
        "status":          metrics["status_maquina"],
        "peca_atual":      peca if peca != "PEÇA TEMP" else None,
        "operador":        op_nome,
        "operador_avatar": _avatar(op_nome),
        "manutentor":      man_nome,
        "oee":             metrics["oee"],
        "disponibilidade": metrics["disponibilidade"],
        "performance":     metrics["performance"],
        "qualidade":       metrics["qualidade"],
        "manutencao": {
            "mtbf": fmt_hm(mtbf_s),
            "mttr": fmt_hm(mttr_s),
            "mtta": None,
        },
        "registros_parada": paradas,
    }

# =========================
# HELPERS INTERNOS
# =========================

_CORES_EQUIPE = ["#f59e0b", "#3b82f6", "#10b981", "#8b5cf6", "#ef4444"]
_STATUS_NAO_PRODUTIVO = {"Parada", "Máquina em manutenção", "Limpeza", "Aguardando Manutentor"}


def _resolve_nome(codigo: Any, id_ihm: int, tabela: str, col_cod: str, col_nome: str) -> Optional[str]:
    """Resolve um código numérico para nome via tabela de de-para."""
    try:
        cod = int(float(codigo))
        if cod == 0:
            return None
        df = run_query(f"""
            SELECT {col_nome} FROM dbo.{tabela}
            WHERE id_ihm = :id AND {col_cod} = :cod
        """, {"id": id_ihm, "cod": cod})
        return df[col_nome].iloc[0] if not df.empty else None
    except Exception:
        return None


def _avatar(nome: Optional[str]) -> Optional[str]:
    """Gera as iniciais de um nome para avatar."""
    if not nome:
        return None
    return "".join(p[0].upper() for p in str(nome).split() if p)[:2]


# =========================
# VISÃO GERAL
# =========================

def get_overview_topbar() -> dict:
    """KPIs globais e eventos recentes para a topbar da Visão Geral."""
    maquinas_total = int(run_query("SELECT COUNT(*) AS total FROM dbo.tb_ihm")["total"].iloc[0])

    # Último status de cada IHM
    df_status = run_query("""
        SELECT lr.id_ihm, lr.nu_valor_bruto AS status
        FROM dbo.tb_log_registrador lr
        JOIN dbo.tb_registrador r ON r.id_registrador = lr.id_registrador
        INNER JOIN (
            SELECT lr2.id_ihm, MAX(lr2.dt_created_at) AS max_dt
            FROM dbo.tb_log_registrador lr2
            JOIN dbo.tb_registrador r2 ON r2.id_registrador = lr2.id_registrador
            WHERE r2.tx_descricao = 'status_maquina'
            GROUP BY lr2.id_ihm
        ) latest ON latest.id_ihm = lr.id_ihm AND lr.dt_created_at = latest.max_dt
        WHERE r.tx_descricao = 'status_maquina'
    """)

    status_inativos = {0, 52}
    maquinas_ativas = (
        int(df_status[~df_status["status"].isin(status_inativos)]["id_ihm"].nunique())
        if not df_status.empty else 0
    )

    # Eventos recentes: últimas mudanças de status
    depara_status = {
        0: "Máquina parada",       1: "Passando padrão",
        4: "Iniciou limpeza",     49: "Entrou em produção",
        50: "Máquina liberada",   51: "Aguardando manutentor",
        52: "Entrou em manutenção", 53: "Alteração de parâmetros",
    }
    df_eventos = run_query("""
        SELECT TOP 5
            i.tx_name AS maquina,
            lr.dt_created_at,
            lr.nu_valor_bruto AS status_cod
        FROM dbo.tb_log_registrador lr
        JOIN dbo.tb_registrador r ON r.id_registrador = lr.id_registrador
        JOIN dbo.tb_ihm i ON i.id_ihm = lr.id_ihm
        WHERE r.tx_descricao = 'status_maquina'
        ORDER BY lr.dt_created_at DESC
    """)
    eventos = [
        {
            "hora":      row["dt_created_at"].strftime("%H:%M"),
            "maquina":   row["maquina"],
            "descricao": depara_status.get(int(row["status_cod"]), f"Status {int(row['status_cod'])}"),
        }
        for _, row in df_eventos.iterrows()
    ]

    return {
        "titulo":          "Monitoramento de Chão de Fábrica",
        "oee_global":      None,  # preenchido por get_overview_data após calcular as linhas
        "maquinas_ativas": maquinas_ativas,
        "maquinas_total":  maquinas_total,
        "data_hora":       datetime.now().strftime("%d/%m/%Y - %H:%M:%S"),
        "user_initials":   "BG",
        "eventos_recentes": eventos,
    }


_DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
_DEPARA_STATUS_CFG = {
    0: "Parada", 4: "Limpeza", 49: "Em Produção",
    51: "Ag. Manutentor", 52: "Em Manutenção", 53: "Alt. Parâmetros",
}


def get_all_machines() -> list:
    """Lista todas as IHMs com nome e linha."""
    df = run_query("""
        SELECT i.id_ihm, i.tx_name, l.tx_name AS linha_nome
        FROM dbo.tb_ihm i
        JOIN dbo.tb_linha_producao l ON l.id_linha_producao = i.id_linha_producao
        ORDER BY i.id_ihm
    """)
    return [
        {"id": int(r["id_ihm"]), "nome": r["tx_name"], "linha": r["linha_nome"]}
        for _, r in df.iterrows()
    ]


def get_machine_config_data(machine_id: int) -> dict:
    """Dados completos para a tela de Configurações de uma máquina."""
    df_ihm = run_query("""
        SELECT i.id_ihm, i.tx_name, l.tx_name AS linha_nome, i.id_linha_producao
        FROM dbo.tb_ihm i
        JOIN dbo.tb_linha_producao l ON l.id_linha_producao = i.id_linha_producao
        WHERE i.id_ihm = :id
    """, {"id": machine_id})

    if df_ihm.empty:
        return {"erro": f"Máquina {machine_id} não encontrada"}

    ihm = df_ihm.iloc[0]

    df_status = run_query("""
        SELECT TOP 1 lr.nu_valor_bruto, lr.dt_created_at
        FROM dbo.tb_log_registrador lr
        JOIN dbo.tb_registrador r ON r.id_registrador = lr.id_registrador
        WHERE lr.id_ihm = :id AND r.tx_descricao = 'status_maquina'
        ORDER BY lr.dt_created_at DESC
    """, {"id": machine_id})

    if not df_status.empty:
        status_cod = int(df_status.iloc[0]["nu_valor_bruto"])
        status_txt = _DEPARA_STATUS_CFG.get(status_cod, f"Status {status_cod}")
        status_desde = df_status.iloc[0]["dt_created_at"].strftime("%H:%M")
    else:
        status_txt, status_desde = "-", "-"

    meta = get_meta(machine_id)
    peca_atual = get_selected_piece(machine_id)
    pecas = get_possible_pieces(machine_id)

    df_turnos = run_query("""
        SELECT dt_inicio, dt_fim, bl_ativo
        FROM dbo.tb_turnos
        WHERE id_linha_producao = :linha
        ORDER BY dt_inicio
    """, {"linha": int(ihm["id_linha_producao"])})

    shifts_by_dow: dict = {}
    if not df_turnos.empty:
        for _, t in df_turnos.iterrows():
            dow = t["dt_inicio"].weekday()
            if dow not in shifts_by_dow:
                shifts_by_dow[dow] = {
                    "inicio": t["dt_inicio"].strftime("%H:%M"),
                    "fim":    t["dt_fim"].strftime("%H:%M"),
                    "ativo":  bool(t["bl_ativo"]),
                }

    calendario = []
    for i, dia in enumerate(_DIAS_SEMANA):
        if i in shifts_by_dow:
            entry = {**shifts_by_dow[i], "dia": dia}
        else:
            entry = {"dia": dia, "inicio": "07:00", "fim": "17:00", "ativo": i < 5}
        calendario.append(entry)

    return {
        "id":           int(ihm["id_ihm"]),
        "nome":         ihm["tx_name"],
        "linha":        ihm["linha_nome"],
        "id_linha":     int(ihm["id_linha_producao"]),
        "status":       status_txt,
        "status_desde": status_desde,
        "meta":         meta,
        "peca_atual":   peca_atual,
        "pecas":        pecas,
        "calendario":   calendario,
    }


def update_machine_config(machine_id: int, meta: int, peca_nome: str, calendario: list) -> dict:
    """Salva meta, peça e calendário semanal de uma máquina."""
    df_regs = run_query("""
        SELECT id_registrador, tx_descricao
        FROM tb_registrador
        WHERE id_ihm = :id AND tx_descricao IN ('meta', 'modelo_peça')
    """, {"id": machine_id})
    regs = {r["tx_descricao"]: int(r["id_registrador"]) for _, r in df_regs.iterrows()}

    if "meta" in regs:
        run_query_update("""
            INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto)
            VALUES (:id_ihm, :id_reg, :valor)
        """, {"id_ihm": machine_id, "id_reg": regs["meta"], "valor": meta})

    if "modelo_peça" in regs:
        df_peca = run_query("""
            SELECT nu_cod_peca FROM tb_depara_peca
            WHERE id_ihm = :id AND tx_peca = :nome
        """, {"id": machine_id, "nome": peca_nome})
        if not df_peca.empty:
            cod_peca = int(df_peca.iloc[0]["nu_cod_peca"])
            run_query_update("""
                INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto)
                VALUES (:id_ihm, :id_reg, :valor)
            """, {"id_ihm": machine_id, "id_reg": regs["modelo_peça"], "valor": cod_peca})

    df_ihm = run_query("SELECT id_linha_producao FROM tb_ihm WHERE id_ihm = :id", {"id": machine_id})
    if not df_ihm.empty:
        id_linha = int(df_ihm.iloc[0]["id_linha_producao"])
        run_query_update("DELETE FROM dbo.tb_turnos WHERE id_linha_producao = :linha", {"linha": id_linha})

        dow_map = {d: i for i, d in enumerate(_DIAS_SEMANA)}
        today = date.today()
        for entry in calendario:
            if not entry.get("ativo", False):
                continue
            dow_target = dow_map.get(entry["dia"])
            if dow_target is None:
                continue
            days_ahead = (dow_target - today.weekday()) % 7
            target_date = today + timedelta(days=days_ahead)
            hi, hm = map(int, entry["inicio"].split(":"))
            fi, fm = map(int, entry["fim"].split(":"))
            dt_inicio = datetime.combine(target_date, time(hi, hm))
            dt_fim_base = datetime.combine(target_date, time(fi, fm))
            dt_fim = dt_fim_base + timedelta(days=1) if (fi, fm) < (hi, hm) else dt_fim_base
            run_query_update("""
                INSERT INTO dbo.tb_turnos (tx_name, dt_inicio, dt_fim, id_linha_producao, bl_ativo)
                VALUES (:nome, :dt_inicio, :dt_fim, :linha, 1)
            """, {
                "nome": f"TURNO_{entry['dia'][:3].upper()}",
                "dt_inicio": dt_inicio,
                "dt_fim": dt_fim,
                "linha": id_linha,
            })

    return {"ok": True}


def get_overview_turno() -> dict:
    """Informações do turno atual."""
    df = run_query("""
        SELECT TOP 1 tx_name, dt_inicio, dt_fim
        FROM dbo.tb_turnos
        WHERE bl_ativo = 1
          AND dt_inicio <= GETDATE()
          AND dt_fim    >= GETDATE()
        ORDER BY dt_inicio
    """)

    if df.empty:
        return {"nome": "-", "encerra_em": "-", "progresso_pct": 0}

    row = df.iloc[0]
    agora     = datetime.now()
    dt_inicio = row["dt_inicio"]
    dt_fim    = row["dt_fim"]

    duracao   = (dt_fim - dt_inicio).total_seconds()
    decorrido = (agora - dt_inicio).total_seconds()
    progresso = int(100 * decorrido / duracao) if duracao else 0

    restante_s    = max(0, (dt_fim - agora).total_seconds())
    horas, resto  = divmod(int(restante_s), 3600)
    encerra_em    = f"{horas:02d}:{resto // 60:02d}h"

    return {
        "nome":          row["tx_name"],
        "encerra_em":    encerra_em,
        "progresso_pct": min(100, max(0, progresso)),
    }


def get_overview_linhas() -> list:
    """Lista de linhas de produção com suas máquinas e métricas."""
    df_linhas = get_lines_df()
    resultado = []

    for _, linha in df_linhas.iterrows():
        line_id    = int(linha["id_linha_producao"])
        df_machines = get_machines_by_line_df(line_id)

        maquinas        = []
        total_produzido = 0
        total_meta      = 0

        for _, machine in df_machines.iterrows():
            machine_id = int(machine["id_ihm"])
            metrics    = get_metrics_machine(machine_id)

            produzido = metrics["produzido"] if isinstance(metrics["produzido"], (int, float)) else 0
            meta      = metrics["meta"]      if isinstance(metrics["meta"],      (int, float)) else 0
            total_produzido += produzido
            total_meta      += meta

            maquinas.append({
                "id":              machine_id,
                "nome":            machine["tx_name"],
                "status":          metrics["status_maquina"],
                "op":              None,
                "oee":             metrics["oee"],
                "disponibilidade": metrics["disponibilidade"],
                "qualidade":       metrics["qualidade"],
                "performance":     metrics["performance"],
                "produzido":       produzido,
                "meta":            meta,
            })

        realizado_pct = int(100 * total_produzido / total_meta) if total_meta else 0
        resultado.append({
            "id":            line_id,
            "nome":          linha["tx_name"],
            "meta_hora":     total_meta,
            "realizado":     total_produzido,
            "realizado_pct": realizado_pct,
            "maquinas":      maquinas,
        })

    return resultado


def get_overview_data() -> dict:
    """Payload completo da tela de Visão Geral."""
    linhas = get_overview_linhas()
    topbar = get_overview_topbar()

    all_oees = [m["oee"] for l in linhas for m in l["maquinas"] if isinstance(m.get("oee"), (int, float))]
    topbar["oee_global"] = round(sum(all_oees) / len(all_oees), 1) if all_oees else "-"

    return {
        "topbar":      topbar,
        "turno_atual": get_overview_turno(),
        "linhas":      linhas,
    }


# =========================
# DETALHE DE LINHA
# =========================

def get_line_detail(line_id: int) -> dict:
    """Payload completo da tela de Monitoramento de uma Linha específica."""
    df_linha = run_query("""
        SELECT id_linha_producao, tx_name
        FROM dbo.tb_linha_producao
        WHERE id_linha_producao = :id
    """, {"id": line_id})

    if df_linha.empty:
        return {"erro": f"Linha {line_id} não encontrada"}

    nome_linha  = df_linha.iloc[0]["tx_name"]
    df_machines = get_machines_by_line_df(line_id)

    maquinas         = []
    total_produzido  = 0
    total_meta       = 0
    oees: List[float]         = []
    maquinas_ativas  = 0
    operadores_vistos: Dict[str, str] = {}  # nome → cor

    for _, machine in df_machines.iterrows():
        machine_id = int(machine["id_ihm"])
        metrics    = get_metrics_machine(machine_id)
        status     = metrics["status_maquina"]

        produzido = metrics["produzido"] if isinstance(metrics["produzido"], (int, float)) else 0
        reprovado = metrics["reprovado"] if isinstance(metrics["reprovado"], (int, float)) else 0
        meta      = metrics["meta"]      if isinstance(metrics["meta"],      (int, float)) else 0
        oee       = metrics["oee"]       if isinstance(metrics["oee"],       (int, float)) else 0

        total_produzido += produzido
        total_meta      += meta
        if isinstance(oee, (int, float)):
            oees.append(oee)
        if status not in _STATUS_NAO_PRODUTIVO and status != "-":
            maquinas_ativas += 1

        # Peça atual
        peca = get_selected_piece(machine_id)
        peca = peca if peca != "PEÇA TEMP" else None

        # Operador, manutentor, engenheiro (resolve código → nome)
        op_nome  = _resolve_nome(metrics.get("operador"),   machine_id, "tb_depara_operador",  "nu_cod_operador",   "tx_operador")
        man_nome = _resolve_nome(metrics.get("manutentor"), machine_id, "tb_depara_manutentor", "nu_cod_manutentor", "tx_manutentor")
        eng_nome = _resolve_nome(metrics.get("engenheiro"), machine_id, "tb_depara_engenheiro", "nu_cod_engenheiro", "tx_engenheiro")

        if op_nome and op_nome not in operadores_vistos:
            operadores_vistos[op_nome] = _CORES_EQUIPE[len(operadores_vistos) % len(_CORES_EQUIPE)]

        # Motivo de parada
        motivo_parada = None
        df_mot = run_query("""
            SELECT TOP 1 lr.nu_valor_bruto
            FROM dbo.tb_log_registrador lr
            JOIN dbo.tb_registrador r ON r.id_registrador = lr.id_registrador
            WHERE lr.id_ihm = :id AND r.tx_descricao = 'motivo_parada'
            ORDER BY lr.dt_created_at DESC
        """, {"id": machine_id})
        if not df_mot.empty:
            motivo_parada = _resolve_nome(
                df_mot.iloc[0]["nu_valor_bruto"], machine_id,
                "tb_depara_motivo_parada", "nu_cod_motivo_parada", "tx_motivo_parada",
            )

        # Tempo parado
        parada_ha = None
        if status in _STATUS_NAO_PRODUTIVO:
            df_parada = run_query("""
                SELECT TOP 1 lr.dt_created_at
                FROM dbo.tb_log_registrador lr
                JOIN dbo.tb_registrador r ON r.id_registrador = lr.id_registrador
                WHERE lr.id_ihm = :id AND r.tx_descricao = 'status_maquina'
                ORDER BY lr.dt_created_at DESC
            """, {"id": machine_id})
            if not df_parada.empty:
                delta      = datetime.utcnow() - df_parada.iloc[0]["dt_created_at"]
                h, resto   = divmod(max(0, int(delta.total_seconds())), 3600)
                parada_ha  = f"{h:02d}:{resto // 60:02d}"

        maquinas.append({
            "id":              machine_id,
            "nome":            machine["tx_name"],
            "tipo":            None,
            "status":          status,
            "op":              None,
            "peca":            peca,
            "oee":             oee,
            "disponibilidade": metrics["disponibilidade"],
            "performance":     metrics["performance"],
            "qualidade":       metrics["qualidade"],
            "produzido":       produzido,
            "rejeitos":        reprovado,
            "ciclo_segundos":  None,
            "operador":        op_nome,
            "operador_avatar": _avatar(op_nome),
            "manutentor":      man_nome,
            "engenheiro":      eng_nome,
            "motivo_parada":   motivo_parada,
            "manutencao":      man_nome if status == "Máquina em manutenção" else None,
            "parada_ha":       parada_ha,
        })

    oee_global = round(sum(oees) / len(oees), 1) if oees else 0
    equipe = [
        {"iniciais": _avatar(nome), "cor": cor}
        for nome, cor in list(operadores_vistos.items())[:5]
    ]

    return {
        "id":                 line_id,
        "nome":               nome_linha,
        "status_geral":       "Operação Normal",
        "ultima_atualizacao": datetime.now().strftime("%H:%M:%S"),
        "kpis": {
            "oee_global":       oee_global,
            "oee_variacao":     None,
            "producao_hoje":    total_produzido,
            "producao_meta":    total_meta,
            "previsao_termino": None,
            "maquinas_ativas":  maquinas_ativas,
            "maquinas_total":   len(maquinas),
            "equipe":           equipe,
            "equipe_extras":    max(0, len(operadores_vistos) - 5),
            "supervisor":       None,
        },
        "maquinas": maquinas,
    }