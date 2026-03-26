from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd

from api.services.db import run_query, run_query_update, run_query_insert


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


# ─── Schema auto-migration ──────────────────────────────────────────────────
_schema_ensured = False

def _ensure_schema():
    """Cria tabela e colunas novas se ainda não existirem (idempotente)."""
    global _schema_ensured
    if _schema_ensured:
        return
    try:
        run_query_update("""
            IF NOT EXISTS (
                SELECT * FROM sys.objects
                WHERE object_id = OBJECT_ID(N'dbo.tb_config_producao_teorica') AND type = 'U'
            )
            BEGIN
                CREATE TABLE dbo.tb_config_producao_teorica (
                    id_ihm              INT  PRIMARY KEY,
                    nu_producao_teorica INT  NOT NULL DEFAULT 0,
                    dt_updated          DATETIME DEFAULT GETDATE()
                )
            END
        """)
        for col_def in [
            ("nu_meta_turno_atual",      "INT  NOT NULL DEFAULT 0"),
            ("nu_pecas_proximos_turnos", "INT  NOT NULL DEFAULT 0"),
            ("dt_fim_turno_calculado",   "DATETIME NULL"),
        ]:
            run_query_update(f"""
                IF NOT EXISTS (
                    SELECT * FROM sys.columns
                    WHERE object_id = OBJECT_ID('dbo.tb_ordem_producao')
                      AND name = '{col_def[0]}'
                )
                    ALTER TABLE dbo.tb_ordem_producao ADD {col_def[0]} {col_def[1]}
            """)
        _schema_ensured = True
    except Exception:
        pass  # não travar se o banco ainda não estiver disponível

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

        df_depara = run_query("""
            SELECT nu_cod_motivo_parada, tx_motivo_parada
            FROM tb_depara_motivo_parada
            WHERE id_ihm = :id
        """, {"id": machine_id})
        depara_status_maquina = (
            dict(zip(df_depara["nu_cod_motivo_parada"].astype(int), df_depara["tx_motivo_parada"]))
            if not df_depara.empty else {}
        )

        if "status_maquina" in df_registradores.columns:
            df_registradores["nu_status_maquina"] = df_registradores["status_maquina"].astype("Int64")
            df_registradores["status_maquina"] = df_registradores["nu_status_maquina"].map(depara_status_maquina)

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
    """Retorna a meta antes da data informada.
    Ignora valores zero — a IHM real retorna 0 no registrador de meta,
    e o valor correto é sempre o último definido pelo usuário via UI."""
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
                  AND nu_valor_bruto > 0
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
                  AND nu_valor_bruto > 0
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


def _get_current_shift_window(machine_id: int, agora: datetime):
    """Retorna (dt_inicio, dt_fim) do turno ativo agora para a máquina.
    Se não houver turno ativo, usa o turno mais recente que terminou hoje.
    Se não houver nenhum turno hoje, retorna (início do dia, agora)."""
    df = run_query("""
        SELECT TOP 1 t.dt_inicio, t.dt_fim
        FROM dbo.tb_turnos t
        JOIN dbo.tb_ihm i ON i.id_linha_producao = t.id_linha_producao
        WHERE i.id_ihm = :id
          AND t.dt_inicio <= :agora
          AND t.dt_fim    >= :agora
        ORDER BY t.dt_inicio
    """, {"id": machine_id, "agora": agora})

    if not df.empty:
        return df.iloc[0]["dt_inicio"], df.iloc[0]["dt_fim"]

    # Último turno que terminou hoje
    df2 = run_query("""
        SELECT TOP 1 t.dt_inicio, t.dt_fim
        FROM dbo.tb_turnos t
        JOIN dbo.tb_ihm i ON i.id_linha_producao = t.id_linha_producao
        WHERE i.id_ihm   = :id
          AND t.dt_fim   <= :agora
          AND t.dt_inicio >= :inicio_dia
        ORDER BY t.dt_fim DESC
    """, {"id": machine_id, "agora": agora,
          "inicio_dia": datetime.combine(agora.date(), time(0, 0))})

    if not df2.empty:
        return df2.iloc[0]["dt_inicio"], df2.iloc[0]["dt_fim"]

    # Fallback: início do dia até agora
    return datetime.combine(agora.date(), time(0, 0)), agora


