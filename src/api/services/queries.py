from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any, Optional
import math
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
            ("nu_produzido",             "INT  NOT NULL DEFAULT 0"),
            ("nu_refugo",                "INT  NOT NULL DEFAULT 0"),
        ]:
            run_query_update(f"""
                IF NOT EXISTS (
                    SELECT * FROM sys.columns
                    WHERE object_id = OBJECT_ID('dbo.tb_ordem_producao')
                      AND name = '{col_def[0]}'
                )
                    ALTER TABLE dbo.tb_ordem_producao ADD {col_def[0]} {col_def[1]}
            """)
        # tb_peca já existe no init.sql — adiciona colunas que faltam
        run_query_update("""
            IF NOT EXISTS (
                SELECT * FROM sys.columns
                WHERE object_id = OBJECT_ID('dbo.tb_peca') AND name = 'id_linha_producao'
            )
                ALTER TABLE dbo.tb_peca ADD id_linha_producao INT NULL
        """)
        # tb_peca_rota
        run_query_update("""
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.tb_peca_rota') AND type = 'U')
            BEGIN
                CREATE TABLE dbo.tb_peca_rota (
                    id_rota             INT IDENTITY(1,1) PRIMARY KEY,
                    id_peca             INT NOT NULL,
                    id_ihm              INT NOT NULL,
                    nu_ordem            INT NOT NULL DEFAULT 0,
                    nu_producao_teorica INT NOT NULL DEFAULT 0
                )
            END
        """)
        # adiciona nu_producao_teorica se a tabela já existia sem ela
        run_query_update("""
            IF NOT EXISTS (
                SELECT * FROM sys.columns
                WHERE object_id = OBJECT_ID('dbo.tb_peca_rota') AND name = 'nu_producao_teorica'
            )
                ALTER TABLE dbo.tb_peca_rota ADD nu_producao_teorica INT NOT NULL DEFAULT 0
        """)
        # id_peca column in tb_ordem_producao
        run_query_update("""
            IF NOT EXISTS (
                SELECT * FROM sys.columns
                WHERE object_id = OBJECT_ID('dbo.tb_ordem_producao') AND name = 'id_peca'
            )
                ALTER TABLE dbo.tb_ordem_producao ADD id_peca INT NULL
        """)
        # tx_tipo_maquina em tb_ihm
        run_query_update("""
            IF NOT EXISTS (
                SELECT * FROM sys.columns
                WHERE object_id = OBJECT_ID('dbo.tb_ihm') AND name = 'tx_tipo_maquina'
            )
                ALTER TABLE dbo.tb_ihm ADD tx_tipo_maquina NVARCHAR(120) NULL
        """)
        # nu_meta_turno em tb_ihm — meta calculada pelo PCP para o turno atual
        run_query_update("""
            IF NOT EXISTS (
                SELECT * FROM sys.columns
                WHERE object_id = OBJECT_ID('dbo.tb_ihm') AND name = 'nu_meta_turno'
            )
                ALTER TABLE dbo.tb_ihm ADD nu_meta_turno INT NOT NULL DEFAULT 0
        """)
        # nu_meta_ativo em tb_ihm — contribuição das OPs ativas no momento (usado para delta acumulativo)
        run_query_update("""
            IF NOT EXISTS (
                SELECT * FROM sys.columns
                WHERE object_id = OBJECT_ID('dbo.tb_ihm') AND name = 'nu_meta_ativo'
            )
                ALTER TABLE dbo.tb_ihm ADD nu_meta_ativo INT NOT NULL DEFAULT 0
        """)
        # tb_op_distribuicao – split de produção entre máquinas do mesmo tipo
        run_query_update("""
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.tb_op_distribuicao') AND type = 'U')
            BEGIN
                CREATE TABLE dbo.tb_op_distribuicao (
                    id_distribuicao  INT IDENTITY(1,1) PRIMARY KEY,
                    id_ordem         INT            NOT NULL,
                    id_ihm           INT            NOT NULL,
                    tx_tipo_maquina  NVARCHAR(120)  NOT NULL,
                    nu_percentual    DECIMAL(5,2)   NOT NULL DEFAULT 100.0,
                    CONSTRAINT UQ_op_dist UNIQUE (id_ordem, id_ihm, tx_tipo_maquina)
                )
            END
        """)
        # tb_turno_modelo – template semanal de turnos (raramente muda)
        run_query_update("""
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.tb_turno_modelo') AND type = 'U')
            BEGIN
                CREATE TABLE dbo.tb_turno_modelo (
                    id_modelo           INT IDENTITY(1,1) PRIMARY KEY,
                    tx_nome             NVARCHAR(120) NOT NULL,
                    id_linha_producao   INT NOT NULL,
                    nu_dia_semana       INT NOT NULL,
                    tm_inicio           TIME NOT NULL,
                    tm_fim              TIME NOT NULL,
                    bl_ativo            BIT NOT NULL DEFAULT 1,
                    dt_created_at       DATETIME2 DEFAULT GETDATE()
                )
            END
        """)
        # tb_turno_ocorrencia – eventos reais de turno (agendado → em_andamento → finalizado)
        run_query_update("""
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.tb_turno_ocorrencia') AND type = 'U')
            BEGIN
                CREATE TABLE dbo.tb_turno_ocorrencia (
                    id_ocorrencia         INT IDENTITY(1,1) PRIMARY KEY,
                    id_modelo             INT NULL,
                    id_linha_producao     INT NOT NULL,
                    tx_nome               NVARCHAR(120) NOT NULL,
                    dt_inicio             DATETIME2 NOT NULL,
                    dt_fim                DATETIME2 NOT NULL,
                    dt_real_inicio        DATETIME2 NULL,
                    dt_real_fim           DATETIME2 NULL,
                    tx_status             NVARCHAR(20) NOT NULL DEFAULT 'agendado',
                    nu_meta               INT NOT NULL DEFAULT 0,
                    nu_produzido          INT NOT NULL DEFAULT 0,
                    nu_pendente_recebido  INT NOT NULL DEFAULT 0,
                    dt_created_at         DATETIME2 DEFAULT GETDATE()
                )
            END
        """)
        run_query_update("""
            IF NOT EXISTS (SELECT * FROM sys.indexes
                           WHERE object_id = OBJECT_ID('dbo.tb_turno_ocorrencia')
                             AND name = 'IX_ocorrencia_linha_status')
                CREATE INDEX IX_ocorrencia_linha_status
                    ON dbo.tb_turno_ocorrencia(id_linha_producao, tx_status)
        """)
        run_query_update("""
            IF NOT EXISTS (SELECT * FROM sys.indexes
                           WHERE object_id = OBJECT_ID('dbo.tb_turno_ocorrencia')
                             AND name = 'IX_ocorrencia_inicio')
                CREATE INDEX IX_ocorrencia_inicio
                    ON dbo.tb_turno_ocorrencia(dt_inicio)
        """)
        # Migra dt_created_at de SYSUTCDATETIME() → GETDATE() para alinhar com
        # datetime.now() (hora local do servidor) e evitar exclusão de dados recentes.
        run_query_update("""
            IF NOT EXISTS (
                SELECT 1 FROM sys.default_constraints
                WHERE name = 'DF_tb_log_registrador_created'
                  AND definition = '(getdate())'
            )
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM sys.default_constraints
                    WHERE name = 'DF_tb_log_registrador_created'
                )
                    ALTER TABLE dbo.tb_log_registrador
                        DROP CONSTRAINT DF_tb_log_registrador_created

                ALTER TABLE dbo.tb_log_registrador
                    ADD CONSTRAINT DF_tb_log_registrador_created
                    DEFAULT (GETDATE()) FOR dt_created_at
            END
        """)
        # Migra registros antigos com timestamp UTC para hora local.
        # Logs gravados com SYSUTCDATETIME() ficam ~3h à frente de GETDATE();
        # a condição WHERE garante idempotência: só converte se ainda estiver no futuro.
        run_query_update("""
            UPDATE dbo.tb_log_registrador
            SET dt_created_at = DATEADD(
                second,
                DATEDIFF(second, SYSUTCDATETIME(), GETDATE()),
                dt_created_at
            )
            WHERE dt_created_at > DATEADD(second, 30, GETDATE())
        """)
        # tb_op_peca_producao – rastreamento individual de peças por OP
        run_query_update("""
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.tb_op_peca_producao') AND type = 'U')
            BEGIN
                CREATE TABLE dbo.tb_op_peca_producao (
                    id_peca_producao  INT IDENTITY(1,1) PRIMARY KEY,
                    id_ordem          INT NOT NULL,
                    nu_peca           INT NOT NULL,
                    nu_etapas_total   INT NOT NULL,
                    nu_etapa_atual    INT NOT NULL,
                    nu_etapa_erro     INT NULL,
                    CONSTRAINT UQ_op_peca UNIQUE (id_ordem, nu_peca)
                )
            END
        """)
        run_query_update("""
            IF NOT EXISTS (SELECT * FROM sys.indexes
                           WHERE object_id = OBJECT_ID('dbo.tb_op_peca_producao')
                             AND name = 'IX_peca_prod_ordem_etapa')
                CREATE INDEX IX_peca_prod_ordem_etapa
                    ON dbo.tb_op_peca_producao(id_ordem, nu_etapa_atual)
                    WHERE nu_etapa_erro IS NULL
        """)
        _schema_ensured = True
    except Exception:
        pass  # não travar se o banco ainda não estiver disponível