def get_metrics_machine(machine_id: int, data_inicio: Optional[Any] = None, data_fim: Optional[Any] = None) -> Dict[str, Any]:
    """Retorna as principais informações de uma IHM para o turno atual (ou período informado)."""
    try:
        agora = datetime.utcnow()

        # Quando não há filtro de data, calcula apenas para o turno atual.
        # Isso evita acumular histórico de dias/turnos anteriores no OEE.
        if not data_inicio or not data_fim:
            data_inicio, data_fim = _get_current_shift_window(machine_id, agora)

        shift_inicio  = data_inicio
        shift_fim_ref = data_fim   # limite teórico do turno
        # Para turno ainda em andamento, o teto real é agora
        fim_efetivo   = min(shift_fim_ref, agora)
        duracao_turno = (fim_efetivo - shift_inicio).total_seconds()

        # Limita os registros a agora — registros futuros (init.sql com timestamps
        # adiantados) criariam intervalos negativos de produção.
        data_fim_registros = min(shift_fim_ref, agora)
        df_registradores = get_machine_timeline(machine_id, data_inicio=shift_inicio, data_fim=data_fim_registros)
        df_shifts        = get_machine_shifts(machine_id,   data_inicio=shift_inicio, data_fim=shift_fim_ref)

        # Remove linhas sem status (registros de meta/peça salvos pela UI)
        if "status_maquina" in df_registradores.columns:
            df_registradores = df_registradores[df_registradores["status_maquina"].notna()].copy()

        if df_registradores.empty:
            return {
                "status_maquina": "-", "oee": "-", "disponibilidade": "-",
                "performance": "-", "qualidade": "-", "meta": "-",
                "produzido": "-", "reprovado": "-", "total_produzido": "-",
                "operador": "-", "manutentor": "-", "engenheiro": "-",
            }

        last_register = df_registradores[df_registradores["dt_created_at"] == df_registradores["dt_created_at"].max()]

        status     = last_register["status_maquina"].to_list()[0] if "status_maquina" in last_register.columns else "-"
        operador   = last_register["operador"].to_list()[0]       if "operador"       in last_register.columns else "-"
        manutentor = last_register["manutentor"].to_list()[0]     if "manutentor"     in last_register.columns else "-"
        engenheiro = last_register["engenheiro"].to_list()[0]     if "engenheiro"     in last_register.columns else "-"

        # ── Calcula intervalos de produção dentro do turno ──────────────────
        lista_produzido:    list = []
        lista_qtd_aprovado:  list = []
        lista_qtd_reprovado: list = []
        lista_qtd_total:     list = []

        nu_status_antigo     = None
        inicio               = None
        inicio_qtd_aprovado  = None
        inicio_qtd_reprovado = None
        inicio_qtd_total     = None

        for _, row in df_registradores.iterrows():
            nu_st_raw = row.get("nu_status_maquina")
            if nu_st_raw is None or (hasattr(nu_st_raw, '__class__') and str(nu_st_raw) == '<NA>'):
                continue
            nu_st = int(nu_st_raw)

            # Entrada em produção (código 49)
            if nu_status_antigo != 49 and nu_st == 49:
                inicio               = max(shift_inicio, row["dt_created_at"])
                inicio_qtd_aprovado  = row.get("produzido")
                inicio_qtd_reprovado = row.get("reprovado")
                inicio_qtd_total     = row.get("total_produzido")

            # Saída de produção
            elif nu_status_antigo == 49 and nu_st != 49:
                if inicio is not None:
                    lista_produzido.append((inicio, min(row["dt_created_at"], shift_fim_ref)))
                    lista_qtd_aprovado.append((inicio_qtd_aprovado,   row.get("produzido")))
                    lista_qtd_reprovado.append((inicio_qtd_reprovado, row.get("reprovado")))
                    lista_qtd_total.append((inicio_qtd_total,          row.get("total_produzido")))
                    inicio = None

            nu_status_antigo = nu_st

        # Fecha sessão ainda aberta no fim do loop (máquina ainda produzindo).
        # Usa os valores do último registro como fim — sem isso total=0 e performance=0%.
        if inicio is not None and fim_efetivo > inicio:
            def _col(col):
                return last_register[col].to_list()[0] if col in last_register.columns else None
            lista_produzido.append((inicio, fim_efetivo))
            lista_qtd_aprovado.append((inicio_qtd_aprovado,  _col("produzido")))
            lista_qtd_reprovado.append((inicio_qtd_reprovado, _col("reprovado")))
            lista_qtd_total.append((inicio_qtd_total,         _col("total_produzido")))

        # ── Métricas de tempo ────────────────────────────────────────────────
        tempo_produzido = sum((b - a).total_seconds() for a, b in lista_produzido)

        # Disponibilidade: janela de observação a partir do primeiro registro
        # no turno (independente do status). Isso garante que se a máquina
        # estiver parada desde o início do turno, a disponibilidade vai cair.
        observation_start = df_registradores["dt_created_at"].min()
        tempo_programado  = (fim_efetivo - observation_start).total_seconds()
        disponibilidade   = min(1.0, tempo_produzido / tempo_programado) if tempo_programado > 0 else 1.0

        produzido = sum((b - a) for a, b in lista_qtd_aprovado  if a is not None and b is not None)
        reprovado = sum((b - a) for a, b in lista_qtd_reprovado if a is not None and b is not None)
        total     = sum((b - a) for a, b in lista_qtd_total      if a is not None and b is not None)

        meta = get_meta(machine_id)

        # Performance: usa a mesma janela de observação da disponibilidade.
        total_shift_s       = (shift_fim_ref - shift_inicio).total_seconds()
        observation_elapsed = (fim_efetivo - observation_start).total_seconds()
        meta_proporcional   = meta * (observation_elapsed / total_shift_s) if total_shift_s > 0 else 0
        performance         = min(1.0, int(total) / meta_proporcional) if meta_proporcional > 0 else 1.0
        qualidade   = min(1.0, int(produzido) / int(total))    if total            else 1.0

        oee = disponibilidade * performance * qualidade

        return {
            "status_maquina":  status,
            "oee":             round(100 * oee,             2),
            "disponibilidade": round(100 * disponibilidade, 2),
            "performance":     round(100 * performance,     2),
            "qualidade":       round(100 * qualidade,       2),
            "meta":            meta,
            "produzido":       produzido,
            "reprovado":       reprovado,
            "total_produzido": total,
            "operador":        operador,
            "manutentor":      manutentor,
            "engenheiro":      engenheiro,
        }
    except Exception:
        return {
            "status_maquina": "-", "oee": "-", "disponibilidade": "-",
            "performance": "-", "qualidade": "-", "meta": "-",
            "produzido": "-", "reprovado": "-", "total_produzido": "-",
            "operador": "-", "manutentor": "-", "engenheiro": "-",
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
    _df_depara_txt = run_query("""
        SELECT nu_cod_motivo_parada, tx_motivo_parada
        FROM tb_depara_motivo_parada
        WHERE id_ihm = :id
    """, {"id": machine_id})
    depara_status_txt = (
        dict(zip(_df_depara_txt["nu_cod_motivo_parada"].astype(int), _df_depara_txt["tx_motivo_parada"]))
        if not _df_depara_txt.empty else {}
    )

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

        inicio_parada    = None
        status_ant       = None
        motivo_parada_cod = None  # código não-0/não-49 visto durante a parada

        for dt, cod in rows:
            cod = int(cod)

            if status_ant == 49 and cod != 49:
                # Saída de produção: início da parada
                inicio_parada    = dt
                motivo_parada_cod = None

            elif status_ant != 49 and cod not in (0, 49):
                # Código intermediário durante a parada = motivo informado pelo operador
                motivo_parada_cod = cod

            elif status_ant != 49 and cod == 49 and inicio_parada is not None:
                # Retorno à produção: fecha o intervalo de parada
                dur_s = (dt - inicio_parada).total_seconds()
                tempos_parada_s.append(dur_s)
                h, r = divmod(int(dur_s), 3600)

                motivo = depara_status_txt.get(motivo_parada_cod, depara_status_txt.get(0, "Máquina Parada")) \
                    if motivo_parada_cod is not None \
                    else depara_status_txt.get(0, "Máquina Parada")

                paradas.append({
                    "inicio":  inicio_parada.strftime("%H:%M"),
                    "motivo":  motivo,
                    "duracao": f"{h}h {r // 60:02d}m" if h else f"{r // 60}m",
                    "status":  depara_status_txt.get(motivo_parada_cod or 0, "Máquina Parada"),
                    "codigo": motivo_parada_cod or 0
                })
                inicio_parada    = None
                motivo_parada_cod = None

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

    # Eventos recentes: últimas mudanças de status — busca labels do banco
    _df_depara_ev = run_query("""
        SELECT d.id_ihm, d.nu_cod_motivo_parada, d.tx_motivo_parada
        FROM tb_depara_motivo_parada d
    """)
    # Monta {id_ihm: {codigo: label}}
    depara_status_por_ihm: Dict[int, Dict[int, str]] = {}
    for _, r in _df_depara_ev.iterrows():
        depara_status_por_ihm.setdefault(int(r["id_ihm"]), {})[int(r["nu_cod_motivo_parada"])] = r["tx_motivo_parada"]
    df_eventos = run_query("""
        SELECT TOP 5
            i.tx_name AS maquina,
            t.id_ihm,
            t.dt_created_at,
            t.nu_valor_bruto AS status_cod
        FROM (
            SELECT
                lr.id_ihm,
                lr.dt_created_at,
                lr.nu_valor_bruto,
                LAG(lr.nu_valor_bruto) OVER (
                    PARTITION BY lr.id_ihm
                    ORDER BY lr.dt_created_at
                ) AS prev_status
            FROM dbo.tb_log_registrador lr
            JOIN dbo.tb_registrador r ON r.id_registrador = lr.id_registrador
            WHERE r.tx_descricao = 'status_maquina'
              AND lr.dt_created_at >= DATEADD(hour, -24, GETDATE())
        ) t
        JOIN dbo.tb_ihm i ON i.id_ihm = t.id_ihm
        WHERE t.prev_status IS NOT NULL
          AND t.nu_valor_bruto <> t.prev_status
        ORDER BY t.dt_created_at DESC
    """)
    eventos = [
        {
            "hora":      row["dt_created_at"].strftime("%H:%M"),
            "maquina":   row["maquina"],
            "descricao": depara_status_por_ihm.get(int(row["id_ihm"]), {}).get(
                int(row["status_cod"]), f"Status {int(row['status_cod'])}"
            ),
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


def get_line_shifts(line_id: int) -> dict:
    """Retorna nome da linha e lista de turnos configurados (um por template único dia+hora)."""
    df_linha = run_query("""
        SELECT id_linha_producao, tx_name
        FROM dbo.tb_linha_producao
        WHERE id_linha_producao = :id
    """, {"id": line_id})

    if df_linha.empty:
        return {"erro": f"Linha {line_id} não encontrada"}

    nome_linha = df_linha.iloc[0]["tx_name"]

    df_turnos = run_query("""
        SELECT tx_name, dt_inicio, dt_fim, bl_ativo
        FROM dbo.tb_turnos
        WHERE id_linha_producao = :linha
        ORDER BY dt_inicio
    """, {"linha": line_id})

    # Deduplica por (dia_semana, inicio, fim) — múltiplos turnos por dia são permitidos
    seen: set = set()
    turnos: list = []
    if not df_turnos.empty:
        for _, t in df_turnos.iterrows():
            dow  = t["dt_inicio"].weekday()
            ini  = t["dt_inicio"].strftime("%H:%M")
            fim_ = t["dt_fim"].strftime("%H:%M")
            key  = (dow, ini, fim_)
            if key not in seen:
                seen.add(key)
                turnos.append({
                    "dia":   _DIAS_SEMANA[dow],
                    "nome":  t["tx_name"],
                    "inicio": ini,
                    "fim":    fim_,
                    "ativo":  bool(t["bl_ativo"]),
                })

    # Ordenar por dia-da-semana e depois por horário de início
    dow_order = {d: i for i, d in enumerate(_DIAS_SEMANA)}
    turnos.sort(key=lambda x: (dow_order.get(x["dia"], 99), x["inicio"]))

    return {
        "id":     line_id,
        "nome":   nome_linha,
        "turnos": turnos,   # lista vazia se nenhum turno configurado
    }


def update_line_shifts(line_id: int, turnos: list) -> dict:
    """Salva a lista de turnos de uma linha, criando ocorrências para 5 semanas passadas + 1 futura."""
    dow_map = {d: i for i, d in enumerate(_DIAS_SEMANA)}
    today       = date.today()
    range_start = today - timedelta(weeks=5)
    range_end   = today + timedelta(weeks=1)

    run_query_update("DELETE FROM dbo.tb_turnos WHERE id_linha_producao = :linha", {"linha": line_id})

    for entry in turnos:
        if not entry.get("ativo", False):
            continue
        dow_target = dow_map.get(entry["dia"])
        if dow_target is None:
            continue
        hi, hm = map(int, entry["inicio"].split(":"))
        fi, fm = map(int, entry["fim"].split(":"))
        nome_turno = entry.get("nome") or f"TURNO_{entry['dia'][:3].upper()}"

        days_to_first = (dow_target - range_start.weekday()) % 7
        occurrence    = range_start + timedelta(days=days_to_first)

        while occurrence <= range_end:
            dt_inicio   = datetime.combine(occurrence, time(hi, hm))
            dt_fim_base = datetime.combine(occurrence, time(fi, fm))
            dt_fim      = dt_fim_base + timedelta(days=1) if (fi, fm) < (hi, hm) else dt_fim_base
            run_query_update("""
                INSERT INTO dbo.tb_turnos (tx_name, dt_inicio, dt_fim, id_linha_producao, bl_ativo)
                VALUES (:nome, :dt_inicio, :dt_fim, :linha, 1)
            """, {
                "nome":      nome_turno,
                "dt_inicio": dt_inicio,
                "dt_fim":    dt_fim,
                "linha":     line_id,
            })
            occurrence += timedelta(weeks=1)

    return {"ok": True}


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

    return {
        "id":                int(ihm["id_ihm"]),
        "nome":              ihm["tx_name"],
        "linha":             ihm["linha_nome"],
        "id_linha":          int(ihm["id_linha_producao"]),
        "status":            status_txt,
        "status_desde":      status_desde,
        "meta":              meta,
        "peca_atual":        peca_atual,
        "pecas":             pecas,
        "producao_teorica":  get_producao_teorica(int(ihm["id_ihm"])),
    }


def update_machine_config(machine_id: int, meta: int, peca_nome: str) -> dict:
    """Salva meta e peça de uma máquina."""
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


def get_historico_data(data_inicio: datetime, data_fim: datetime) -> dict:
    """Payload histórico para um período arbitrário."""
    df_linhas = get_lines_df()
    linhas = []

    for _, linha in df_linhas.iterrows():
        line_id     = int(linha["id_linha_producao"])
        df_machines = get_machines_by_line_df(line_id)

        maquinas        = []
        total_produzido = 0
        total_meta      = 0

        for _, machine in df_machines.iterrows():
            machine_id = int(machine["id_ihm"])
            metrics    = get_metrics_machine(machine_id, data_inicio=data_inicio, data_fim=data_fim)

            produzido = metrics["produzido"] if isinstance(metrics["produzido"], (int, float)) else 0
            meta      = metrics["meta"]      if isinstance(metrics["meta"],      (int, float)) else 0
            total_produzido += produzido
            total_meta      += meta

            maquinas.append({
                "id":              machine_id,
                "nome":            machine["tx_name"],
                "status":          metrics["status_maquina"],
                "oee":             metrics["oee"],
                "disponibilidade": metrics["disponibilidade"],
                "qualidade":       metrics["qualidade"],
                "performance":     metrics["performance"],
                "produzido":       produzido,
                "meta":            meta,
            })

        realizado_pct = int(100 * total_produzido / total_meta) if total_meta else 0
        linhas.append({
            "id":            line_id,
            "nome":          linha["tx_name"],
            "realizado":     total_produzido,
            "meta_total":    total_meta,
            "realizado_pct": realizado_pct,
            "maquinas":      maquinas,
        })

    all_oees = [m["oee"] for l in linhas for m in l["maquinas"] if isinstance(m.get("oee"), (int, float))]
    oee_global = round(sum(all_oees) / len(all_oees), 1) if all_oees else None

    return {
        "oee_global": oee_global,
        "periodo": {
            "inicio": data_inicio.strftime("%d/%m/%Y %H:%M"),
            "fim":    data_fim.strftime("%d/%m/%Y %H:%M"),
        },
        "linhas": linhas,
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

# =========================
# ORDENS DE PRODUÇÃO
# =========================

def ensure_ordens_table():
    """Cria tb_ordem_producao se ainda não existir."""
    run_query_update("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'tb_ordem_producao')
        BEGIN
            CREATE TABLE dbo.tb_ordem_producao (
                id_ordem          INT IDENTITY(1,1) PRIMARY KEY,
                nu_numero_op      VARCHAR(50)  NOT NULL,
                id_linha_producao INT          NOT NULL,
                tx_peca           VARCHAR(100) NOT NULL DEFAULT '',
                nu_quantidade     INT          NOT NULL DEFAULT 0,
                nu_meta_hora      INT          NOT NULL DEFAULT 0,
                tx_status         VARCHAR(20)  NOT NULL DEFAULT 'fila',
                nu_prioridade     INT          NOT NULL DEFAULT 0,
                dt_criacao        DATETIME     NOT NULL DEFAULT GETDATE(),
                dt_inicio         DATETIME     NULL,
                dt_fim            DATETIME     NULL,
                tx_observacoes    VARCHAR(500) NULL
            )
        END
    """)


def get_all_ordens() -> list:
    """Retorna todas as ordens de produção ordenadas por prioridade e data."""
    _ensure_schema()
    df = run_query("""
        SELECT
            o.id_ordem, o.nu_numero_op,
            o.id_linha_producao, l.tx_name AS linha_nome,
            o.tx_peca, o.nu_quantidade,
            o.tx_status, o.nu_prioridade,
            o.dt_criacao, o.dt_inicio, o.dt_fim,
            o.tx_observacoes,
            o.nu_meta_turno_atual,
            o.nu_pecas_proximos_turnos
        FROM dbo.tb_ordem_producao o
        JOIN dbo.tb_linha_producao l ON l.id_linha_producao = o.id_linha_producao
        ORDER BY o.nu_prioridade DESC, o.dt_criacao
    """)
    result = []
    for _, r in df.iterrows():
        result.append({
            "id":                    int(r["id_ordem"]),
            "numero_op":             r["nu_numero_op"],
            "linha_id":              int(r["id_linha_producao"]),
            "linha_nome":            r["linha_nome"],
            "peca":                  r["tx_peca"],
            "quantidade":            int(r["nu_quantidade"]),
            "meta_turno_atual":      int(r["nu_meta_turno_atual"]),
            "pecas_proximos_turnos": int(r["nu_pecas_proximos_turnos"]),
            "status":                r["tx_status"],
            "prioridade":            int(r["nu_prioridade"]),
            "dt_criacao":            r["dt_criacao"].isoformat() if r["dt_criacao"] is not None else None,
            "dt_inicio":             r["dt_inicio"].isoformat()  if r["dt_inicio"]  is not None else None,
            "dt_fim":                r["dt_fim"].isoformat()      if r["dt_fim"]     is not None else None,
            "observacoes":           r["tx_observacoes"],
        })
    return result


def proximo_numero_op() -> str:
    """Gera o próximo número de OP no formato OP-YYYYMM-XXXX."""
    ym = datetime.now().strftime("%Y%m")
    df = run_query("""
        SELECT COUNT(*) AS cnt FROM dbo.tb_ordem_producao
        WHERE nu_numero_op LIKE :pat
    """, {"pat": f"OP-{ym}-%"})
    cnt = int(df.iloc[0]["cnt"]) + 1 if not df.empty else 1
    return f"OP-{ym}-{cnt:04d}"


def create_ordem(numero_op, linha_id, peca, quantidade, prioridade, observacoes) -> int:
    """Cria nova ordem de produção, calcula metas por turno e retorna o id gerado."""
    _ensure_schema()
    metas = calcular_metas_op(linha_id, quantidade)
    return run_query_insert("""
        INSERT INTO dbo.tb_ordem_producao
            (nu_numero_op, id_linha_producao, tx_peca, nu_quantidade,
             nu_meta_hora, nu_prioridade, tx_observacoes,
             nu_meta_turno_atual, nu_pecas_proximos_turnos, dt_fim_turno_calculado)
        OUTPUT INSERTED.id_ordem
        VALUES (:num, :linha, :peca, :qtd,
                0, :pri, :obs,
                :meta_turno, :pecas_proximos, :dt_fim_turno)
    """, {
        "num":           numero_op,
        "linha":         linha_id,
        "peca":          peca,
        "qtd":           quantidade,
        "pri":           prioridade,
        "obs":           observacoes or None,
        "meta_turno":    metas["meta_turno_atual"],
        "pecas_proximos": metas["pecas_proximos_turnos"],
        "dt_fim_turno":  metas["dt_fim_turno"],
    })


STATUSES_VALIDOS = {"fila", "em_producao", "finalizado", "cancelado"}


# ─── Helpers internos de OP ──────────────────────────────────────────────────

def _set_meta_linha(linha_id: int, meta: int, peca: str = None) -> None:
    """Seta a meta de todas as máquinas de uma linha.
    Se peca=None, mantém a peça atual de cada máquina."""
    df_m = run_query("""
        SELECT id_ihm FROM dbo.tb_ihm WHERE id_linha_producao = :lid
    """, {"lid": linha_id})
    for _, m in df_m.iterrows():
        machine_id = int(m["id_ihm"])
        peca_usar  = peca if peca is not None else get_selected_piece(machine_id)
        try:
            update_machine_config(machine_id, meta, peca_usar)
        except Exception:
            pass


def _op_ativa_linha(linha_id: int, excluir_id: int = None) -> Optional[dict]:
    """Retorna a OP em_producao da linha, ou None.
    excluir_id: ignora essa OP na busca (usada ao mover a própria OP)."""
    params = {"lid": linha_id, "excluir": excluir_id if excluir_id else -1}
    df = run_query("""
        SELECT id_ordem, nu_meta_turno_atual, tx_peca
        FROM dbo.tb_ordem_producao
        WHERE id_linha_producao = :lid
          AND tx_status = 'em_producao'
          AND id_ordem <> :excluir
    """, params)
    if df.empty:
        return None
    r = df.iloc[0]
    return {"id": int(r["id_ordem"]), "meta": int(r["nu_meta_turno_atual"]), "peca": r["tx_peca"]}


def _ativar_proxima_op(linha_id: int) -> None:
    """Ativa automaticamente a próxima OP em 'fila' de maior prioridade na linha."""
    df = run_query("""
        SELECT TOP 1 id_ordem, nu_quantidade, tx_peca
        FROM dbo.tb_ordem_producao
        WHERE id_linha_producao = :lid AND tx_status = 'fila'
        ORDER BY nu_prioridade DESC, dt_criacao ASC
    """, {"lid": linha_id})
    if df.empty:
        return
    r          = df.iloc[0]
    prox_id    = int(r["id_ordem"])
    quantidade = int(r["nu_quantidade"])
    peca       = r["tx_peca"]

    # Recalcula metas com base no momento atual
    metas = calcular_metas_op(linha_id, quantidade)

    run_query_update("""
        UPDATE dbo.tb_ordem_producao
        SET tx_status                = 'em_producao',
            dt_inicio                = GETDATE(),
            dt_fim                   = NULL,
            nu_meta_turno_atual      = :meta,
            nu_pecas_proximos_turnos = :proximas,
            dt_fim_turno_calculado   = :dt_fim
        WHERE id_ordem = :id
    """, {
        "meta":     metas["meta_turno_atual"],
        "proximas": metas["pecas_proximos_turnos"],
        "dt_fim":   metas["dt_fim_turno"],
        "id":       prox_id,
    })
    _set_meta_linha(linha_id, metas["meta_turno_atual"], peca)


# ─── Status da OP ────────────────────────────────────────────────────────────

def update_ordem_status(ordem_id: int, new_status: str) -> dict:
    """
    Atualiza o status de uma OP tratando todos os cenários:

    fila        → em_producao : recalcula metas; bloqueia se já há outra ativa na linha;
                                 seta meta das máquinas
    em_producao → fila        : limpa meta das máquinas; recalcula metas do ponto atual
    em_producao → finalizado  : registra dt_fim; limpa meta; ativa próxima OP da fila
    em_producao → cancelado   : zera metas da OP; limpa meta; ativa próxima OP da fila
    fila        → cancelado   : zera metas da OP
    finalizado  → fila        : reabre OP; recalcula metas
    """
    if new_status not in STATUSES_VALIDOS:
        raise ValueError(f"Status inválido: {new_status}")

    # Carrega dados atuais da OP
    df_op = run_query("""
        SELECT tx_status, id_linha_producao, nu_quantidade, tx_peca
        FROM dbo.tb_ordem_producao WHERE id_ordem = :id
    """, {"id": ordem_id})
    if df_op.empty:
        raise ValueError(f"OP {ordem_id} não encontrada")

    r           = df_op.iloc[0]
    status_ant  = r["tx_status"]
    linha_id    = int(r["id_linha_producao"])
    quantidade  = int(r["nu_quantidade"])
    peca        = r["tx_peca"]

    # ── fila / finalizado → em_producao ──────────────────────────────────────
    if new_status == "em_producao":
        # Bloqueia se já há outra OP ativa na mesma linha
        ativa = _op_ativa_linha(linha_id, excluir_id=ordem_id)
        if ativa:
            raise ConflictError(
                f"Já existe uma OP em produção nesta linha (OP #{ativa['id']}). "
                "Finalize ou pause-a antes de iniciar uma nova."
            )

        # Recalcula metas com base no momento atual (não na criação)
        metas = calcular_metas_op(linha_id, quantidade)

        run_query_update("""
            UPDATE dbo.tb_ordem_producao
            SET tx_status                = 'em_producao',
                dt_inicio                = GETDATE(),
                dt_fim                   = NULL,
                nu_meta_turno_atual      = :meta,
                nu_pecas_proximos_turnos = :proximas,
                dt_fim_turno_calculado   = :dt_fim
            WHERE id_ordem = :id
        """, {
            "meta":     metas["meta_turno_atual"],
            "proximas": metas["pecas_proximos_turnos"],
            "dt_fim":   metas["dt_fim_turno"],
            "id":       ordem_id,
        })
        _set_meta_linha(linha_id, metas["meta_turno_atual"], peca)

    # ── em_producao → fila  (pausa) ───────────────────────────────────────────
    elif new_status == "fila" and status_ant == "em_producao":
        # Recalcula metas para quando for reativada
        metas = calcular_metas_op(linha_id, quantidade)

        run_query_update("""
            UPDATE dbo.tb_ordem_producao
            SET tx_status                = 'fila',
                dt_inicio                = NULL,
                dt_fim                   = NULL,
                nu_meta_turno_atual      = :meta,
                nu_pecas_proximos_turnos = :proximas,
                dt_fim_turno_calculado   = :dt_fim
            WHERE id_ordem = :id
        """, {
            "meta":     metas["meta_turno_atual"],
            "proximas": metas["pecas_proximos_turnos"],
            "dt_fim":   metas["dt_fim_turno"],
            "id":       ordem_id,
        })
        # Limpa meta das máquinas (sem OP ativa = sem meta)
        _set_meta_linha(linha_id, 0)

    # ── → finalizado ─────────────────────────────────────────────────────────
    elif new_status == "finalizado":
        run_query_update("""
            UPDATE dbo.tb_ordem_producao
            SET tx_status = 'finalizado', dt_fim = GETDATE()
            WHERE id_ordem = :id
        """, {"id": ordem_id})

        if status_ant == "em_producao":
            _set_meta_linha(linha_id, 0)
            _ativar_proxima_op(linha_id)

    # ── → cancelado ──────────────────────────────────────────────────────────
    elif new_status == "cancelado":
        run_query_update("""
            UPDATE dbo.tb_ordem_producao
            SET tx_status                = 'cancelado',
                dt_fim                   = GETDATE(),
                nu_meta_turno_atual      = 0,
                nu_pecas_proximos_turnos = 0,
                dt_fim_turno_calculado   = NULL
            WHERE id_ordem = :id
        """, {"id": ordem_id})

        if status_ant == "em_producao":
            _set_meta_linha(linha_id, 0)
            _ativar_proxima_op(linha_id)

    # ── finalizado / cancelado → fila  (reabertura) ───────────────────────────
    else:
        metas = calcular_metas_op(linha_id, quantidade)
        run_query_update("""
            UPDATE dbo.tb_ordem_producao
            SET tx_status                = 'fila',
                dt_inicio                = NULL,
                dt_fim                   = NULL,
                nu_meta_turno_atual      = :meta,
                nu_pecas_proximos_turnos = :proximas,
                dt_fim_turno_calculado   = :dt_fim
            WHERE id_ordem = :id
        """, {
            "meta":     metas["meta_turno_atual"],
            "proximas": metas["pecas_proximos_turnos"],
            "dt_fim":   metas["dt_fim_turno"],
            "id":       ordem_id,
        })

    return {"ok": True}


class ConflictError(Exception):
    """OP em conflito com outra já ativa na linha."""
    pass


def delete_ordem(ordem_id: int) -> dict:
    """Remove uma ordem de produção. Se estava em produção, limpa a meta e ativa próxima."""
    df = run_query("""
        SELECT tx_status, id_linha_producao FROM dbo.tb_ordem_producao WHERE id_ordem = :id
    """, {"id": ordem_id})

    if not df.empty:
        status   = df.iloc[0]["tx_status"]
        linha_id = int(df.iloc[0]["id_linha_producao"])
        if status == "em_producao":
            _set_meta_linha(linha_id, 0)
            run_query_update(
                "DELETE FROM dbo.tb_ordem_producao WHERE id_ordem = :id",
                {"id": ordem_id},
            )
            _ativar_proxima_op(linha_id)
            return {"ok": True}

    run_query_update(
        "DELETE FROM dbo.tb_ordem_producao WHERE id_ordem = :id",
        {"id": ordem_id},
    )
    return {"ok": True}


# ─── Produção Teórica ────────────────────────────────────────────────────────

def get_producao_teorica(machine_id: int) -> int:
    """Retorna a produção teórica (pç/h) configurada para a máquina."""
    _ensure_schema()
    df = run_query("""
        SELECT nu_producao_teorica
        FROM dbo.tb_config_producao_teorica
        WHERE id_ihm = :id
    """, {"id": machine_id})
    return int(df.iloc[0]["nu_producao_teorica"]) if not df.empty else 0


def update_producao_teorica(machine_id: int, value: int) -> None:
    """Salva/atualiza a produção teórica de uma máquina."""
    _ensure_schema()
    run_query_update("""
        MERGE dbo.tb_config_producao_teorica AS tgt
        USING (SELECT :id AS id_ihm, :val AS nu_producao_teorica) AS src
            ON tgt.id_ihm = src.id_ihm
        WHEN MATCHED THEN
            UPDATE SET nu_producao_teorica = src.nu_producao_teorica, dt_updated = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (id_ihm, nu_producao_teorica)
            VALUES (src.id_ihm, src.nu_producao_teorica);
    """, {"id": machine_id, "val": value})


def get_producao_teorica_linha(linha_id: int) -> int:
    """Retorna a soma da produção teórica de todas as máquinas de uma linha."""
    _ensure_schema()
    df = run_query("""
        SELECT COALESCE(SUM(c.nu_producao_teorica), 0) AS total
        FROM dbo.tb_ihm i
        LEFT JOIN dbo.tb_config_producao_teorica c ON c.id_ihm = i.id_ihm
        WHERE i.id_linha_producao = :lid
    """, {"lid": linha_id})
    return int(df.iloc[0]["total"]) if not df.empty else 0


def calcular_metas_op(linha_id: int, quantidade: int) -> dict:
    """
    Calcula meta_turno_atual, pecas_proximos_turnos e dt_fim_turno
    com base na produção teórica da linha e no turno ativo agora.
    """
    _ensure_schema()
    agora = datetime.now()
    prod_teorica = get_producao_teorica_linha(linha_id)

    if prod_teorica <= 0:
        return {
            "meta_turno_atual":      0,
            "pecas_proximos_turnos": quantidade,
            "dt_fim_turno":          None,
        }

    df_turno = run_query("""
        SELECT TOP 1 dt_inicio, dt_fim
        FROM dbo.tb_turnos
        WHERE id_linha_producao = :lid
          AND dt_inicio <= :agora
          AND dt_fim    >= :agora
        ORDER BY dt_inicio
    """, {"lid": linha_id, "agora": agora})

    if df_turno.empty:
        return {
            "meta_turno_atual":      0,
            "pecas_proximos_turnos": quantidade,
            "dt_fim_turno":          None,
        }

    dt_fim_turno    = df_turno.iloc[0]["dt_fim"]
    horas_restantes = max(0.0, (dt_fim_turno - agora).total_seconds() / 3600)
    capacidade      = int(prod_teorica * horas_restantes)

    meta_turno_atual      = min(quantidade, capacidade)
    pecas_proximos_turnos = quantidade - meta_turno_atual

    return {
        "meta_turno_atual":      meta_turno_atual,
        "pecas_proximos_turnos": pecas_proximos_turnos,
        "dt_fim_turno":          dt_fim_turno,
    }


def recalcular_turno_ordens_ativas() -> None:
    """
    Verifica OPs em produção cujo turno calculado já expirou e redistribui
    as peças restantes para o turno seguinte (rollover automático).
    Chamado a cada broadcast do WebSocket de ordens.
    """
    _ensure_schema()
    agora = datetime.now()

    df = run_query("""
        SELECT id_ordem, id_linha_producao,
               nu_meta_turno_atual, nu_pecas_proximos_turnos,
               dt_fim_turno_calculado
        FROM dbo.tb_ordem_producao
        WHERE tx_status = 'em_producao'
          AND nu_pecas_proximos_turnos > 0
          AND dt_fim_turno_calculado IS NOT NULL
          AND dt_fim_turno_calculado < :agora
    """, {"agora": agora})

    for _, op in df.iterrows():
        linha_id       = int(op["id_linha_producao"])
        pecas_restantes = int(op["nu_pecas_proximos_turnos"])

        df_turno = run_query("""
            SELECT TOP 1 dt_inicio, dt_fim
            FROM dbo.tb_turnos
            WHERE id_linha_producao = :lid
              AND dt_inicio <= :agora
              AND dt_fim    >= :agora
            ORDER BY dt_inicio
        """, {"lid": linha_id, "agora": agora})

        if df_turno.empty:
            continue  # sem turno ativo agora, aguarda

        dt_fim_turno    = df_turno.iloc[0]["dt_fim"]
        horas_restantes = max(0.0, (dt_fim_turno - agora).total_seconds() / 3600)
        prod_teorica    = get_producao_teorica_linha(linha_id)
        nova_meta       = int(min(pecas_restantes, prod_teorica * horas_restantes))
        novas_proximas  = pecas_restantes - nova_meta

        run_query_update("""
            UPDATE dbo.tb_ordem_producao
            SET nu_meta_turno_atual      = :meta,
                nu_pecas_proximos_turnos = :proximas,
                dt_fim_turno_calculado   = :dt_fim
            WHERE id_ordem = :id
        """, {
            "meta":     nova_meta,
            "proximas": novas_proximas,
            "dt_fim":   dt_fim_turno,
            "id":       int(op["id_ordem"]),
        })