def get_machines_by_line_df(line_id: int):
    _ensure_schema()
    df = run_query("""
        SELECT id_ihm, tx_name, COALESCE(tx_tipo_maquina, '') AS tx_tipo_maquina
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
        # Fallback para máquinas sem depara configurado (ex: simuladas)
        _defaults = {
            49: "Em Produção",
            0:  "Parada",
            4:  "Limpeza",
            51: "Ag. Manutentor",
            52: "Em Manutenção",
        }
        for k, v in _defaults.items():
            if k not in depara_status_maquina:
                depara_status_maquina[k] = v

        if "status_maquina" in df_registradores.columns:
            df_registradores["nu_status_maquina"] = df_registradores["status_maquina"].astype("Int64")
            df_registradores["status_maquina"] = df_registradores["nu_status_maquina"].map(depara_status_maquina)

    return df_registradores


def get_machine_shifts(machine_id: int, data_inicio: Optional[Any] = None, data_fim: Optional[Any] = None):
    """Usando o id de uma IHM, retorna os turnos de uma linha de produção filtrado por data ou não.
    Tenta tb_turno_ocorrencia primeiro; fallback para tb_turnos (OEE legado)."""
    _ensure_schema()

    # Busca linha da máquina
    df_ihm_linha = run_query("""
        SELECT id_linha_producao FROM dbo.tb_ihm WHERE id_ihm = :id
    """, {"id": machine_id})

    if not df_ihm_linha.empty:
        lid = int(df_ihm_linha.iloc[0]["id_linha_producao"])
        if not data_inicio or not data_fim:
            df_occ = run_query("""
                SELECT id_ocorrencia AS id, tx_nome AS tx_name,
                       dt_inicio, dt_fim, tx_status,
                       id_linha_producao
                FROM dbo.tb_turno_ocorrencia
                WHERE id_linha_producao = :lid
            """, {"lid": lid})
        else:
            df_occ = run_query("""
                SELECT id_ocorrencia AS id, tx_nome AS tx_name,
                       dt_inicio, dt_fim, tx_status,
                       id_linha_producao
                FROM dbo.tb_turno_ocorrencia
                WHERE id_linha_producao = :lid
                  AND dt_inicio >= :data_inicio
                  AND dt_fim    <= :data_fim
            """, {"lid": lid, "data_inicio": data_inicio, "data_fim": data_fim})

        if not df_occ.empty:
            df_ihms = run_query("SELECT id_ihm, tx_name, id_linha_producao FROM tb_ihm")
            df_occ = df_occ.merge(df_ihms, how="left", on="id_linha_producao")
            return df_occ

    # Fallback legado: tb_turnos (necessário para OEE)
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

    df_ihms = run_query("SELECT id_ihm, tx_name, id_linha_producao FROM tb_ihm")
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
        # Fallback: lê diretamente da coluna nu_meta_turno de tb_ihm
        try:
            df_ihm = run_query("""
                SELECT nu_meta_turno FROM dbo.tb_ihm WHERE id_ihm = :id
            """, {"id": machine_id})
            if not df_ihm.empty:
                return int(df_ihm.iloc[0]["nu_meta_turno"])
        except Exception:
            pass
        return 0


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
    Se não houver nenhum turno hoje, retorna (início do dia, agora).
    Lê de tb_turno_ocorrencia; fallback para tb_turnos se vazio."""
    # Busca linha da máquina
    df_ihm = run_query("""
        SELECT id_linha_producao FROM dbo.tb_ihm WHERE id_ihm = :id
    """, {"id": machine_id})

    if df_ihm.empty:
        return datetime.combine(agora.date(), time(0, 0)), agora

    lid = int(df_ihm.iloc[0]["id_linha_producao"])

    # Turno em andamento
    df = run_query("""
        SELECT TOP 1 dt_inicio, dt_fim
        FROM dbo.tb_turno_ocorrencia
        WHERE id_linha_producao = :lid AND tx_status = 'em_andamento'
        ORDER BY dt_inicio
    """, {"lid": lid})

    if not df.empty:
        return df.iloc[0]["dt_inicio"], df.iloc[0]["dt_fim"]

    # Último turno finalizado hoje
    df2 = run_query("""
        SELECT TOP 1 dt_inicio, dt_fim
        FROM dbo.tb_turno_ocorrencia
        WHERE id_linha_producao = :lid
          AND tx_status = 'finalizado'
          AND CAST(dt_real_fim AS DATE) = CAST(:agora AS DATE)
        ORDER BY dt_real_fim DESC
    """, {"lid": lid, "agora": agora})

    if not df2.empty:
        return df2.iloc[0]["dt_inicio"], df2.iloc[0]["dt_fim"]

    # Fallback legacy: tb_turnos (compatibilidade com dados antigos / primeiro run)
    df3 = run_query("""
        SELECT TOP 1 t.dt_inicio, t.dt_fim
        FROM dbo.tb_turnos t
        JOIN dbo.tb_ihm i ON i.id_linha_producao = t.id_linha_producao
        WHERE i.id_ihm = :id
          AND t.dt_inicio <= :agora
          AND t.dt_fim    >= :agora
        ORDER BY t.dt_inicio
    """, {"id": machine_id, "agora": agora})

    if not df3.empty:
        return df3.iloc[0]["dt_inicio"], df3.iloc[0]["dt_fim"]

    # Fallback: início do dia até agora
    return datetime.combine(agora.date(), time(0, 0)), agora


def get_metrics_machine(machine_id: int, data_inicio: Optional[Any] = None, data_fim: Optional[Any] = None) -> Dict[str, Any]:
    """Retorna as principais informações de uma IHM para o turno atual (ou período informado)."""
    try:
        agora = datetime.now()

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
            # Sem dados do simulador: máquina parada, mas meta definida pelo PCP
            df_ihm_meta = run_query("""
                SELECT nu_meta_turno FROM dbo.tb_ihm WHERE id_ihm = :id
            """, {"id": machine_id})
            meta_pcp = int(df_ihm_meta.iloc[0]["nu_meta_turno"]) if not df_ihm_meta.empty else 0
            return {
                "status_maquina": "Parada", "oee": 0, "disponibilidade": 0,
                "performance": 0, "qualidade": 0, "meta": meta_pcp,
                "produzido": 0, "reprovado": 0, "total_produzido": 0,
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
        SELECT i.id_ihm, i.tx_name, l.tx_name AS linha_nome,
               COALESCE(i.tx_tipo_maquina, '') AS tx_tipo_maquina
        FROM dbo.tb_ihm i
        JOIN dbo.tb_linha_producao l ON l.id_linha_producao = i.id_linha_producao
        ORDER BY i.id_ihm
    """)
    return [
        {
            "id": int(r["id_ihm"]),
            "nome": r["tx_name"],
            "linha": r["linha_nome"],
            "tipo_maquina": r["tx_tipo_maquina"],
        }
        for _, r in df.iterrows()
    ]


def update_machine_tipo(machine_id: int, tipo: str) -> None:
    """Atualiza o tipo da máquina (usado para agrupar máquinas intercambiáveis)."""
    _ensure_schema()
    run_query_update(
        "UPDATE dbo.tb_ihm SET tx_tipo_maquina = :tipo WHERE id_ihm = :id",
        {"tipo": tipo.strip() if tipo else None, "id": machine_id},
    )


def get_line_shifts(line_id: int) -> dict:
    """Retorna nome da linha e lista de turnos configurados (lê de tb_turno_modelo)."""
    _ensure_schema()
    df_linha = run_query("""
        SELECT id_linha_producao, tx_name
        FROM dbo.tb_linha_producao
        WHERE id_linha_producao = :id
    """, {"id": line_id})

    if df_linha.empty:
        return {"erro": f"Linha {line_id} não encontrada"}

    nome_linha = df_linha.iloc[0]["tx_name"]

    df_modelos = run_query("""
        SELECT tx_nome, nu_dia_semana, tm_inicio, tm_fim, bl_ativo
        FROM dbo.tb_turno_modelo
        WHERE id_linha_producao = :linha
        ORDER BY nu_dia_semana, tm_inicio
    """, {"linha": line_id})

    turnos: list = []
    if not df_modelos.empty:
        for _, t in df_modelos.iterrows():
            dow = int(t["nu_dia_semana"])
            # tm_inicio / tm_fim podem vir como datetime.time ou timedelta (SQL Server)
            def _fmt_time(v):
                if hasattr(v, "strftime"):
                    return v.strftime("%H:%M")
                # timedelta (pyodbc retorna assim às vezes)
                total = int(v.total_seconds())
                return f"{total // 3600:02d}:{(total % 3600) // 60:02d}"
            turnos.append({
                "dia":    _DIAS_SEMANA[dow] if 0 <= dow <= 6 else str(dow),
                "nome":   t["tx_nome"],
                "inicio": _fmt_time(t["tm_inicio"]),
                "fim":    _fmt_time(t["tm_fim"]),
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
    """Salva a lista de turnos de uma linha em tb_turno_modelo e gera ocorrências futuras."""
    _ensure_schema()
    dow_map = {d: i for i, d in enumerate(_DIAS_SEMANA)}

    # 1. Substitui modelos da linha
    run_query_update(
        "DELETE FROM dbo.tb_turno_modelo WHERE id_linha_producao = :linha",
        {"linha": line_id},
    )

    for entry in turnos:
        dow_target = dow_map.get(entry["dia"])
        if dow_target is None:
            continue
        nome_turno = entry.get("nome") or f"TURNO_{entry['dia'][:3].upper()}"
        ativo = 1 if entry.get("ativo", False) else 0
        run_query_update("""
            INSERT INTO dbo.tb_turno_modelo
                (tx_nome, id_linha_producao, nu_dia_semana, tm_inicio, tm_fim, bl_ativo)
            VALUES (:nome, :linha, :dow, :ini, :fim, :ativo)
        """, {
            "nome":  nome_turno,
            "linha": line_id,
            "dow":   dow_target,
            "ini":   entry["inicio"],   # 'HH:MM' — SQL Server aceita como TIME
            "fim":   entry["fim"],
            "ativo": ativo,
        })

    # 2. Gera ocorrências baseadas nos novos modelos
    _ensure_ocorrencias_futuras(line_id)

    return {"ok": True}


# ─── Gerenciamento de ocorrências de turno ────────────────────────────────────

def _ensure_ocorrencias_futuras(linha_id: int) -> None:
    """Gera ocorrências de turno para a janela [hoje-1 dia, hoje+4 semanas]
    com base nos modelos ativos da linha. Pula se já existir para (id_modelo, dt_inicio)."""
    _ensure_schema()
    agora   = datetime.now()
    w_start = agora.date() - timedelta(days=1)
    w_end   = agora.date() + timedelta(weeks=4)

    df_modelos = run_query("""
        SELECT id_modelo, tx_nome, nu_dia_semana, tm_inicio, tm_fim
        FROM dbo.tb_turno_modelo
        WHERE id_linha_producao = :lid AND bl_ativo = 1
    """, {"lid": linha_id})

    if df_modelos.empty:
        return

    for _, m in df_modelos.iterrows():
        id_modelo = int(m["id_modelo"])
        dow_target = int(m["nu_dia_semana"])
        nome_turno = m["tx_nome"]

        # Converte TIME (pode vir como datetime.time ou timedelta)
        def _to_hm(v):
            if hasattr(v, "hour"):
                return v.hour, v.minute
            total = int(v.total_seconds())
            return total // 3600, (total % 3600) // 60

        hi, hm = _to_hm(m["tm_inicio"])
        fi, fm = _to_hm(m["tm_fim"])

        # Primeira ocorrência na janela
        days_to_first = (dow_target - w_start.weekday()) % 7
        current_date  = w_start + timedelta(days=days_to_first)

        while current_date <= w_end:
            dt_inicio   = datetime.combine(current_date, time(hi, hm))
            dt_fim_base = datetime.combine(current_date, time(fi, fm))
            dt_fim      = dt_fim_base + timedelta(days=1) if (fi, fm) < (hi, hm) else dt_fim_base

            run_query_update("""
                IF NOT EXISTS (
                    SELECT 1 FROM dbo.tb_turno_ocorrencia
                    WHERE id_modelo = :mid AND dt_inicio = :di
                )
                INSERT INTO dbo.tb_turno_ocorrencia
                    (id_modelo, id_linha_producao, tx_nome, dt_inicio, dt_fim, tx_status)
                VALUES (:mid, :lid, :nome, :di, :df, 'agendado')
            """, {
                "mid":  id_modelo,
                "lid":  linha_id,
                "nome": nome_turno,
                "di":   dt_inicio,
                "df":   dt_fim,
            })

            current_date += timedelta(weeks=1)


def _abrir_turno(id_ocorrencia: int, linha_id: int) -> None:
    """Abre um turno agendado: seta status=em_andamento e calcula meta das OPs ativas."""
    agora = datetime.now()

    df_meta = run_query("""
        SELECT COALESCE(SUM(nu_meta_turno_atual), 0) AS total
        FROM dbo.tb_ordem_producao
        WHERE id_linha_producao = :lid AND tx_status = 'em_producao'
    """, {"lid": linha_id})
    nu_meta = int(df_meta.iloc[0]["total"]) if not df_meta.empty else 0

    run_query_update("""
        UPDATE dbo.tb_turno_ocorrencia
        SET tx_status = 'em_andamento',
            dt_real_inicio = :agora,
            nu_meta = :meta
        WHERE id_ocorrencia = :id
    """, {"agora": agora, "meta": nu_meta, "id": id_ocorrencia})

    # Reseta meta das máquinas ao iniciar novo turno
    run_query_update("""
        UPDATE dbo.tb_ihm SET nu_meta_turno = 0, nu_meta_ativo = 0
        WHERE id_linha_producao = :lid
    """, {"lid": linha_id})


def _fechar_turno(id_ocorrencia: int, linha_id: int) -> None:
    """Fecha um turno em_andamento: registra produção real e seta status=finalizado."""
    agora = datetime.now()

    df = run_query("""
        SELECT dt_real_inicio FROM dbo.tb_turno_ocorrencia
        WHERE id_ocorrencia = :id
    """, {"id": id_ocorrencia})

    if df.empty or df.iloc[0]["dt_real_inicio"] is None:
        nu_produzido = 0
    else:
        dt_inicio_real = df.iloc[0]["dt_real_inicio"]
        nu_produzido = _get_producao_linha_desde(linha_id, dt_inicio_real)

    run_query_update("""
        UPDATE dbo.tb_turno_ocorrencia
        SET tx_status = 'finalizado',
            dt_real_fim = :agora,
            nu_produzido = :prod
        WHERE id_ocorrencia = :id
    """, {"agora": agora, "prod": nu_produzido, "id": id_ocorrencia})


def get_historico_turnos(linha_id: int, limit: int = 20) -> list:
    """Retorna o histórico de ocorrências de turno de uma linha."""
    _ensure_schema()
    df = run_query("""
        SELECT TOP (:lim) id_ocorrencia, tx_nome, dt_inicio, dt_fim,
               dt_real_inicio, dt_real_fim, tx_status,
               nu_meta, nu_produzido, nu_pendente_recebido
        FROM dbo.tb_turno_ocorrencia
        WHERE id_linha_producao = :lid
        ORDER BY dt_inicio DESC
    """, {"lid": linha_id, "lim": limit})

    if df.empty:
        return []

    result = []
    for _, r in df.iterrows():
        result.append({
            "id_ocorrencia":        int(r["id_ocorrencia"]),
            "nome":                 r["tx_nome"],
            "dt_inicio":            r["dt_inicio"].isoformat() if r["dt_inicio"] is not None else None,
            "dt_fim":               r["dt_fim"].isoformat()    if r["dt_fim"]    is not None else None,
            "dt_real_inicio":       r["dt_real_inicio"].isoformat() if r["dt_real_inicio"] is not None else None,
            "dt_real_fim":          r["dt_real_fim"].isoformat()    if r["dt_real_fim"]    is not None else None,
            "status":               r["tx_status"],
            "meta":                 int(r["nu_meta"]),
            "produzido":            int(r["nu_produzido"]),
            "pendente_recebido":    int(r["nu_pendente_recebido"]),
        })
    return result


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
    """Informações do turno atual (lê de tb_turno_ocorrencia)."""
    _ensure_schema()
    agora_ov = datetime.now()
    df = run_query("""
        SELECT TOP 1 id_ocorrencia, tx_nome, dt_inicio, dt_fim, nu_meta
        FROM dbo.tb_turno_ocorrencia
        WHERE dt_inicio <= :agora AND dt_fim >= :agora
          AND tx_status IN ('em_andamento', 'agendado')
        ORDER BY dt_inicio
    """, {"agora": agora_ov})

    if df.empty:
        return {"nome": "-", "encerra_em": "-", "progresso_pct": 0, "nu_meta": 0}

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
        "nome":          row["tx_nome"],
        "encerra_em":    encerra_em,
        "progresso_pct": min(100, max(0, progresso)),
        "nu_meta":       int(row["nu_meta"]),
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
            reprovado = metrics["reprovado"] if isinstance(metrics["reprovado"], (int, float)) else 0
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
                "reprovado":       reprovado,
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
                delta      = datetime.now() - df_parada.iloc[0]["dt_created_at"]
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
                tx_observacoes    VARCHAR(500) NULL,
                nu_produzido      INT          NOT NULL DEFAULT 0,
                nu_refugo         INT          NOT NULL DEFAULT 0
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
            o.nu_pecas_proximos_turnos,
            o.id_peca,
            o.nu_produzido,
            o.nu_refugo
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
            "peca_id":               int(r["id_peca"]) if r["id_peca"] is not None and not pd.isna(r["id_peca"]) else None,
            "status":                r["tx_status"],
            "prioridade":            int(r["nu_prioridade"]),
            "dt_criacao":            r["dt_criacao"].isoformat() if r["dt_criacao"] is not None else None,
            "dt_inicio":             r["dt_inicio"].isoformat()  if r["dt_inicio"]  is not None else None,
            "dt_fim":                r["dt_fim"].isoformat()      if r["dt_fim"]     is not None else None,
            "observacoes":           r["tx_observacoes"],
            "produzido":             int(r["nu_produzido"]) if r.get("nu_produzido") is not None and not pd.isna(r["nu_produzido"]) else 0,
            "refugo":                int(r["nu_refugo"])    if r.get("nu_refugo")    is not None and not pd.isna(r["nu_refugo"])    else 0,
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


def create_ordem(numero_op, linha_id, peca, quantidade, prioridade, observacoes, peca_id: int = None) -> int:
    """Cria nova ordem de produção na fila (sem calcular metas) e retorna o id gerado."""
    _ensure_schema()
    return run_query_insert("""
        INSERT INTO dbo.tb_ordem_producao
            (nu_numero_op, id_linha_producao, tx_peca, nu_quantidade,
             nu_meta_hora, nu_prioridade, tx_observacoes,
             nu_meta_turno_atual, nu_pecas_proximos_turnos, dt_fim_turno_calculado, id_peca)
        OUTPUT INSERTED.id_ordem
        VALUES (:num, :linha, :peca, :qtd,
                0, :pri, :obs,
                0, :qtd, NULL, :peca_id)
    """, {
        "num":     numero_op,
        "linha":   linha_id,
        "peca":    peca,
        "qtd":     quantidade,
        "pri":     prioridade,
        "obs":     observacoes or None,
        "peca_id": peca_id,
    })


STATUSES_VALIDOS = {"fila", "em_producao", "finalizado", "cancelado"}


# ─── Helpers internos de OP ──────────────────────────────────────────────────

def _recalcular_metas_linha(linha_id: int) -> None:
    """
    Recalcula e aplica a meta de cada máquina como SOMA das contribuições
    de todas as OPs em_producao da linha. Deve ser chamado sempre que uma OP
    mudar de status nesta linha.

    Regras:
    - Sem OPs ativas → zera nu_meta_turno e nu_meta_ativo de todas as máquinas.
    - Máquinas paralelas (mesmo tipo_maquina): a meta é dividida proporcionalmente
      à producao_teorica de cada uma, salvo se houver distribuição manual salva
      em tb_op_distribuicao.
    - Por OP: contrib de cada máquina = min(meta_op * pct/100, cap_máquina_no_turno).
    - Múltiplas OPs: contribuições se somam, capadas pela capacidade da máquina.
    - Atribuição direta: nu_meta_turno = nu_meta_ativo = contribuição calculada.
    """
    horas = _get_horas_restantes_turno(linha_id)

    df_ops = run_query("""
        SELECT id_ordem, tx_peca, id_peca, nu_meta_turno_atual, nu_quantidade
        FROM dbo.tb_ordem_producao
        WHERE id_linha_producao = :lid AND tx_status = 'em_producao'
    """, {"lid": linha_id})

    if df_ops.empty:
        # Sem OPs ativas: zera meta de todas as máquinas da linha
        df_curr_empty = run_query("""
            SELECT id_ihm FROM dbo.tb_ihm WHERE id_linha_producao = :lid
        """, {"lid": linha_id})
        for _, row in df_curr_empty.iterrows():
            iid = int(row["id_ihm"])
            try:
                run_query_update("""
                    UPDATE dbo.tb_ihm SET nu_meta_turno = 0, nu_meta_ativo = 0 WHERE id_ihm = :id
                """, {"id": iid})
                update_machine_config(iid, 0, get_selected_piece(iid))
            except Exception:
                pass
        return

    # Carrega todas as máquinas da linha com producao_teorica, agrupadas por tipo
    df_linha = run_query("""
        SELECT i.id_ihm, COALESCE(i.tx_tipo_maquina, '') AS tx_tipo_maquina,
               COALESCE(c.nu_producao_teorica, 0) AS nu_producao_teorica
        FROM dbo.tb_ihm i
        LEFT JOIN dbo.tb_config_producao_teorica c ON c.id_ihm = i.id_ihm
        WHERE i.id_linha_producao = :lid
    """, {"lid": linha_id})
    maquinas_por_tipo: dict = {}
    for _, m in df_linha.iterrows():
        t = m["tx_tipo_maquina"]
        if t:
            maquinas_por_tipo.setdefault(t, []).append({
                "id_ihm": int(m["id_ihm"]),
                "producao_teorica": int(m["nu_producao_teorica"]),
            })

    metas: dict = {}       # id_ihm -> meta_soma
    caps: dict = {}        # id_ihm -> capacidade máxima no turno
    pecas_nome: dict = {}  # id_ihm -> último nome de peça

    for _, op in df_ops.iterrows():
        peca_id    = int(op["id_peca"]) if op["id_peca"] is not None and not pd.isna(op["id_peca"]) else None
        pn         = op["tx_peca"]
        meta_turno = int(op["nu_meta_turno_atual"])
        quantidade = int(op["nu_quantidade"])
        # Sem turno ativo, meta_turno é 0 → usa a quantidade total da OP como meta
        meta_op    = meta_turno if meta_turno > 0 else quantidade
        op_id      = int(op["id_ordem"])

        if peca_id:
            rota = get_rota_peca(peca_id)

            # Producao_teorica por máquina a partir da rota (tb_peca_rota tem prioridade)
            route_prod = {step["id_ihm"]: step["producao_teorica"] for step in rota}

            # Distribuição manual salva para esta OP
            df_dist = run_query("""
                SELECT id_ihm, tx_tipo_maquina, nu_percentual
                FROM dbo.tb_op_distribuicao
                WHERE id_ordem = :id
            """, {"id": op_id})
            dist_map: dict = {}
            if not df_dist.empty:
                for _, d in df_dist.iterrows():
                    dist_map[(int(d["id_ihm"]), d["tx_tipo_maquina"])] = float(d["nu_percentual"])

            seen_tipos: set = set()
            for step in rota:
                tipo = step["tipo_maquina"]

                if tipo and tipo in seen_tipos:
                    continue

                if tipo and tipo in maquinas_por_tipo:
                    seen_tipos.add(tipo)
                    alternativas = maquinas_por_tipo[tipo]

                    total_pct  = sum(dist_map.get((m["id_ihm"], tipo), 0.0) for m in alternativas)
                    # Usa producao_teorica da rota quando disponível
                    total_prod = sum(route_prod.get(m["id_ihm"]) or m["producao_teorica"] for m in alternativas)

                    # Coleta dados por máquina para aplicar LRM
                    machines_data = []
                    for m in alternativas:
                        iid         = m["id_ihm"]
                        prod_m      = route_prod.get(iid) or m["producao_teorica"]
                        cap_maquina = int(prod_m * horas)
                        caps[iid]   = cap_maquina

                        if total_pct > 0:
                            pct = dist_map.get((iid, tipo), 0.0)
                        elif total_prod > 0:
                            pct = 100.0 * prod_m / total_prod
                        else:
                            pct = 100.0 if iid == step["id_ihm"] else 0.0

                        machines_data.append((iid, pct, cap_maquina))

                    # Largest Remainder Method: garante que soma == meta_op
                    raw_vals = [(iid, meta_op * pct / 100, cap) for iid, pct, cap in machines_data]
                    floors   = [(iid, math.floor(val), val - math.floor(val), cap)
                                for iid, val, cap in raw_vals]
                    remainder = meta_op - sum(f[1] for f in floors)
                    # Ordena por fração decrescente; desempate por iid (menor primeiro = mais prioritário)
                    sorted_f  = sorted(floors, key=lambda x: (-x[2], x[0]))
                    contribs  = {}
                    for i, (iid, fl, frac, cap) in enumerate(sorted_f):
                        extra = 1 if i < remainder else 0
                        contribs[iid] = min(fl + extra, cap)

                    for iid, pct, cap in machines_data:
                        metas[iid]      = metas.get(iid, 0) + contribs[iid]
                        pecas_nome[iid] = pn
                else:
                    # Máquina sem tipo definido ou sem paralelas — usa direto da rota
                    iid         = step["id_ihm"]
                    cap_maquina = int(step.get("producao_teorica", 0) * horas)
                    caps[iid]   = cap_maquina
                    contrib     = min(meta_op, cap_maquina)
                    metas[iid]      = metas.get(iid, 0) + contrib
                    pecas_nome[iid] = pn
        else:
            # Sem roteiro configurado: distribui meta_op em todas as máquinas da linha
            df_m = run_query("SELECT id_ihm FROM dbo.tb_ihm WHERE id_linha_producao = :lid",
                             {"lid": linha_id})
            for _, m in df_m.iterrows():
                iid = int(m["id_ihm"])
                metas[iid]      = metas.get(iid, 0) + meta_op
                pecas_nome[iid] = pn

    # Garante que a soma de múltiplas OPs não ultrapassa a capacidade da máquina
    for iid in metas:
        if iid in caps:
            metas[iid] = min(metas[iid], caps[iid])

    all_iids = {int(m["id_ihm"]) for _, m in df_linha.iterrows()}

    # Aplica metas diretamente — sem fórmula delta para evitar duplicações
    for iid, new_meta in metas.items():
        try:
            run_query_update("""
                UPDATE dbo.tb_ihm SET nu_meta_turno = :meta, nu_meta_ativo = :meta WHERE id_ihm = :id
            """, {"meta": new_meta, "id": iid})
        except Exception:
            pass
        try:
            update_machine_config(iid, new_meta, pecas_nome.get(iid, ""))
        except Exception:
            pass

    # Máquinas sem contribuição ativa: zera meta
    for iid in all_iids - set(metas.keys()):
        try:
            run_query_update("""
                UPDATE dbo.tb_ihm SET nu_meta_turno = 0, nu_meta_ativo = 0 WHERE id_ihm = :id
            """, {"id": iid})
            update_machine_config(iid, 0, pecas_nome.get(iid, ""))
        except Exception:
            pass


def _set_meta_linha(linha_id: int, meta: int, peca: str = None) -> None:
    """Zera a meta de todas as máquinas de uma linha (chamado quando não há OPs ativas).
    Se peca=None, mantém a peça atual de cada máquina."""
    try:
        run_query_update("""
            UPDATE dbo.tb_ihm SET nu_meta_turno = :meta
            WHERE id_linha_producao = :lid
        """, {"meta": meta, "lid": linha_id})
    except Exception:
        pass
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
        SELECT TOP 1 id_ordem, nu_quantidade, tx_peca, id_peca
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
    peca_id    = int(r["id_peca"]) if r["id_peca"] is not None and not pd.isna(r["id_peca"]) else None

    # Recalcula metas com base no momento atual
    metas = calcular_metas_op(linha_id, quantidade, peca_id)

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
    # Recalcula metas das máquinas somando todas as OPs ativas da linha
    _recalcular_metas_linha(linha_id)
    # Inicializa rastreamento de peças
    n_etapas = _get_n_etapas(peca_id)
    if n_etapas > 0:
        _init_op_pecas(prox_id, quantidade, n_etapas)


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
        SELECT tx_status, id_linha_producao, nu_quantidade, tx_peca, id_peca, dt_inicio
        FROM dbo.tb_ordem_producao WHERE id_ordem = :id
    """, {"id": ordem_id})
    if df_op.empty:
        raise ValueError(f"OP {ordem_id} não encontrada")

    r           = df_op.iloc[0]
    status_ant  = r["tx_status"]
    linha_id    = int(r["id_linha_producao"])
    quantidade  = int(r["nu_quantidade"])
    peca        = r["tx_peca"]
    peca_id     = int(r["id_peca"]) if r["id_peca"] is not None and not pd.isna(r["id_peca"]) else None
    dt_inicio   = r["dt_inicio"]

    # ── fila / finalizado → em_producao ──────────────────────────────────────
    if new_status == "em_producao":
        # Recalcula metas com base no momento atual (não na criação)
        metas = calcular_metas_op(linha_id, quantidade, peca_id)

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
        # Recalcula meta das máquinas somando todas as OPs ativas da linha
        _recalcular_metas_linha(linha_id)
        # Inicializa rastreamento de peças
        n_etapas = _get_n_etapas(peca_id)
        if n_etapas > 0:
            _init_op_pecas(ordem_id, quantidade, n_etapas)

    # ── em_producao → fila  (pausa) ───────────────────────────────────────────
    elif new_status == "fila" and status_ant == "em_producao":
        # Recalcula metas para quando for reativada
        metas = calcular_metas_op(linha_id, quantidade, peca_id)

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
        # Recalcula meta das máquinas (remove a contribuição desta OP)
        _recalcular_metas_linha(linha_id)

    # ── → finalizado ─────────────────────────────────────────────────────────
    elif new_status == "finalizado":
        producao = (
            _get_producao_refugo_op(linha_id, dt_inicio, peca_id)
            if dt_inicio is not None
            else {"produzido": 0, "refugo": 0}
        )
        run_query_update("""
            UPDATE dbo.tb_ordem_producao
            SET tx_status                = 'finalizado',
                dt_fim                   = GETDATE(),
                nu_produzido             = :prod,
                nu_refugo                = :refugo,
                nu_meta_turno_atual      = 0,
                nu_pecas_proximos_turnos = 0
            WHERE id_ordem = :id
        """, {"prod": producao["produzido"], "refugo": producao["refugo"], "id": ordem_id})

        # Operações secundárias — não devem reverter a finalização se falharem
        try:
            if status_ant == "em_producao":
                _recalcular_metas_linha(linha_id)
                _ativar_proxima_op(linha_id)
        except Exception:
            pass

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
            _recalcular_metas_linha(linha_id)
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
            run_query_update(
                "DELETE FROM dbo.tb_ordem_producao WHERE id_ordem = :id",
                {"id": ordem_id},
            )
            _recalcular_metas_linha(linha_id)
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


def calcular_metas_op(linha_id: int, quantidade: int, peca_id: int = None) -> dict:
    """
    Calcula meta_turno_atual, pecas_proximos_turnos e dt_fim_turno.

    Capacidade de cada etapa sequencial do roteiro:
      - Máquinas do MESMO tipo na linha trabalham em PARALELO → suas capacidades se SOMAM.
      - Etapas de tipos DIFERENTES são sequenciais → o gargalo é o MÍNIMO entre elas.

    Sem peca_id, usa a soma total da linha (compatibilidade).
    """
    _ensure_schema()
    agora = datetime.now()

    # Busca turno ativo em tb_turno_ocorrencia
    # Considera 'em_andamento' e 'agendado' dentro da janela (evita race condition do tick)
    df_turno = run_query("""
        SELECT TOP 1 dt_inicio, dt_fim
        FROM dbo.tb_turno_ocorrencia
        WHERE id_linha_producao = :lid
          AND dt_inicio <= :agora AND dt_fim >= :agora
          AND tx_status IN ('em_andamento', 'agendado')
        ORDER BY dt_inicio
    """, {"lid": linha_id, "agora": agora})

    # Fallback legacy: tb_turnos
    if df_turno.empty:
        df_turno = run_query("""
            SELECT TOP 1 dt_inicio, dt_fim
            FROM dbo.tb_turnos
            WHERE id_linha_producao = :lid
              AND dt_inicio <= :agora
              AND dt_fim    >= :agora
            ORDER BY dt_inicio
        """, {"lid": linha_id, "agora": agora})

    if df_turno.empty:
        return {"meta_turno_atual": 0, "pecas_proximos_turnos": quantidade, "dt_fim_turno": None}

    dt_fim_turno    = df_turno.iloc[0]["dt_fim"]
    horas_restantes = max(0.0, (dt_fim_turno - agora).total_seconds() / 3600)

    if peca_id:
        rota = get_rota_peca(peca_id)
        if not rota:
            return {"meta_turno_atual": 0, "pecas_proximos_turnos": quantidade, "dt_fim_turno": None}

        # Mapa de producao_teorica por máquina a partir da rota (tb_peca_rota tem prioridade)
        route_prod = {step["id_ihm"]: step["producao_teorica"] for step in rota}

        # Soma capacidade de todas as máquinas de cada tipo na linha (paralelas somam)
        df_linha = run_query("""
            SELECT i.id_ihm, COALESCE(i.tx_tipo_maquina, '') AS tx_tipo_maquina,
                   COALESCE(c.nu_producao_teorica, 0) AS nu_producao_teorica
            FROM dbo.tb_ihm i
            LEFT JOIN dbo.tb_config_producao_teorica c ON c.id_ihm = i.id_ihm
            WHERE i.id_linha_producao = :lid
        """, {"lid": linha_id})
        cap_por_tipo: dict = {}  # tipo -> soma das capacidades das máquinas paralelas
        for _, m in df_linha.iterrows():
            t = m["tx_tipo_maquina"]
            if t:
                iid = int(m["id_ihm"])
                prod = route_prod.get(iid) or int(m["nu_producao_teorica"])
                cap_por_tipo[t] = cap_por_tipo.get(t, 0) + prod

        # Percorre o roteiro: cada tipo aparece uma só vez; gargalo = mínimo entre tipos
        seen_tipos: set = set()
        caps_sequenciais: list = []
        for step in rota:
            tipo = step["tipo_maquina"]
            key  = tipo if tipo else str(step["id_ihm"])
            if key in seen_tipos:
                continue
            seen_tipos.add(key)
            if tipo and tipo in cap_por_tipo:
                caps_sequenciais.append(cap_por_tipo[tipo])
            else:
                # Máquina sem tipo: usa producao_teorica do próprio step
                c = step.get("producao_teorica", 0)
                if c > 0:
                    caps_sequenciais.append(c)

        if not caps_sequenciais or not any(c > 0 for c in caps_sequenciais):
            return {"meta_turno_atual": 0, "pecas_proximos_turnos": quantidade, "dt_fim_turno": None}

        gargalo   = min(c for c in caps_sequenciais if c > 0)
        capacidade = int(gargalo * horas_restantes)
    else:
        prod_teorica = get_producao_teorica_linha(linha_id)
        if prod_teorica <= 0:
            return {"meta_turno_atual": 0, "pecas_proximos_turnos": quantidade, "dt_fim_turno": None}
        capacidade = int(prod_teorica * horas_restantes)

    meta_turno_atual      = min(quantidade, capacidade)
    pecas_proximos_turnos = quantidade - meta_turno_atual

    return {
        "meta_turno_atual":      meta_turno_atual,
        "pecas_proximos_turnos": pecas_proximos_turnos,
        "dt_fim_turno":          dt_fim_turno,
    }


def _get_producao_linha_desde(linha_id: int, dt_inicio: datetime) -> int:
    """Soma a produção real de todas as máquinas da linha desde dt_inicio.
    Usa o delta do registrador 'total_produzido' (acumulador) por máquina."""
    df_maquinas = run_query("""
        SELECT id_ihm FROM dbo.tb_ihm WHERE id_linha_producao = :lid
    """, {"lid": linha_id})
    if df_maquinas.empty:
        return 0
    total = 0
    for _, m in df_maquinas.iterrows():
        df = run_query("""
            SELECT MIN(lr.nu_valor_bruto) AS val_inicio,
                   MAX(lr.nu_valor_bruto) AS val_fim
            FROM dbo.tb_log_registrador lr
            JOIN dbo.tb_registrador r ON r.id_registrador = lr.id_registrador
            WHERE lr.id_ihm      = :id
              AND r.tx_descricao = 'total_produzido'
              AND lr.dt_created_at >= :dt_inicio
        """, {"id": int(m["id_ihm"]), "dt_inicio": dt_inicio})
        if not df.empty and df.iloc[0]["val_inicio"] is not None:
            delta = float(df.iloc[0]["val_fim"]) - float(df.iloc[0]["val_inicio"])
            if delta > 0:
                total += int(delta)
    return total


def _get_terminal_ihms(peca_id: int) -> list:
    """Retorna os IDs das IHMs terminais do roteiro (última etapa = max nu_ordem)."""
    df = run_query("""
        SELECT id_ihm, nu_ordem
        FROM dbo.tb_peca_rota
        WHERE id_peca = :id
    """, {"id": peca_id})
    if df.empty:
        return []
    max_ordem = int(df["nu_ordem"].max())
    return [int(r["id_ihm"]) for _, r in df.iterrows() if int(r["nu_ordem"]) == max_ordem]


def _get_producao_refugo_op(linha_id: int, dt_inicio: datetime, peca_id: int = None) -> dict:
    """Retorna {produzido, refugo} contando apenas as IHMs terminais do roteiro da peça.

    Somente a última etapa do roteiro representa peças acabadas — a mesma peça
    passa por múltiplas máquinas, então somar todas as etapas multiplicaria a contagem.
    Quando peca_id não é fornecido (sem roteiro configurado), usa todas as máquinas
    da linha como fallback.
    """
    terminal_ihms: list = []
    if peca_id:
        terminal_ihms = _get_terminal_ihms(peca_id)

    if not terminal_ihms:
        # Fallback: sem roteiro configurado — usa todas as máquinas da linha
        df_maquinas = run_query(
            "SELECT id_ihm FROM dbo.tb_ihm WHERE id_linha_producao = :lid",
            {"lid": linha_id}
        )
        if df_maquinas.empty:
            return {"produzido": 0, "refugo": 0}
        terminal_ihms = [int(r["id_ihm"]) for _, r in df_maquinas.iterrows()]

    conformes = 0
    refugo    = 0
    for iid in terminal_ihms:
        for desc in ("produzido", "reprovado"):
            df = run_query("""
                SELECT
                    MAX(CASE WHEN lr.dt_created_at <  :dt THEN lr.nu_valor_bruto ELSE NULL END) AS v_base,
                    MAX(CASE WHEN lr.dt_created_at >= :dt THEN lr.nu_valor_bruto ELSE NULL END) AS v_curr,
                    MIN(CASE WHEN lr.dt_created_at >= :dt THEN lr.nu_valor_bruto ELSE NULL END) AS v_first
                FROM dbo.tb_log_registrador lr
                JOIN dbo.tb_registrador r ON r.id_registrador = lr.id_registrador
                WHERE lr.id_ihm      = :id
                  AND r.tx_descricao = :desc
            """, {"id": iid, "desc": desc, "dt": dt_inicio})
            if not df.empty and df.iloc[0]["v_curr"] is not None:
                row = df.iloc[0]
                v_curr  = float(row["v_curr"])
                v_base  = float(row["v_base"])  if row["v_base"]  is not None else None
                v_first = float(row["v_first"]) if row["v_first"] is not None else None
                baseline = v_base if v_base is not None else v_first
                if baseline is not None:
                    delta = v_curr - baseline
                    if delta > 0:
                        if desc == "produzido":
                            conformes += int(delta)
                        else:
                            refugo += int(delta)
    return {"produzido": conformes, "refugo": refugo}


def _criar_complemento_se_necessario(ordem_id: int, nu_produzido: int) -> None:
    """Se a OP foi finalizada com menos conformes do que o solicitado, cria uma nova OP
    na fila com a quantidade faltante, marcada como complemento da OP original."""
    df = run_query("""
        SELECT nu_numero_op, id_linha_producao, tx_peca, id_peca,
               nu_quantidade, nu_prioridade
        FROM dbo.tb_ordem_producao
        WHERE id_ordem = :id
    """, {"id": ordem_id})
    if df.empty:
        return
    r          = df.iloc[0]
    quantidade = int(r["nu_quantidade"])
    faltante   = quantidade - nu_produzido
    if faltante <= 0:
        return  # eficiência 100% — nenhum complemento necessário

    numero_op_original = r["nu_numero_op"]
    novo_numero        = proximo_numero_op()
    obs                = f"Complemento da OP {numero_op_original} ({faltante} peça(s) reprovada(s))"

    create_ordem(
        numero_op   = novo_numero,
        linha_id    = int(r["id_linha_producao"]),
        peca        = r["tx_peca"],
        quantidade  = faltante,
        prioridade  = int(r["nu_prioridade"]) if r["nu_prioridade"] is not None else 0,
        observacoes = obs,
        peca_id     = int(r["id_peca"]) if r["id_peca"] is not None and not pd.isna(r["id_peca"]) else None,
    )


def _finalizar_op_automatico(ordem_id: int, nu_produzido: int, nu_refugo: int) -> None:
    """Finaliza automaticamente uma OP registrando conformes e refugos produzidos."""
    rows = run_query_update("""
        UPDATE dbo.tb_ordem_producao
        SET tx_status                = 'finalizado',
            dt_fim                   = GETDATE(),
            nu_produzido             = :prod,
            nu_refugo                = :refugo,
            nu_meta_turno_atual      = 0,
            nu_pecas_proximos_turnos = 0
        WHERE id_ordem = :id AND tx_status = 'em_producao'
    """, {"prod": nu_produzido, "refugo": nu_refugo, "id": ordem_id})

    # rowcount == 0 → OP já foi finalizada por outra chamada concorrente (2b e 2c
    # podem disparar para a mesma OP no mesmo tick). Não faz nada.
    if not rows:
        return

    df = run_query(
        "SELECT id_linha_producao FROM dbo.tb_ordem_producao WHERE id_ordem = :id",
        {"id": ordem_id}
    )
    if df.empty:
        return
    linha_id = int(df.iloc[0]["id_linha_producao"])
    try:
        _recalcular_metas_linha(linha_id)
        _ativar_proxima_op(linha_id)
    except Exception:
        pass


# ─── Peças e Roteiros ────────────────────────────────────────────────────────

def get_pecas_by_linha(linha_id: int) -> list:
    """Lista as peças configuradas para uma linha, com seus roteiros."""
    _ensure_schema()
    df = run_query("""
        SELECT id_peca, tx_name FROM dbo.tb_peca
        WHERE id_linha_producao = :lid ORDER BY tx_name
    """, {"lid": linha_id})
    result = []
    for _, r in df.iterrows():
        peca_id = int(r["id_peca"])
        result.append({"id": peca_id, "nome": r["tx_name"], "rota": get_rota_peca(peca_id)})
    return result


def create_peca(linha_id: int, nome: str) -> int:
    _ensure_schema()
    return run_query_insert("""
        INSERT INTO dbo.tb_peca (tx_name, id_linha_producao, tempo_producao) OUTPUT INSERTED.id_peca
        VALUES (:nome, :lid, 0)
    """, {"nome": nome.strip(), "lid": linha_id})


def delete_peca(peca_id: int) -> None:
    _ensure_schema()
    run_query_update("DELETE FROM dbo.tb_peca_rota WHERE id_peca = :id", {"id": peca_id})
    run_query_update("DELETE FROM dbo.tb_peca WHERE id_peca = :id", {"id": peca_id})


def get_rota_peca(peca_id: int) -> list:
    """Retorna o roteiro ordenado de uma peça: lista de {id_ihm, nome, nu_ordem, producao_teorica, tipo_maquina}."""
    _ensure_schema()
    df = run_query("""
        SELECT r.id_ihm, i.tx_name AS nome, r.nu_ordem,
               COALESCE(r.nu_producao_teorica, 0) AS nu_producao_teorica,
               COALESCE(i.tx_tipo_maquina, '') AS tx_tipo_maquina
        FROM dbo.tb_peca_rota r
        JOIN dbo.tb_ihm i ON i.id_ihm = r.id_ihm
        WHERE r.id_peca = :id ORDER BY r.nu_ordem
    """, {"id": peca_id})
    if df.empty:
        return []
    return [
        {
            "id_ihm": int(r["id_ihm"]),
            "nome": r["nome"],
            "nu_ordem": int(r["nu_ordem"]),
            "producao_teorica": int(r["nu_producao_teorica"]),
            "tipo_maquina": r["tx_tipo_maquina"],
        }
        for _, r in df.iterrows()
    ]


def _get_n_etapas(peca_id: int | None) -> int:
    """Retorna o número de etapas (estágios distintos) no roteiro de uma peça."""
    if not peca_id:
        return 0
    rota = get_rota_peca(peca_id)
    seen: set = set()
    n = 0
    for step in rota:
        tipo = step["tipo_maquina"]
        if tipo and tipo not in seen:
            seen.add(tipo)
            n += 1
        elif not tipo:
            n += 1
    return n


def _init_op_pecas(op_id: int, quantidade: int, n_etapas: int) -> None:
    """Insere as peças de uma OP na tabela de rastreamento (idempotente)."""
    if n_etapas <= 0:
        return
    _ensure_schema()
    df = run_query(
        "SELECT COUNT(*) AS n FROM dbo.tb_op_peca_producao WHERE id_ordem = :id",
        {"id": op_id}
    )
    if not df.empty and int(df.iloc[0]["n"]) > 0:
        return  # já inicializado

    # Insere em blocos de 5000 via CTE recursiva
    BLOCK = 5000
    for bloco_ini in range(1, quantidade + 1, BLOCK):
        bloco_fim = min(bloco_ini + BLOCK - 1, quantidade)
        run_query_update(f"""
            WITH nums AS (
                SELECT {bloco_ini} AS n
                UNION ALL
                SELECT n + 1 FROM nums WHERE n < {bloco_fim}
            )
            INSERT INTO dbo.tb_op_peca_producao
                (id_ordem, nu_peca, nu_etapas_total, nu_etapa_atual, nu_etapa_erro)
            SELECT {op_id}, n, {n_etapas}, 1, NULL FROM nums
            OPTION (MAXRECURSION 5000)
        """)


def update_rota_peca(peca_id: int, steps: list) -> None:
    """Salva o roteiro de uma peça. steps = lista de {id_ihm, producao_teorica}."""
    _ensure_schema()
    run_query_update("DELETE FROM dbo.tb_peca_rota WHERE id_peca = :id", {"id": peca_id})
    for ordem, step in enumerate(steps, start=1):
        run_query_update("""
            INSERT INTO dbo.tb_peca_rota (id_peca, id_ihm, nu_ordem, nu_producao_teorica)
            VALUES (:peca, :ihm, :ordem, :prod)
        """, {
            "peca": peca_id,
            "ihm": step["id_ihm"],
            "ordem": ordem,
            "prod": step.get("producao_teorica", 0),
        })


def _get_horas_restantes_turno(linha_id: int) -> float:
    agora = datetime.now()
    df = run_query("""
        SELECT TOP 1 dt_fim FROM dbo.tb_turno_ocorrencia
        WHERE id_linha_producao = :lid
          AND dt_inicio <= :agora AND dt_fim >= :agora
          AND tx_status IN ('em_andamento', 'agendado')
        ORDER BY dt_inicio
    """, {"lid": linha_id, "agora": agora})
    if df.empty:
        return 0.0
    return max(0.0, (df.iloc[0]["dt_fim"] - agora).total_seconds() / 3600)


def _set_meta_rota(peca_id: int, linha_id: int, peca_nome: str) -> None:
    """Seta meta individualmente em cada máquina do roteiro da peça."""
    horas = _get_horas_restantes_turno(linha_id)
    for m in get_rota_peca(peca_id):
        meta = int(m.get("producao_teorica", 0) * horas)
        try:
            update_machine_config(m["id_ihm"], meta, peca_nome)
        except Exception:
            pass


def _clear_meta_rota(peca_id: int) -> None:
    """Zera a meta nas máquinas do roteiro da peça."""
    for m in get_rota_peca(peca_id):
        try:
            update_machine_config(m["id_ihm"], 0, get_selected_piece(m["id_ihm"]))
        except Exception:
            pass


def recalcular_turno_ordens_ativas() -> None:
    """
    Verifica OPs em produção cujo turno calculado já expirou e redistribui
    as peças restantes para o turno seguinte (rollover automático).
    Chamado a cada broadcast do WebSocket de ordens.
    """
    _ensure_schema()
    agora = datetime.now()

    # === Parte 1: Gerencia ocorrências de turno ===

    # Garante ocorrências futuras para todas as linhas
    try:
        df_linhas = get_lines_df()
        for _, linha in df_linhas.iterrows():
            lid = int(linha["id_linha_producao"])
            _ensure_ocorrencias_futuras(lid)
    except Exception:
        pass

    # Fecha turnos em_andamento cujo dt_fim já passou
    try:
        df_closing = run_query("""
            SELECT id_ocorrencia, id_linha_producao
            FROM dbo.tb_turno_ocorrencia
            WHERE tx_status = 'em_andamento' AND dt_fim < :agora
        """, {"agora": agora})
        for _, oc in df_closing.iterrows():
            try:
                _fechar_turno(int(oc["id_ocorrencia"]), int(oc["id_linha_producao"]))
            except Exception:
                pass
    except Exception:
        pass

    # Marca turnos agendados que já expiraram (sem nunca terem aberto) como finalizado
    try:
        run_query_update("""
            UPDATE dbo.tb_turno_ocorrencia
            SET tx_status = 'finalizado', nu_produzido = 0
            WHERE tx_status = 'agendado' AND dt_fim < :agora
        """, {"agora": agora})
    except Exception:
        pass

    # Abre turnos agendados cujo intervalo inclui agora
    try:
        df_opening = run_query("""
            SELECT id_ocorrencia, id_linha_producao
            FROM dbo.tb_turno_ocorrencia
            WHERE tx_status = 'agendado'
              AND dt_inicio <= :agora AND dt_fim >= :agora
        """, {"agora": agora})
        for _, oc in df_opening.iterrows():
            try:
                _abrir_turno(int(oc["id_ocorrencia"]), int(oc["id_linha_producao"]))
                _recalcular_metas_linha(int(oc["id_linha_producao"]))
            except Exception:
                pass
    except Exception:
        pass

    # === Parte 2: Auto-finalização de OPs ===

    # 2a: Turno calculado expirou → finaliza com o que foi produzido
    try:
        df_expiradas = run_query("""
            SELECT id_ordem, id_linha_producao, dt_inicio, id_peca
            FROM dbo.tb_ordem_producao
            WHERE tx_status = 'em_producao'
              AND dt_fim_turno_calculado IS NOT NULL
              AND dt_fim_turno_calculado < :agora
        """, {"agora": agora})
        for _, op in df_expiradas.iterrows():
            try:
                dt_ini   = op["dt_inicio"]
                peca_id  = int(op["id_peca"]) if op.get("id_peca") is not None and not pd.isna(op["id_peca"]) else None
                producao = _get_producao_refugo_op(int(op["id_linha_producao"]), dt_ini, peca_id) if dt_ini is not None else {"produzido": 0, "refugo": 0}
                _finalizar_op_automatico(int(op["id_ordem"]), producao["produzido"], producao["refugo"])
            except Exception:
                pass
    except Exception:
        pass

    # 2b: Meta atingida (terminais produziram >= meta_op) → finaliza
    try:
        df_ativas = run_query("""
            SELECT id_ordem, id_linha_producao, nu_meta_turno_atual, dt_inicio, id_peca
            FROM dbo.tb_ordem_producao
            WHERE tx_status = 'em_producao'
              AND nu_meta_turno_atual > 0
              AND dt_inicio IS NOT NULL
        """, {})
        for _, op in df_ativas.iterrows():
            try:
                dt_ini  = op["dt_inicio"]
                meta    = int(op["nu_meta_turno_atual"])
                peca_id = int(op["id_peca"]) if op.get("id_peca") is not None and not pd.isna(op["id_peca"]) else None
                # Período de carência: aguarda ao menos 120 s desde dt_inicio antes de
                # auto-finalizar, para evitar falso-positivo com logs antigos (UTC).
                dt_ini_py = pd.Timestamp(dt_ini).to_pydatetime() if not isinstance(dt_ini, datetime) else dt_ini
                age_s = (datetime.now() - dt_ini_py.replace(tzinfo=None)).total_seconds()
                if age_s < 120:
                    continue
                # Conta apenas a última etapa do roteiro.
                # Aprovadas + reprovadas somam ao total processado: se uma peça
                # foi reprovada, ela já foi consumida da OP — não precisa refazer.
                producao = _get_producao_refugo_op(int(op["id_linha_producao"]), dt_ini, peca_id)
                total_processado = producao["produzido"] + producao["refugo"]
                if total_processado >= meta:
                    _finalizar_op_automatico(int(op["id_ordem"]), producao["produzido"], producao["refugo"])
            except Exception:
                pass
    except Exception:
        pass

    # 2c: Roteiro completo — todas as peças rastreadas concluíram ou falharam → finaliza
    try:
        df_rastreadas = run_query("""
            SELECT DISTINCT o.id_ordem, o.id_linha_producao, o.dt_inicio, o.id_peca
            FROM dbo.tb_ordem_producao o
            WHERE o.tx_status = 'em_producao'
              AND o.dt_inicio IS NOT NULL
              AND EXISTS (
                  SELECT 1 FROM dbo.tb_op_peca_producao p WHERE p.id_ordem = o.id_ordem
              )
              AND NOT EXISTS (
                  SELECT 1 FROM dbo.tb_op_peca_producao p
                  WHERE p.id_ordem = o.id_ordem
                    AND p.nu_etapa_atual <= p.nu_etapas_total
                    AND p.nu_etapa_erro IS NULL
              )
        """, {})
        for _, op in df_rastreadas.iterrows():
            try:
                dt_ini    = op["dt_inicio"]
                dt_ini_py = pd.Timestamp(dt_ini).to_pydatetime() if not isinstance(dt_ini, datetime) else dt_ini
                age_s = (datetime.now() - dt_ini_py.replace(tzinfo=None)).total_seconds()
                if age_s < 120:
                    continue
                peca_id = int(op["id_peca"]) if op.get("id_peca") is not None and not pd.isna(op["id_peca"]) else None
                producao = _get_producao_refugo_op(int(op["id_linha_producao"]), dt_ini, peca_id)
                _finalizar_op_automatico(int(op["id_ordem"]), producao["produzido"], producao["refugo"])
            except Exception:
                pass
    except Exception:
        pass


# ─── Distribuição e Fluxo de Produção ────────────────────────────────────────

def save_op_distribuicao(op_id: int, distribuicao: list) -> None:
    """
    Salva a distribuição de produção de uma OP entre máquinas do mesmo tipo
    e recalcula as metas das máquinas da linha imediatamente.
    distribuicao = lista de {id_ihm, tipo_maquina, percentual}
    """
    _ensure_schema()
    # Remove entradas existentes e reinsere
    run_query_update("DELETE FROM dbo.tb_op_distribuicao WHERE id_ordem = :id", {"id": op_id})
    for entry in distribuicao:
        run_query_update("""
            INSERT INTO dbo.tb_op_distribuicao (id_ordem, id_ihm, tx_tipo_maquina, nu_percentual)
            VALUES (:ordem, :ihm, :tipo, :pct)
        """, {
            "ordem": op_id,
            "ihm":   entry["id_ihm"],
            "tipo":  entry["tipo_maquina"],
            "pct":   float(entry.get("percentual", 100.0)),
        })

    # Recalcula metas das máquinas da linha desta OP
    df = run_query("SELECT id_linha_producao FROM dbo.tb_ordem_producao WHERE id_ordem = :id", {"id": op_id})
    if not df.empty:
        _recalcular_metas_linha(int(df.iloc[0]["id_linha_producao"]))


def _get_machine_stats_op(ihm_id: int, dt_inicio, dt_fim=None) -> dict:
    """Aprovado, reprovado e status de uma IHM no intervalo [dt_inicio, dt_fim].
    dt_fim=None significa OP ainda em andamento (sem limite superior)."""
    aprovado  = 0
    reprovado = 0
    for desc in ("produzido", "reprovado"):
        if dt_fim is not None:
            df = run_query("""
                SELECT
                    MAX(CASE WHEN lr.dt_created_at <  :dt_ini THEN lr.nu_valor_bruto ELSE NULL END) AS v_base,
                    MAX(CASE WHEN lr.dt_created_at >= :dt_ini AND lr.dt_created_at <= :dt_fim THEN lr.nu_valor_bruto ELSE NULL END) AS v_curr,
                    MIN(CASE WHEN lr.dt_created_at >= :dt_ini AND lr.dt_created_at <= :dt_fim THEN lr.nu_valor_bruto ELSE NULL END) AS v_first
                FROM dbo.tb_log_registrador lr
                JOIN dbo.tb_registrador r ON r.id_registrador = lr.id_registrador
                WHERE lr.id_ihm = :id AND r.tx_descricao = :desc
            """, {"id": ihm_id, "desc": desc, "dt_ini": dt_inicio, "dt_fim": dt_fim})
        else:
            df = run_query("""
                SELECT
                    MAX(CASE WHEN lr.dt_created_at <  :dt THEN lr.nu_valor_bruto ELSE NULL END) AS v_base,
                    MAX(CASE WHEN lr.dt_created_at >= :dt THEN lr.nu_valor_bruto ELSE NULL END) AS v_curr,
                    MIN(CASE WHEN lr.dt_created_at >= :dt THEN lr.nu_valor_bruto ELSE NULL END) AS v_first
                FROM dbo.tb_log_registrador lr
                JOIN dbo.tb_registrador r ON r.id_registrador = lr.id_registrador
                WHERE lr.id_ihm = :id AND r.tx_descricao = :desc
            """, {"id": ihm_id, "desc": desc, "dt": dt_inicio})
        if not df.empty and df.iloc[0]["v_curr"] is not None:
            row = df.iloc[0]
            v_curr  = float(row["v_curr"])
            v_base  = float(row["v_base"])  if row["v_base"]  is not None else None
            v_first = float(row["v_first"]) if row["v_first"] is not None else None
            baseline = v_base if v_base is not None else v_first
            if baseline is not None:
                delta = v_curr - baseline
                if delta > 0:
                    if desc == "produzido": aprovado  = int(delta)
                    else:                  reprovado = int(delta)

    # Para OP finalizada, o status no dt_fim é sempre parada
    if dt_fim is not None:
        status = "parada"
    else:
        df_st = run_query("""
            SELECT TOP 1 lr.nu_valor_bruto
            FROM dbo.tb_log_registrador lr
            JOIN dbo.tb_registrador r ON r.id_registrador = lr.id_registrador
            WHERE lr.id_ihm = :id AND r.tx_descricao = 'status_maquina'
            ORDER BY lr.dt_created_at DESC
        """, {"id": ihm_id})
        status = "parada"
        if not df_st.empty:
            v = int(df_st.iloc[0]["nu_valor_bruto"])
            status = {49: "produzindo", 4: "limpeza", 52: "manutencao"}.get(v, "parada")

    return {"aprovado": aprovado, "reprovado": reprovado, "status_maquina": status}


def get_op_fluxo(op_id: int) -> dict:
    """
    Retorna os dados de fluxograma para uma OP:
    - Informações da OP
    - Etapas do roteiro agrupadas por tipo_maquina
    - Para cada tipo, lista de máquinas com percentual e quantidade calculada
    - Máquinas paralelas (mesmo tipo, mesma linha) também inclusas
    - Quando em_producao: adiciona stats live (aprovado/reprovado/status) por máquina
    """
    _ensure_schema()

    # Busca OP
    df_op = run_query("""
        SELECT o.id_ordem, o.nu_numero_op, o.tx_peca, o.nu_quantidade,
               o.tx_status, o.id_linha_producao, o.id_peca, o.dt_inicio, o.dt_fim
        FROM dbo.tb_ordem_producao o
        WHERE o.id_ordem = :id
    """, {"id": op_id})
    if df_op.empty:
        return {}

    op = df_op.iloc[0]
    linha_id   = int(op["id_linha_producao"])
    quantidade = int(op["nu_quantidade"])
    peca_id    = op["id_peca"]
    dt_inicio  = op["dt_inicio"]
    dt_fim_op  = op["dt_fim"]
    status_op  = op["tx_status"]
    em_prod    = status_op in ("em_producao", "finalizado")

    steps = []

    if peca_id is not None:
        rota = get_rota_peca(int(peca_id))

        # Producao_teorica por máquina a partir da rota (tb_peca_rota tem prioridade)
        route_prod = {step["id_ihm"]: step["producao_teorica"] for step in rota}

        # Agrupa máquinas da linha por tipo (inclui producao_teorica como fallback)
        df_linha = run_query("""
            SELECT i.id_ihm, i.tx_name, COALESCE(i.tx_tipo_maquina, '') AS tx_tipo_maquina,
                   COALESCE(c.nu_producao_teorica, 0) AS nu_producao_teorica
            FROM dbo.tb_ihm i
            LEFT JOIN dbo.tb_config_producao_teorica c ON c.id_ihm = i.id_ihm
            WHERE i.id_linha_producao = :lid
            ORDER BY i.id_ihm
        """, {"lid": linha_id})
        maquinas_por_tipo: dict = {}
        for _, m in df_linha.iterrows():
            t = m["tx_tipo_maquina"]
            if t:
                iid = int(m["id_ihm"])
                maquinas_por_tipo.setdefault(t, []).append({
                    "id_ihm": iid,
                    "nome": m["tx_name"],
                    "producao_teorica": route_prod.get(iid) or int(m["nu_producao_teorica"]),
                })

        # Busca distribuição existente para esta OP
        df_dist = run_query("""
            SELECT id_ihm, tx_tipo_maquina, nu_percentual
            FROM dbo.tb_op_distribuicao
            WHERE id_ordem = :id
        """, {"id": op_id})
        dist_map: dict = {}  # (id_ihm, tipo) -> percentual
        if not df_dist.empty:
            for _, d in df_dist.iterrows():
                dist_map[(int(d["id_ihm"]), d["tx_tipo_maquina"])] = float(d["nu_percentual"])

        # Monta etapas sem duplicar tipos já vistos
        seen_tipos: set = set()
        for step in rota:
            tipo = step["tipo_maquina"]

            if tipo and tipo in seen_tipos:
                continue  # já processou este tipo de máquina

            if tipo and tipo in maquinas_por_tipo:
                seen_tipos.add(tipo)
                alternativas = maquinas_por_tipo[tipo]

                # Monta distribuição: usa salva ou proporcional à producao_teorica
                total_pct = sum(dist_map.get((m["id_ihm"], tipo), 0) for m in alternativas)
                total_prod = sum(m.get("producao_teorica", 0) for m in alternativas)
                maquinas_etapa = []
                for m in alternativas:
                    if total_pct > 0:
                        pct = dist_map.get((m["id_ihm"], tipo), 0.0)
                    elif total_prod > 0:
                        pct = 100.0 * m.get("producao_teorica", 0) / total_prod
                    else:
                        pct = 100.0 if m["id_ihm"] == step["id_ihm"] else 0.0
                    entry = {
                        "id_ihm": m["id_ihm"],
                        "nome": m["nome"],
                        "percentual": round(pct, 1),
                        "quantidade": round(quantidade * pct / 100),
                    }
                    if em_prod and dt_inicio is not None:
                        _dt_fim = dt_fim_op if status_op == "finalizado" else None
                        entry.update(_get_machine_stats_op(m["id_ihm"], dt_inicio, _dt_fim))
                    maquinas_etapa.append(entry)

                steps.append({
                    "ordem": step["nu_ordem"],
                    "tipo_maquina": tipo,
                    "producao_teorica": step["producao_teorica"],
                    "maquinas": maquinas_etapa,
                })
            else:
                # Máquina sem tipo definido — aparece sozinha, sem paralelas
                pct = dist_map.get((step["id_ihm"], ""), 100.0)
                entry = {
                    "id_ihm": step["id_ihm"],
                    "nome": step["nome"],
                    "percentual": 100.0,
                    "quantidade": quantidade,
                }
                if em_prod and dt_inicio is not None:
                    _dt_fim = dt_fim_op if status_op == "finalizado" else None
                    entry.update(_get_machine_stats_op(step["id_ihm"], dt_inicio, _dt_fim))
                steps.append({
                    "ordem": step["nu_ordem"],
                    "tipo_maquina": tipo or step["nome"],
                    "producao_teorica": step["producao_teorica"],
                    "maquinas": [entry],
                })

    # Rastreamento individual de peças (sempre que existir na tabela)
    df_pieces = run_query("""
        SELECT nu_peca, nu_etapas_total, nu_etapa_atual, nu_etapa_erro
        FROM dbo.tb_op_peca_producao
        WHERE id_ordem = :id
        ORDER BY nu_peca
    """, {"id": op_id})
    pieces = []
    if not df_pieces.empty:
        for _, r in df_pieces.iterrows():
            pieces.append({
                "peca":         int(r["nu_peca"]),
                "etapas_total": int(r["nu_etapas_total"]),
                "etapa_atual":  int(r["nu_etapa_atual"]),
                "etapa_erro":   int(r["nu_etapa_erro"]) if r["nu_etapa_erro"] is not None and not pd.isna(r["nu_etapa_erro"]) else None,
            })

    return {
        "op": {
            "id":         int(op["id_ordem"]),
            "numero_op":  op["nu_numero_op"],
            "peca":       op["tx_peca"],
            "quantidade": quantidade,
            "status":     op["tx_status"],
        },
        "steps":  steps,
        "pieces": pieces,
    }


# ─── Setup de dados fantasma ──────────────────────────────────────────────────

def setup_ghost_data() -> None:
    """
    Executa na inicialização do servidor (toda vez que o container sobe):
    - Configura tx_tipo_maquina das IHMs da Linha Pintura (A, B, C, C, D)
    - Cria/atualiza a peça fantasma com o roteiro completo
    - Configura producao_teorica das IHMs da Linha Pintura
    - Cria o turno fantasma do dia atual (19h–22h) se ainda não existir
    """
    _ensure_schema()
    try:
        df_linha = run_query("""
            SELECT id_linha_producao FROM dbo.tb_linha_producao
            WHERE tx_name = N'LINHA PINTURA'
        """)
        if df_linha.empty:
            return
        linha_id = int(df_linha.iloc[0]["id_linha_producao"])

        # Mapas: id_ihm → tipo e producao_teorica
        tipos      = {3: "A", 4: "B", 5: "C", 6: "C", 7: "D"}
        producoes  = {3: 80,  4: 40,  5: 300, 6: 300, 7: 80}

        for id_ihm, tipo in tipos.items():
            run_query_update(
                "UPDATE dbo.tb_ihm SET tx_tipo_maquina = :t WHERE id_ihm = :id",
                {"t": tipo, "id": id_ihm},
            )

        for id_ihm, prod in producoes.items():
            run_query_update("""
                MERGE dbo.tb_config_producao_teorica AS tgt
                USING (SELECT :id AS id_ihm, :prod AS nu_producao_teorica) AS src
                    ON tgt.id_ihm = src.id_ihm
                WHEN MATCHED THEN
                    UPDATE SET nu_producao_teorica = src.nu_producao_teorica,
                               dt_updated          = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (id_ihm, nu_producao_teorica)
                    VALUES (src.id_ihm, src.nu_producao_teorica);
            """, {"id": id_ihm, "prod": prod})

        # Garante a peça fantasma
        df_peca = run_query(
            "SELECT id_peca FROM dbo.tb_peca WHERE tx_name = N'PEÇA FANTASMA'"
        )
        if df_peca.empty:
            peca_id = run_query_insert("""
                INSERT INTO dbo.tb_peca (tx_name, tempo_producao, id_linha_producao)
                OUTPUT INSERTED.id_peca
                VALUES (N'PEÇA FANTASMA', 0, :lid)
            """, {"lid": linha_id})
        else:
            peca_id = int(df_peca.iloc[0]["id_peca"])
            run_query_update(
                "UPDATE dbo.tb_peca SET id_linha_producao = :lid WHERE id_peca = :id",
                {"lid": linha_id, "id": peca_id},
            )

        # Recria roteiro: A(3,ord=1) → B(4,ord=2) → C(5+6,ord=3) → D(7,ord=4)
        run_query_update("DELETE FROM dbo.tb_peca_rota WHERE id_peca = :id", {"id": peca_id})
        for id_ihm, ordem in [(3, 1), (4, 2), (5, 3), (6, 3), (7, 4)]:
            run_query_update("""
                INSERT INTO dbo.tb_peca_rota (id_peca, id_ihm, nu_ordem, nu_producao_teorica)
                VALUES (:peca, :ihm, :ordem, :prod)
            """, {"peca": peca_id, "ihm": id_ihm, "ordem": ordem, "prod": producoes[id_ihm]})

        # Seed operadores fixos dos simuladores (um por máquina)
        operadores_ghost = {
            3: (1, "Carlos Silva"),
            4: (2, "Ana Souza"),
            5: (3, "João Pereira"),
            6: (4, "Marcos Oliveira"),
            7: (5, "Fernanda Costa"),
        }
        for id_ihm, (cod, nome) in operadores_ghost.items():
            run_query_update("""
                MERGE dbo.tb_depara_operador AS tgt
                USING (SELECT :id AS id_ihm, :cod AS nu_cod_operador) AS src
                    ON tgt.id_ihm = src.id_ihm AND tgt.nu_cod_operador = src.nu_cod_operador
                WHEN MATCHED THEN
                    UPDATE SET tx_operador = :nome
                WHEN NOT MATCHED THEN
                    INSERT (id_ihm, nu_cod_operador, tx_operador)
                    VALUES (:id, :cod, :nome);
            """, {"id": id_ihm, "cod": cod, "nome": nome})

        # Cria turno fantasma de hoje (19h–22h) se ainda não existir
        hoje   = datetime.now().date()
        dt_ini = datetime.combine(hoje, time(19, 0, 0))
        dt_fim = datetime.combine(hoje, time(22, 0, 0))
        df_t = run_query("""
            SELECT 1 FROM dbo.tb_turnos
            WHERE id_linha_producao = :lid AND dt_inicio = :ini AND dt_fim = :fim
        """, {"lid": linha_id, "ini": dt_ini, "fim": dt_fim})
        if df_t.empty:
            run_query_update("""
                INSERT INTO dbo.tb_turnos (tx_name, dt_inicio, dt_fim, id_linha_producao, bl_ativo)
                VALUES (N'T_FANTASMA', :ini, :fim, :lid, 1)
            """, {"ini": dt_ini, "fim": dt_fim, "lid": linha_id})

    except Exception:
        pass
