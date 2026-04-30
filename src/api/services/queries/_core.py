from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any, Optional
import math
import time as _time
import pandas as pd

from api.services.db import run_query, run_query_update, run_query_insert


# =========================
# QUERIES / FUNÇÕES REUTILIZÁVEIS
# (NÃO COLOCAR ROTAS AQUI)
# =========================

# ─── Cache de linhas ────────────────────────────────────────────────────────
_LINES_TTL = 30.0          # segundos
_lines_cache: dict = {"df": None, "ts": 0.0}

def get_lines_df():
    now = _time.monotonic()
    if _lines_cache["df"] is not None and (now - _lines_cache["ts"]) < _LINES_TTL:
        return _lines_cache["df"]
    df = run_query("""
        SELECT id_linha_producao, tx_name
        FROM dbo.tb_linha_producao
        ORDER BY id_linha_producao
    """)
    _lines_cache["df"] = df
    _lines_cache["ts"] = now
    return df


# ─── Cache / dirty-flag do recalcular_turno_ordens_ativas ──────────────────
# _meta_dirty: ativado quando uma OP muda de status → força recalc imediato
# _last_meta_recalc_ts: timestamp do último recalc de metas (Part 3)
# _ocorrencias_ts: por linha — quando foi a última verificação de ocorrências
_META_RECALC_INTERVAL   = 10.0    # segundos entre recalcs periódicos de meta
_OCORRENCIAS_INTERVAL   = 300.0   # 5 min entre ensure_ocorrencias por linha
_meta_dirty:           bool  = False
_last_meta_recalc_ts:  float = 0.0
_ocorrencias_ts:       dict  = {}  # {lid: monotonic_ts}


def _mark_meta_dirty() -> None:
    """Sinaliza que as metas precisam ser recalculadas na próxima chamada."""
    global _meta_dirty
    _meta_dirty = True


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
        # ── Relação N:N entre turno-modelo e linha-de-produção ────────────────
        # Um turno pode ter várias linhas; uma linha pode ter vários turnos.
        run_query_update("""
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.tb_turno_modelo_linha') AND type = 'U')
            BEGIN
                CREATE TABLE dbo.tb_turno_modelo_linha (
                    id_vmlink         INT IDENTITY(1,1) PRIMARY KEY,
                    id_modelo         INT NOT NULL,
                    id_linha_producao INT NOT NULL,
                    CONSTRAINT UQ_turno_modelo_linha UNIQUE (id_modelo, id_linha_producao)
                )
            END
        """)
        run_query_update("""
            IF NOT EXISTS (SELECT * FROM sys.indexes WHERE object_id = OBJECT_ID('dbo.tb_turno_modelo_linha') AND name = 'IX_vmlink_modelo')
                CREATE INDEX IX_vmlink_modelo ON dbo.tb_turno_modelo_linha(id_modelo)
        """)
        # Migra registros existentes → junction table (idempotente)
        run_query_update("""
            INSERT INTO dbo.tb_turno_modelo_linha (id_modelo, id_linha_producao)
            SELECT m.id_modelo, m.id_linha_producao
            FROM dbo.tb_turno_modelo m
            WHERE m.id_linha_producao IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM dbo.tb_turno_modelo_linha l
                WHERE l.id_modelo = m.id_modelo AND l.id_linha_producao = m.id_linha_producao
              )
        """)
        # Torna id_linha_producao nullable (campo mantido para compatibilidade, lógica migrada para junction)
        run_query_update("""
            IF EXISTS (
                SELECT 1 FROM sys.columns
                WHERE object_id = OBJECT_ID('dbo.tb_turno_modelo')
                  AND name = 'id_linha_producao' AND is_nullable = 0
            )
                ALTER TABLE dbo.tb_turno_modelo ALTER COLUMN id_linha_producao INT NULL
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
                "tempo_produzido_s": 0,
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
            "status_maquina":    status,
            "oee":               round(100 * oee,             2),
            "disponibilidade":   round(100 * disponibilidade, 2),
            "performance":       round(100 * performance,     2),
            "qualidade":         round(100 * qualidade,       2),
            "meta":              meta,
            "produzido":         produzido,
            "reprovado":         reprovado,
            "total_produzido":   total,
            "operador":          operador,
            "manutentor":        manutentor,
            "engenheiro":        engenheiro,
            "tempo_produzido_s": round(tempo_produzido),
        }
    except Exception:
        return {
            "status_maquina": "-", "oee": "-", "disponibilidade": "-",
            "performance": "-", "qualidade": "-", "meta": "-",
            "produzido": "-", "reprovado": "-", "total_produzido": "-",
            "operador": "-", "manutentor": "-", "engenheiro": "-",
            "tempo_produzido_s": 0,
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

def get_historico_turnos_machine(machine_id: int, n: int = 7) -> list:
    """Retorna disponibilidade e nº de paradas dos últimos N turnos finalizados."""
    try:
        df_ihm = run_query("SELECT id_linha_producao FROM dbo.tb_ihm WHERE id_ihm = :id", {"id": machine_id})
        if df_ihm.empty:
            return []
        lid = int(df_ihm.iloc[0]["id_linha_producao"])

        df_shifts = run_query("""
            SELECT TOP :n id_ocorrencia, tx_nome, dt_inicio, dt_fim
            FROM dbo.tb_turno_ocorrencia
            WHERE id_linha_producao = :lid AND tx_status = 'finalizado'
            ORDER BY dt_inicio DESC
        """, {"n": n, "lid": lid})

        if df_shifts.empty:
            return []

        oldest = df_shifts["dt_inicio"].min()

        df_logs = run_query("""
            SELECT lr.dt_created_at, lr.nu_valor_bruto
            FROM dbo.tb_log_registrador lr
            JOIN dbo.tb_registrador r ON r.id_registrador = lr.id_registrador
            WHERE lr.id_ihm = :id
              AND r.tx_descricao = 'status_maquina'
              AND lr.dt_created_at >= :oldest
            ORDER BY lr.dt_created_at
        """, {"id": machine_id, "oldest": oldest})

        result = []
        for _, shift in df_shifts.iterrows():
            dt_ini  = pd.Timestamp(shift["dt_inicio"])
            dt_fim  = pd.Timestamp(shift["dt_fim"])
            total_s = (dt_fim - dt_ini).total_seconds()
            if total_s <= 0:
                continue

            if not df_logs.empty:
                mask = (
                    (pd.to_datetime(df_logs["dt_created_at"]) >= dt_ini) &
                    (pd.to_datetime(df_logs["dt_created_at"]) <= dt_fim)
                )
                shift_logs = df_logs[mask].sort_values("dt_created_at")
                rows_sl    = [(pd.Timestamp(r["dt_created_at"]), int(r["nu_valor_bruto"]))
                               for _, r in shift_logs.iterrows()]
            else:
                rows_sl = []

            prod_s     = 0.0
            num_paradas = 0
            for i, (dt, cod) in enumerate(rows_sl):
                dt_next = rows_sl[i + 1][0] if i + 1 < len(rows_sl) else dt_fim
                dur = max(0.0, (dt_next - dt).total_seconds())
                if cod == 49:
                    prod_s += dur
                elif i > 0 and rows_sl[i - 1][1] == 49:
                    num_paradas += 1

            disp = round(prod_s / total_s * 100, 1) if total_s > 0 else 0
            result.append({
                "nome":           shift["tx_nome"],
                "data":           dt_ini.strftime("%d/%m"),
                "hora":           dt_ini.strftime("%H:%M"),
                "disponibilidade": disp,
                "num_paradas":    num_paradas,
            })

        return list(reversed(result))   # mais antigo primeiro (esquerda do gráfico)
    except Exception:
        return []


def get_machine_detail(machine_id: int) -> dict:
    """Payload completo da tela de detalhe de uma máquina específica."""
    df_ihm = run_query("""
        SELECT i.id_ihm, i.tx_name, l.tx_name AS linha_nome,
               COALESCE(i.tx_tipo_maquina, '') AS tipo_maquina
        FROM dbo.tb_ihm i
        JOIN dbo.tb_linha_producao l ON l.id_linha_producao = i.id_linha_producao
        WHERE i.id_ihm = :id
    """, {"id": machine_id})

    if df_ihm.empty:
        return {"erro": f"Máquina {machine_id} não encontrada"}

    ihm     = df_ihm.iloc[0]
    metrics = get_metrics_machine(machine_id)
    peca    = get_selected_piece(machine_id)

    # Janela do turno — usada em toda a função
    agora_dt = datetime.now()
    shift_ini, shift_fim = _get_current_shift_window(machine_id, agora_dt)

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
        df_status = df_logs[df_logs["tx_descricao"] == "status_maquina"].sort_values("dt_created_at")
        df_motivo = df_logs[df_logs["tx_descricao"] == "motivo_parada"].sort_values("dt_created_at")
        rows      = df_status[["dt_created_at", "nu_valor_bruto"]].values.tolist()

        # Lista de (timestamp, cod) para correlação assíncrona do motivo
        motivo_log = list(zip(
            pd.to_datetime(df_motivo["dt_created_at"]),
            df_motivo["nu_valor_bruto"].astype(int),
        ))
        mo_ptr = 0

        # Estados transitórios: aguardam o motivo definitivo para fechar o segmento.
        # - Status 0  (Máquina Parada)  : absorve duração até o motivo operacional chegar
        # - Status 52 (Em Manutenção)   : absorve duração até código 3300+ chegar
        # Status 51 (Ag. Manutentor) é PERMANENTE: gera registro próprio até 52 chegar.
        _TRANSITIONAL = {0, 52}

        estado_atual = None   # status atual do segmento aberto
        inicio_seg   = None   # timestamp de início do segmento atual
        label_cod    = 0      # código de motivo do segmento (atualizado assincronamente)
        status_ant   = None

        def _fechar_segmento(dt_fim, cod_label):
            """Fecha o segmento atual e adiciona à lista de paradas."""
            dur_s = (dt_fim - inicio_seg).total_seconds()
            tempos_parada_s.append(dur_s)
            h_s, r_s = divmod(int(dur_s), 3600)
            mot = depara_status_txt.get(cod_label, depara_status_txt.get(0, "Máquina Parada"))
            paradas.append({
                "inicio":  inicio_seg.strftime("%H:%M"),
                "motivo":  mot,
                "duracao": f"{h_s}h {r_s // 60:02d}m" if h_s else f"{r_s // 60}m",
                "status":  mot,
                "codigo":  cod_label,
            })

        for dt, cod in rows:
            cod = int(cod)
            dt  = pd.Timestamp(dt)

            # ── Passo 1: transições de estado ──────────────────────────────────

            if status_ant == 49 and cod != 49:
                # Saindo de produção → abre segmento
                estado_atual = cod
                inicio_seg   = dt
                label_cod    = 0 if cod in _TRANSITIONAL else cod

            elif status_ant is not None and status_ant != 49 and cod != 49:
                # Transição entre estados não-produtivos
                if cod == estado_atual and cod in _TRANSITIONAL:
                    # Mesmo estado transitório re-inserido (simulador): não faz nada
                    pass

                elif estado_atual == 51 and cod == 52:
                    # Ag. Manutentor (permanente) → Em Manutenção (transitório):
                    # fecha o 51, abre novo segmento transitório para o 52.
                    _fechar_segmento(dt, 51)
                    estado_atual = 52
                    inicio_seg   = dt
                    label_cod    = 0

                elif estado_atual in _TRANSITIONAL and cod not in _TRANSITIONAL and cod not in (0, 49):
                    # Motivo definitivo chegou para o estado transitório: só atualiza o label.
                    label_cod = cod

                elif cod in _TRANSITIONAL and cod != estado_atual:
                    # Entrando num estado transitório diferente (edge case): fecha e reabre.
                    _fechar_segmento(dt, label_cod)
                    estado_atual = cod
                    inicio_seg   = dt
                    label_cod    = 0

                else:
                    # Transição entre estados permanentes: fecha e reabre.
                    _fechar_segmento(dt, label_cod)
                    estado_atual = cod
                    inicio_seg   = dt
                    label_cod    = 0 if cod in _TRANSITIONAL else cod

            # ── Passo 2: avança ponteiro de motivo (assíncrono / simulador) ───
            while mo_ptr < len(motivo_log):
                m_dt, m_cod = motivo_log[mo_ptr]
                if m_dt > dt:
                    break
                if (inicio_seg is not None
                        and m_dt >= inicio_seg
                        and m_cod not in (0, 49)
                        and m_cod not in _TRANSITIONAL
                        and estado_atual in _TRANSITIONAL):
                    label_cod = m_cod
                mo_ptr += 1

            # ── Passo 3: fecha segmento ao retornar à produção ─────────────────
            if status_ant is not None and status_ant != 49 and cod == 49 and inicio_seg is not None:
                _fechar_segmento(dt, label_cod)
                estado_atual = None
                inicio_seg   = None
                label_cod    = 0

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

    # ── Adicionar duracao_s a cada parada ─────────────────────────────────────
    for i, p in enumerate(paradas):
        p["duracao_s"] = round(tempos_parada_s[i]) if i < len(tempos_parada_s) else 0

    # ── Métricas de produção do turno ──────────────────────────────────────────
    prod_int   = int(metrics.get("produzido",         0) or 0)
    meta_int   = int(metrics.get("meta",              0) or 0)
    tempo_prod = int(metrics.get("tempo_produzido_s", 0) or 0)
    prod_pct   = round(prod_int / meta_int * 100, 1) if meta_int > 0 else 0
    velocidade = round(prod_int / tempo_prod * 3600) if tempo_prod > 0 else 0

    # ── Refugo do turno ────────────────────────────────────────────────────────
    refugo_turno = int(metrics.get("reprovado", 0) or 0)
    refugo_pct   = round(refugo_turno / (prod_int + refugo_turno) * 100, 1) if (prod_int + refugo_turno) > 0 else 0

    # ── Uptime: segundos rodando desde a última parada ─────────────────────────
    uptime_s = None
    if "produz" in str(metrics.get("status_maquina", "")).lower() and not df_logs.empty:
        df_st_up = df_logs[df_logs["tx_descricao"] == "status_maquina"].sort_values("dt_created_at")
        rows_up  = [(pd.Timestamp(r["dt_created_at"]), int(r["nu_valor_bruto"]))
                    for _, r in df_st_up.iterrows()]
        for i in range(len(rows_up) - 1, -1, -1):
            if rows_up[i][1] == 49:
                if i == 0 or rows_up[i - 1][1] != 49:
                    uptime_s = max(0, int((datetime.now() - rows_up[i][0]).total_seconds()))
                    break

    # ── Há quanto tempo parada ─────────────────────────────────────────────────
    parada_ha = None
    if "produz" not in str(metrics.get("status_maquina", "")).lower() and not df_logs.empty:
        df_st_last = df_logs[df_logs["tx_descricao"] == "status_maquina"].sort_values("dt_created_at")
        if not df_st_last.empty:
            last_ts   = pd.Timestamp(df_st_last.iloc[-1]["dt_created_at"])
            delta     = datetime.now() - last_ts
            h_p, r_p  = divmod(max(0, int(delta.total_seconds())), 3600)
            parada_ha = f"{h_p:02d}:{r_p // 60:02d}"

    # ── OP ativa desta linha/máquina ───────────────────────────────────────────
    op_ativa = None
    try:
        df_op = run_query("""
            SELECT TOP 1 o.nu_numero_op, o.tx_peca, o.nu_quantidade, o.nu_refugo,
                   COALESCE(rt.nu_prod_rt, o.nu_produzido) AS nu_prod
            FROM dbo.tb_ordem_producao o
            JOIN dbo.tb_ihm i ON i.id_linha_producao = o.id_linha_producao
            LEFT JOIN (
                SELECT id_ordem,
                    SUM(CASE WHEN nu_etapa_atual >= nu_etapas_total
                                  AND nu_etapa_erro IS NULL THEN 1 ELSE 0 END) AS nu_prod_rt
                FROM dbo.tb_op_peca_producao GROUP BY id_ordem
            ) rt ON rt.id_ordem = o.id_ordem
            WHERE i.id_ihm = :id
              AND o.tx_status NOT IN ('concluida', 'cancelada')
            ORDER BY o.nu_prioridade DESC, o.dt_criacao
        """, {"id": machine_id})
        if not df_op.empty:
            rop    = df_op.iloc[0]
            qtd_op = int(rop["nu_quantidade"]) if not pd.isna(rop["nu_quantidade"]) else 0
            prd_op = int(rop["nu_prod"])       if not pd.isna(rop["nu_prod"])       else 0
            ref_op = int(rop["nu_refugo"])     if not pd.isna(rop["nu_refugo"])     else 0
            op_ativa = {
                "numero":    rop["nu_numero_op"],
                "peca":      rop["tx_peca"],
                "quantidade": qtd_op,
                "produzido":  prd_op,
                "refugo":     ref_op,
                "progresso":  round(prd_op / qtd_op * 100, 1) if qtd_op > 0 else 0,
            }
    except Exception:
        pass

    # ── Histórico de turnos (OEE/disponibilidade últimos 7) ───────────────────
    historico_turnos: list = []
    try:
        historico_turnos = get_historico_turnos_machine(machine_id, n=7)
    except Exception:
        pass

    # ── Produção hora a hora e pareto de paradas ───────────────────────────────
    efetivo = min(shift_fim, agora_dt)
    producao_horaria: list = []
    pareto_paradas:   list = []
    try:
        producao_horaria = get_producao_hora_maquina(machine_id, shift_ini, efetivo)
    except Exception:
        pass
    try:
        pareto_paradas = get_pareto_paradas(machine_id, shift_ini, efetivo)
    except Exception:
        pass

    # ── Timeline do turno ──────────────────────────────────────────────────────
    timeline_turno: list = []
    agora_pct = 100
    _TL_INFO = {
        49: ("Produzindo",      "#16a34a"),
        0:  ("Parada",         "#dc2626"),
        4:  ("Limpeza",        "#2563eb"),
        51: ("Ag. Manutentor", "#d97706"),
        52: ("Manutenção",     "#7c3aed"),
    }
    try:
        shift_dur_s = max(1, (efetivo - shift_ini).total_seconds())
        agora_pct   = round(min(100, (agora_dt - shift_ini).total_seconds() / shift_dur_s * 100), 2)

        if not df_logs.empty:
            df_st_tl = df_logs[df_logs["tx_descricao"] == "status_maquina"].copy()
            df_st_tl["_ts"] = pd.to_datetime(df_st_tl["dt_created_at"])
            df_st_tl = (
                df_st_tl[df_st_tl["_ts"] >= pd.Timestamp(shift_ini)]
                .sort_values("_ts")
            )
            rows_tl = list(zip(df_st_tl["_ts"], df_st_tl["nu_valor_bruto"].astype(int)))
            for i_tl, (dt_tl, cod_tl) in enumerate(rows_tl):
                dt_fim_tl = rows_tl[i_tl + 1][0] if i_tl + 1 < len(rows_tl) else efetivo
                ini_s = max(0.0, (dt_tl   - shift_ini).total_seconds())
                fim_s = min(shift_dur_s, (dt_fim_tl - shift_ini).total_seconds())
                if fim_s <= ini_s:
                    continue
                label_tl, color_tl = _TL_INFO.get(cod_tl, (str(cod_tl), "#9ca3af"))
                timeline_turno.append({
                    "status":     cod_tl,
                    "label":      label_tl,
                    "color":      color_tl,
                    "inicio_pct": round(ini_s / shift_dur_s * 100, 2),
                    "fim_pct":    round(fim_s / shift_dur_s * 100, 2),
                    "duracao_s":  round(fim_s - ini_s),
                })
    except Exception:
        pass

    return {
        "id":              machine_id,
        "nome":            ihm["tx_name"],
        "linha":           ihm["linha_nome"],
        "tipo_maquina":    ihm["tipo_maquina"] or None,
        "status":          metrics["status_maquina"],
        "peca_atual":      peca if peca != "PEÇA TEMP" else None,
        "operador":        op_nome,
        "operador_avatar": _avatar(op_nome),
        "manutentor":      man_nome,
        "oee":             metrics["oee"],
        "disponibilidade": metrics["disponibilidade"],
        "performance":     metrics["performance"],
        "qualidade":       metrics["qualidade"],
        "meta":            meta_int,
        "produzido":       prod_int,
        "producao_pct":    prod_pct,
        "velocidade_pph":  velocidade,
        "refugo_turno":    refugo_turno,
        "refugo_pct":      refugo_pct,
        "uptime_s":        uptime_s,
        "parada_ha":       parada_ha,
        "num_paradas":     num_paradas,
        "op_ativa":        op_ativa,
        "producao_horaria": producao_horaria,
        "pareto_paradas":   pareto_paradas,
        "timeline_turno":   timeline_turno,
        "historico_turnos": historico_turnos,
        "agora_pct":        agora_pct,
        "shift_inicio":     shift_ini.strftime("%H:%M"),
        "shift_fim":        efetivo.strftime("%H:%M"),
        "manutencao": {
            "mtbf":   fmt_hm(mtbf_s),
            "mttr":   fmt_hm(mttr_s),
            "mtbf_s": round(mtbf_s),
            "mttr_s": round(mttr_s),
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
    """Retorna nome da linha e lista de turnos (via junction N:N).
    Cada turno inclui id_modelo e lista de linha_ids vinculadas."""
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
        SELECT m.id_modelo, m.tx_nome, m.nu_dia_semana, m.tm_inicio, m.tm_fim, m.bl_ativo
        FROM dbo.tb_turno_modelo m
        JOIN dbo.tb_turno_modelo_linha ml ON ml.id_modelo = m.id_modelo
        WHERE ml.id_linha_producao = :linha
        ORDER BY m.nu_dia_semana, m.tm_inicio
    """, {"linha": line_id})

    def _fmt_time(v):
        if hasattr(v, "strftime"):
            return v.strftime("%H:%M")
        total = int(v.total_seconds())
        return f"{total // 3600:02d}:{(total % 3600) // 60:02d}"

    turnos: list = []
    if not df_modelos.empty:
        # Busca todos os vínculos de uma vez para evitar N+1 queries
        all_ids = [int(r["id_modelo"]) for _, r in df_modelos.iterrows()]
        ids_sql = ",".join(str(x) for x in all_ids)
        df_links = run_query(
            f"SELECT id_modelo, id_linha_producao FROM dbo.tb_turno_modelo_linha WHERE id_modelo IN ({ids_sql})"
        ) if all_ids else None

        links_map: dict = {}
        if df_links is not None and not df_links.empty:
            for _, lr in df_links.iterrows():
                mid = int(lr["id_modelo"])
                links_map.setdefault(mid, []).append(int(lr["id_linha_producao"]))

        for _, t in df_modelos.iterrows():
            id_modelo = int(t["id_modelo"])
            dow = int(t["nu_dia_semana"])
            turnos.append({
                "id_modelo": id_modelo,
                "dia":       _DIAS_SEMANA[dow] if 0 <= dow <= 6 else str(dow),
                "nome":      t["tx_nome"],
                "inicio":    _fmt_time(t["tm_inicio"]),
                "fim":       _fmt_time(t["tm_fim"]),
                "ativo":     bool(t["bl_ativo"]),
                "linha_ids": links_map.get(id_modelo, [line_id]),
            })

    dow_order = {d: i for i, d in enumerate(_DIAS_SEMANA)}
    turnos.sort(key=lambda x: (dow_order.get(x["dia"], 99), x["inicio"]))

    return {
        "id":     line_id,
        "nome":   nome_linha,
        "turnos": turnos,
    }


def update_line_shifts(line_id: int, turnos: list) -> dict:
    """Salva a lista de turnos de uma linha preservando IDs (evita perder vínculos N:N).
    - UPDATE in-place para modelos existentes (id_modelo presente na payload)
    - INSERT para novos turnos (sem id_modelo)
    - Desvincula/exclui modelos removidos pelo usuário
    - Sincroniza a junction table com linha_ids de cada turno
    """
    _ensure_schema()
    dow_map = {d: i for i, d in enumerate(_DIAS_SEMANA)}

    # IDs recebidos do frontend (turnos que o usuário quer manter)
    incoming_ids = {int(t["id_modelo"]) for t in turnos if t.get("id_modelo")}

    # IDs atualmente ligados a esta linha via junction
    df_existing = run_query("""
        SELECT m.id_modelo FROM dbo.tb_turno_modelo m
        JOIN dbo.tb_turno_modelo_linha ml ON ml.id_modelo = m.id_modelo
        WHERE ml.id_linha_producao = :lid
    """, {"lid": line_id})
    existing_ids = {int(r["id_modelo"]) for _, r in df_existing.iterrows()}

    # Modelos removidos pelo usuário
    for mid in existing_ids - incoming_ids:
        # Remove vínculo desta linha
        run_query_update(
            "DELETE FROM dbo.tb_turno_modelo_linha WHERE id_modelo=:mid AND id_linha_producao=:lid",
            {"mid": mid, "lid": line_id},
        )
        # Se ficou órfão (sem outras linhas), remove modelo e ocorrências agendadas
        df_rest = run_query(
            "SELECT id_vmlink FROM dbo.tb_turno_modelo_linha WHERE id_modelo=:mid",
            {"mid": mid},
        )
        if df_rest.empty:
            run_query_update(
                "DELETE FROM dbo.tb_turno_ocorrencia WHERE id_modelo=:mid AND tx_status='agendado'",
                {"mid": mid},
            )
            run_query_update("DELETE FROM dbo.tb_turno_modelo WHERE id_modelo=:mid", {"mid": mid})

    affected_lines = {line_id}

    for entry in turnos:
        dow_target = dow_map.get(entry.get("dia"))
        if dow_target is None:
            continue
        nome  = entry.get("nome") or f"TURNO_{entry['dia'][:3].upper()}"
        ativo = 1 if entry.get("ativo", False) else 0
        ini, fim = entry["inicio"], entry["fim"]
        id_modelo = entry.get("id_modelo")

        # linha_ids desejadas; garante que a linha atual sempre está incluída
        linha_ids = list({int(lid) for lid in (entry.get("linha_ids") or [])} | {line_id})
        affected_lines.update(linha_ids)

        if id_modelo:
            # Atualiza in-place — preserva id_modelo e, portanto, todos os vínculos existentes
            run_query_update("""
                UPDATE dbo.tb_turno_modelo
                SET tx_nome=:nome, nu_dia_semana=:dow, tm_inicio=:ini, tm_fim=:fim, bl_ativo=:ativo
                WHERE id_modelo=:mid
            """, {"nome": nome, "dow": dow_target, "ini": ini, "fim": fim, "ativo": ativo, "mid": id_modelo})
        else:
            # Insere novo modelo
            id_modelo = run_query_insert("""
                INSERT INTO dbo.tb_turno_modelo
                    (tx_nome, id_linha_producao, nu_dia_semana, tm_inicio, tm_fim, bl_ativo)
                OUTPUT INSERTED.id_modelo
                VALUES (:nome, :lid, :dow, :ini, :fim, :ativo)
            """, {"nome": nome, "lid": line_id, "dow": dow_target, "ini": ini, "fim": fim, "ativo": ativo})

        if not id_modelo:
            continue

        # Adiciona vínculos ausentes
        for lid in linha_ids:
            run_query_update("""
                IF NOT EXISTS (SELECT 1 FROM dbo.tb_turno_modelo_linha WHERE id_modelo=:mid AND id_linha_producao=:lid)
                    INSERT INTO dbo.tb_turno_modelo_linha (id_modelo, id_linha_producao) VALUES (:mid, :lid)
            """, {"mid": id_modelo, "lid": lid})

        # Remove vínculos que o usuário desmarcou (exceto a linha atual)
        df_atuais = run_query(
            "SELECT id_linha_producao FROM dbo.tb_turno_modelo_linha WHERE id_modelo=:mid",
            {"mid": id_modelo},
        )
        atuais = {int(r["id_linha_producao"]) for _, r in df_atuais.iterrows()}
        for lid in atuais - set(linha_ids):
            run_query_update(
                "DELETE FROM dbo.tb_turno_modelo_linha WHERE id_modelo=:mid AND id_linha_producao=:lid",
                {"mid": id_modelo, "lid": lid},
            )

    # Regenera ocorrências para todas as linhas afetadas
    for lid in affected_lines:
        _ensure_ocorrencias_futuras(lid)

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
        SELECT m.id_modelo, m.tx_nome, m.nu_dia_semana, m.tm_inicio, m.tm_fim
        FROM dbo.tb_turno_modelo m
        JOIN dbo.tb_turno_modelo_linha ml ON ml.id_modelo = m.id_modelo
        WHERE ml.id_linha_producao = :lid AND m.bl_ativo = 1
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


def get_proximos_turnos(linha_id: int) -> list:
    """Retorna os turnos pendentes de ação do gerente: em_andamento + agendados futuros/presentes.
    Inclui também os últimos 2 turnos finalizados para contexto.
    """
    _ensure_schema()
    agora = datetime.now()

    df = run_query("""
        SELECT id_ocorrencia, tx_nome, dt_inicio, dt_fim,
               dt_real_inicio, dt_real_fim, tx_status, nu_meta, nu_produzido
        FROM dbo.tb_turno_ocorrencia
        WHERE id_linha_producao = :lid
          AND (
            tx_status IN ('em_andamento', 'agendado')
            OR (tx_status = 'finalizado' AND dt_inicio >= DATEADD(HOUR, -48, :agora))
          )
        ORDER BY
          CASE WHEN tx_status = 'em_andamento' THEN 0
               WHEN tx_status = 'agendado'     THEN 1
               ELSE 2
          END,
          dt_inicio
    """, {"lid": linha_id, "agora": agora})

    if df.empty:
        return []

    result = []
    for _, r in df.iterrows():
        result.append({
            "id_ocorrencia": int(r["id_ocorrencia"]),
            "nome":          r["tx_nome"],
            "dt_inicio":     r["dt_inicio"].isoformat() if r["dt_inicio"] is not None else None,
            "dt_fim":        r["dt_fim"].isoformat()    if r["dt_fim"]    is not None else None,
            "dt_real_inicio": r["dt_real_inicio"].isoformat() if r["dt_real_inicio"] is not None else None,
            "dt_real_fim":    r["dt_real_fim"].isoformat()    if r["dt_real_fim"]    is not None else None,
            "status":        r["tx_status"],
            "meta":          int(r["nu_meta"]),
            "produzido":     int(r["nu_produzido"]),
        })
    return result


def abrir_turno_manual(id_ocorrencia: int) -> dict:
    """Abre um turno manualmente pelo gerente."""
    _ensure_schema()
    df = run_query("""
        SELECT id_linha_producao, tx_status
        FROM dbo.tb_turno_ocorrencia
        WHERE id_ocorrencia = :id
    """, {"id": id_ocorrencia})
    if df.empty:
        raise ValueError(f"Ocorrência {id_ocorrencia} não encontrada.")
    row = df.iloc[0]
    if row["tx_status"] != "agendado":
        raise ValueError(f"Turno está com status '{row['tx_status']}', não pode ser iniciado.")
    linha_id = int(row["id_linha_producao"])
    _abrir_turno(id_ocorrencia, linha_id)
    _recalcular_metas_linha(linha_id)
    return {"ok": True}


def fechar_turno_manual(id_ocorrencia: int) -> dict:
    """Fecha um turno manualmente pelo gerente."""
    _ensure_schema()
    df = run_query("""
        SELECT id_linha_producao, tx_status
        FROM dbo.tb_turno_ocorrencia
        WHERE id_ocorrencia = :id
    """, {"id": id_ocorrencia})
    if df.empty:
        raise ValueError(f"Ocorrência {id_ocorrencia} não encontrada.")
    row = df.iloc[0]
    if row["tx_status"] != "em_andamento":
        raise ValueError(f"Turno está com status '{row['tx_status']}', não está em andamento.")
    linha_id = int(row["id_linha_producao"])
    _fechar_turno(id_ocorrencia, linha_id)
    return {"ok": True}


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


def link_modelo_to_linhas(id_modelo: int, linha_ids: list) -> dict:
    """Vincula/desvincula um template de turno a múltiplas linhas (N:N).
    Não desfaz a linha primária (id_linha_producao no modelo).
    Regenera ocorrências para linhas recém-adicionadas.
    """
    _ensure_schema()
    df_old = run_query(
        "SELECT id_linha_producao FROM dbo.tb_turno_modelo_linha WHERE id_modelo = :mid",
        {"mid": id_modelo},
    )
    old_ids = {int(r["id_linha_producao"]) for _, r in df_old.iterrows()}
    new_ids = set(int(x) for x in linha_ids)

    for lid in old_ids - new_ids:
        run_query_update(
            "DELETE FROM dbo.tb_turno_modelo_linha WHERE id_modelo=:mid AND id_linha_producao=:lid",
            {"mid": id_modelo, "lid": lid},
        )

    for lid in new_ids - old_ids:
        run_query_update("""
            IF NOT EXISTS (SELECT 1 FROM dbo.tb_turno_modelo_linha WHERE id_modelo=:mid AND id_linha_producao=:lid)
                INSERT INTO dbo.tb_turno_modelo_linha (id_modelo, id_linha_producao) VALUES (:mid, :lid)
        """, {"mid": id_modelo, "lid": lid})
        _ensure_ocorrencias_futuras_from_modelo(id_modelo, lid)

    return {"ok": True, "linhas_vinculadas": list(new_ids)}


def _ensure_ocorrencias_futuras_from_modelo(id_modelo: int, linha_id: int) -> None:
    """Gera ocorrências futuras de um modelo específico para uma linha específica."""
    _ensure_schema()
    df = run_query("""
        SELECT id_modelo, tx_nome, nu_dia_semana, tm_inicio, tm_fim
        FROM dbo.tb_turno_modelo
        WHERE id_modelo = :mid AND bl_ativo = 1
    """, {"mid": id_modelo})
    if df.empty:
        return

    agora   = datetime.now()
    w_start = agora.date() - timedelta(days=1)
    w_end   = agora.date() + timedelta(weeks=4)

    for _, m in df.iterrows():
        dow_target = int(m["nu_dia_semana"])
        nome_turno = m["tx_nome"]

        def _to_hm(v):
            if hasattr(v, "hour"):
                return v.hour, v.minute
            total = int(v.total_seconds())
            return total // 3600, (total % 3600) // 60

        hi, hm = _to_hm(m["tm_inicio"])
        fi, fm = _to_hm(m["tm_fim"])

        days_to_first = (dow_target - w_start.weekday()) % 7
        current_date  = w_start + timedelta(days=days_to_first)

        while current_date <= w_end:
            dt_inicio   = datetime.combine(current_date, time(hi, hm))
            dt_fim_base = datetime.combine(current_date, time(fi, fm))
            dt_fim      = dt_fim_base + timedelta(days=1) if (fi, fm) < (hi, hm) else dt_fim_base

            run_query_update("""
                IF NOT EXISTS (
                    SELECT 1 FROM dbo.tb_turno_ocorrencia
                    WHERE id_modelo = :mid AND id_linha_producao = :lid AND dt_inicio = :di
                )
                INSERT INTO dbo.tb_turno_ocorrencia
                    (id_modelo, id_linha_producao, tx_nome, dt_inicio, dt_fim, tx_status)
                VALUES (:mid, :lid, :nome, :di, :df, 'agendado')
            """, {
                "mid": id_modelo, "lid": linha_id,
                "nome": nome_turno, "di": dt_inicio, "df": dt_fim,
            })
            current_date += timedelta(weeks=1)


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
    """Informações do turno atual (lê de tb_turno_ocorrencia).

    Retorna:
        nome, encerra_em, progresso_pct, nu_meta, status
        status: 'em_andamento' | 'aguardando_inicio' | '-'
    Para turnos em_andamento, usa dt_real_inicio + duração teórica para calcular
    progresso e tempo restante com base no tempo real.
    """
    _ensure_schema()
    agora = datetime.now()
    # Prioriza turno em_andamento; se não houver, mostra o próximo agendado
    df = run_query("""
        SELECT TOP 1 id_ocorrencia, tx_nome, dt_inicio, dt_fim,
                     dt_real_inicio, tx_status, nu_meta
        FROM dbo.tb_turno_ocorrencia
        WHERE tx_status IN ('em_andamento', 'agendado')
          AND (tx_status = 'em_andamento' OR (dt_inicio <= :agora AND dt_fim >= :agora))
        ORDER BY
          CASE WHEN tx_status = 'em_andamento' THEN 0 ELSE 1 END,
          dt_inicio
    """, {"agora": agora})

    if df.empty:
        return {"nome": "-", "encerra_em": "-", "progresso_pct": 0, "nu_meta": 0, "status": "-"}

    row       = df.iloc[0]
    dt_inicio = row["dt_inicio"]
    dt_fim    = row["dt_fim"]
    duracao_s = (dt_fim - dt_inicio).total_seconds()
    status    = row["tx_status"]

    if status == "em_andamento" and row["dt_real_inicio"] is not None:
        # Usa tempo real: início real + duração teórica = fim esperado
        dt_real_ini  = row["dt_real_inicio"]
        expected_end = dt_real_ini + (dt_fim - dt_inicio)
        decorrido_s  = (agora - dt_real_ini).total_seconds()
        progresso    = int(100 * decorrido_s / duracao_s) if duracao_s else 0
        restante_s   = max(0, (expected_end - agora).total_seconds())
    else:
        # Turno agendado aguardando início — mostra tempo até início teórico
        decorrido_s = 0
        progresso   = 0
        restante_s  = max(0, (dt_fim - agora).total_seconds())

    horas, resto = divmod(int(restante_s), 3600)
    encerra_em   = f"{horas:02d}:{resto // 60:02d}h"

    return {
        "nome":          row["tx_nome"],
        "encerra_em":    encerra_em,
        "progresso_pct": min(100, max(0, progresso)),
        "nu_meta":       int(row["nu_meta"]),
        "status":        "aguardando_inicio" if status == "agendado" else "em_andamento",
    }


def get_overview_linhas() -> list:
    """Lista de linhas de produção com suas máquinas e métricas."""
    df_linhas = get_lines_df()
    resultado = []

    for _, linha in df_linhas.iterrows():
        line_id    = int(linha["id_linha_producao"])
        df_machines = get_machines_by_line_df(line_id)

        df_term_ov = run_query("""
            SELECT DISTINCT r.id_ihm
            FROM dbo.tb_peca_rota r
            JOIN dbo.tb_peca p ON p.id_peca = r.id_peca
            WHERE p.id_linha_producao = :lid
              AND r.nu_ordem = (
                  SELECT MAX(r2.nu_ordem) FROM dbo.tb_peca_rota r2 WHERE r2.id_peca = r.id_peca
              )
        """, {"lid": line_id})
        term_ids_ov: set = set(int(r["id_ihm"]) for _, r in df_term_ov.iterrows())
        if not term_ids_ov:
            term_ids_ov = set(int(r["id_ihm"]) for _, r in df_machines.iterrows())

        maquinas        = []
        total_produzido = 0
        total_meta      = 0

        for _, machine in df_machines.iterrows():
            machine_id = int(machine["id_ihm"])
            metrics    = get_metrics_machine(machine_id)

            produzido = metrics["produzido"] if isinstance(metrics["produzido"], (int, float)) else 0
            reprovado = metrics["reprovado"] if isinstance(metrics["reprovado"], (int, float)) else 0
            meta      = metrics["meta"]      if isinstance(metrics["meta"],      (int, float)) else 0
            if machine_id in term_ids_ov:
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

        df_term_h = run_query("""
            SELECT DISTINCT r.id_ihm
            FROM dbo.tb_peca_rota r
            JOIN dbo.tb_peca p ON p.id_peca = r.id_peca
            WHERE p.id_linha_producao = :lid
              AND r.nu_ordem = (
                  SELECT MAX(r2.nu_ordem) FROM dbo.tb_peca_rota r2 WHERE r2.id_peca = r.id_peca
              )
        """, {"lid": line_id})
        term_ids_h: set = set(int(r["id_ihm"]) for _, r in df_term_h.iterrows())
        if not term_ids_h:
            term_ids_h = set(int(r["id_ihm"]) for _, r in df_machines.iterrows())

        maquinas        = []
        total_produzido = 0

        for _, machine in df_machines.iterrows():
            machine_id = int(machine["id_ihm"])
            metrics    = get_metrics_machine(machine_id, data_inicio=data_inicio, data_fim=data_fim)
            pareto_maq = get_pareto_paradas(machine_id, data_inicio, data_fim)

            produzido = metrics["produzido"] if isinstance(metrics["produzido"], (int, float)) else 0
            meta      = metrics["meta"]      if isinstance(metrics["meta"],      (int, float)) else 0
            if machine_id in term_ids_h:
                total_produzido += produzido

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
                "pareto_paradas":  pareto_maq,
            })

        # Pareto consolidado da linha (agrega os paretos de cada máquina)
        parada_agg: dict = {}
        for m in maquinas:
            for p in m.get("pareto_paradas", []):
                parada_agg[p["motivo"]] = parada_agg.get(p["motivo"], 0) + p["minutos"]
        total_min_linha = sum(parada_agg.values())
        acum_l = 0.0
        pareto_linha: list = []
        for mot, mins in sorted(parada_agg.items(), key=lambda x: x[1], reverse=True):
            pct_l = round(100 * mins / total_min_linha, 1) if total_min_linha > 0 else 0
            acum_l += pct_l
            pareto_linha.append({
                "motivo": mot, "minutos": round(mins, 1),
                "percentual": pct_l, "acumulado": round(min(acum_l, 100.0), 1),
            })

        # Ordens do período para esta linha
        df_ordens_l = run_query("""
            SELECT nu_numero_op, tx_peca, nu_quantidade, tx_status,
                   COALESCE(nu_produzido, 0) AS nu_produzido,
                   COALESCE(nu_refugo,    0) AS nu_refugo
            FROM dbo.tb_ordem_producao
            WHERE id_linha_producao = :lid
              AND (dt_criacao BETWEEN :inicio AND :fim
                   OR  dt_inicio BETWEEN :inicio AND :fim
                   OR  tx_status = 'em_producao')
            ORDER BY dt_criacao DESC
        """, {"lid": line_id, "inicio": data_inicio, "fim": data_fim})
        ordens_l: list = []
        for _, o in df_ordens_l.iterrows():
            qtd  = int(o["nu_quantidade"])
            prod = int(o["nu_produzido"])
            ordens_l.append({
                "numero":     o["nu_numero_op"],
                "peca":       o["tx_peca"],
                "quantidade": qtd,
                "produzido":  prod,
                "refugo":     int(o["nu_refugo"]),
                "status":     o["tx_status"],
                "conclusao":  round(100 * prod / qtd) if qtd > 0 else 0,
            })

        # Meta = soma das quantidades das OPs (não soma de metas por máquina,
        # pois a mesma peça passa por várias máquinas e duplicaria o valor)
        total_meta = sum(o["quantidade"] for o in ordens_l) if ordens_l else 0
        realizado_pct = int(100 * total_produzido / total_meta) if total_meta else 0

        # OEE e componentes médios da linha (média das máquinas)
        oee_vals  = [m["oee"]             for m in maquinas if isinstance(m.get("oee"),             (int, float))]
        disp_vals = [m["disponibilidade"] for m in maquinas if isinstance(m.get("disponibilidade"), (int, float))]
        perf_vals = [m["performance"]     for m in maquinas if isinstance(m.get("performance"),     (int, float))]
        qual_vals = [m["qualidade"]       for m in maquinas if isinstance(m.get("qualidade"),       (int, float))]
        oee_linha  = round(sum(oee_vals)  / len(oee_vals),  1) if oee_vals  else None
        disp_linha = round(sum(disp_vals) / len(disp_vals), 1) if disp_vals else None
        perf_linha = round(sum(perf_vals) / len(perf_vals), 1) if perf_vals else None
        qual_linha = round(sum(qual_vals) / len(qual_vals), 1) if qual_vals else None

        linhas.append({
            "id":              line_id,
            "nome":            linha["tx_name"],
            "realizado":       total_produzido,
            "meta_total":      total_meta,
            "realizado_pct":   realizado_pct,
            "oee":             oee_linha,
            "disponibilidade": disp_linha,
            "performance":     perf_linha,
            "qualidade":       qual_linha,
            "maquinas":        maquinas,
            "pareto_paradas":  pareto_linha,
            "ordens":          ordens_l,
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
# HISTÓRICO — DETALHADO
# =========================

def get_producao_hora_maquina(maquina_id: int, dt_inicio: datetime, dt_fim: datetime) -> list:
    """Produção hora a hora de uma máquina (delta de total_produzido). Retorna [{hora, produzido}]."""
    df = run_query("""
        SELECT
            DATEADD(HOUR, DATEDIFF(HOUR, 0, lr.dt_created_at), 0) AS hora,
            MAX(lr.nu_valor_bruto) - MIN(lr.nu_valor_bruto) AS producao
        FROM dbo.tb_log_registrador lr
        JOIN dbo.tb_registrador r ON r.id_registrador = lr.id_registrador
        WHERE lr.id_ihm = :id
          AND r.tx_descricao  = 'total_produzido'
          AND lr.dt_created_at >= :inicio
          AND lr.dt_created_at <= :fim
        GROUP BY DATEADD(HOUR, DATEDIFF(HOUR, 0, lr.dt_created_at), 0)
        ORDER BY hora
    """, {"id": maquina_id, "inicio": dt_inicio, "fim": dt_fim})
    return [
        {
            "hora": row["hora"].strftime("%H:%M") if hasattr(row["hora"], "strftime") else str(row["hora"]),
            "produzido": max(0, int(row["producao"])) if row["producao"] is not None else 0,
        }
        for _, row in df.iterrows()
    ]


def get_pareto_paradas(maquina_id: int, dt_inicio: datetime, dt_fim: datetime) -> list:
    """Pareto de motivos de parada usando state-machine sobre os logs.

    Lê status_maquina e motivo_parada separadamente e correlaciona por
    intervalo temporal — suporta o fluxo real assíncrono onde o operador
    informa o motivo alguns segundos APÓS a parada ocorrer.
    """
    df = run_query("""
        SELECT lr.dt_created_at, lr.nu_valor_bruto, r.tx_descricao
        FROM dbo.tb_log_registrador lr
        JOIN dbo.tb_registrador r ON r.id_registrador = lr.id_registrador
        WHERE lr.id_ihm         = :id
          AND lr.dt_created_at >= :inicio
          AND lr.dt_created_at <= :fim
          AND r.tx_descricao   IN ('status_maquina', 'motivo_parada')
        ORDER BY lr.dt_created_at
    """, {"id": maquina_id, "inicio": dt_inicio, "fim": dt_fim})

    if df.empty:
        return []

    df_st = df[df["tx_descricao"] == "status_maquina"].sort_values("dt_created_at")
    df_mo = df[df["tx_descricao"] == "motivo_parada"].sort_values("dt_created_at")

    # Lista de (timestamp, motivo_cod) para varredura durante cada intervalo de parada
    motivo_log: list = list(zip(
        pd.to_datetime(df_mo["dt_created_at"]),
        df_mo["nu_valor_bruto"].astype(int),
    ))
    mo_ptr = 0  # ponteiro de varredura — avança monotonicamente com o tempo

    status_rows = list(zip(
        pd.to_datetime(df_st["dt_created_at"]),
        df_st["nu_valor_bruto"].astype(int),
    ))

    # Estados transitórios (aguardam motivo definitivo para fechar o segmento):
    #   0  = Máquina Parada   — motivo operacional (1-32) chega depois
    #   52 = Em Manutenção    — código 3300+ chega depois
    # Status 51 (Ag. Manutentor) é PERMANENTE: agrega sua própria duração.
    _TRANS = {0, 52}

    durations: dict = {}
    status_ant: Optional[int] = None
    estado_atual: Optional[int] = None
    inicio_seg:   Optional[Any] = None
    label_cod:    int           = 0

    for dt, cod in status_rows:
        # ── Passo 1: transições de estado ──────────────────────────────────────

        if status_ant == 49 and cod != 49:
            # Saindo de produção → abre segmento
            estado_atual = cod
            inicio_seg   = dt
            label_cod    = 0 if cod in _TRANS else cod

        elif status_ant is not None and status_ant != 49 and cod != 49:
            if cod == estado_atual and cod in _TRANS:
                # Mesmo estado transitório re-inserido (simulador): não faz nada
                pass

            elif estado_atual == 51 and cod == 52:
                # Ag. Manutentor → Em Manutenção: fecha 51, abre segmento transitório 52
                secs = (dt - inicio_seg).total_seconds()
                if secs > 0:
                    durations[51] = durations.get(51, 0) + secs
                estado_atual = 52
                inicio_seg   = dt
                label_cod    = 0

            elif estado_atual in _TRANS and cod not in _TRANS and cod not in (0, 49):
                # Motivo definitivo do estado transitório: só atualiza label
                label_cod = cod

            elif cod in _TRANS and cod != estado_atual:
                # Entrando num estado transitório diferente (edge case)
                secs = (dt - inicio_seg).total_seconds()
                if secs > 0:
                    durations[label_cod] = durations.get(label_cod, 0) + secs
                estado_atual = cod
                inicio_seg   = dt
                label_cod    = 0

            else:
                # Transição entre estados permanentes
                secs = (dt - inicio_seg).total_seconds()
                if secs > 0:
                    durations[label_cod] = durations.get(label_cod, 0) + secs
                estado_atual = cod
                inicio_seg   = dt
                label_cod    = 0 if cod in _TRANS else cod

        # ── Passo 2: avança ponteiro de motivo (assíncrono / simulador) ────────
        while mo_ptr < len(motivo_log):
            m_dt, m_cod = motivo_log[mo_ptr]
            if m_dt > dt:
                break
            if (inicio_seg is not None
                    and m_dt >= inicio_seg
                    and m_cod not in (0, 49)
                    and m_cod not in _TRANS
                    and estado_atual in _TRANS):
                label_cod = m_cod
            mo_ptr += 1

        # ── Passo 3: fecha segmento ao retornar à produção ─────────────────────
        if status_ant is not None and status_ant != 49 and cod == 49 and inicio_seg is not None:
            secs = (dt - inicio_seg).total_seconds()
            if secs > 0:
                durations[label_cod] = durations.get(label_cod, 0) + secs
            estado_atual = None
            inicio_seg   = None
            label_cod    = 0

        status_ant = cod

    if not durations:
        return []

    df_nomes = run_query("""
        SELECT nu_cod_motivo_parada, tx_motivo_parada
        FROM dbo.tb_depara_motivo_parada WHERE id_ihm = :id
    """, {"id": maquina_id})
    nomes = {int(r["nu_cod_motivo_parada"]): r["tx_motivo_parada"] for _, r in df_nomes.iterrows()}

    total_s  = sum(durations.values())
    sorted_d = sorted(durations.items(), key=lambda x: x[1], reverse=True)
    result: list = []
    acum = 0.0
    for cod, secs in sorted_d:
        nome = nomes.get(cod, f"Motivo {cod}" if cod != 0 else "Sem motivo")
        pct  = round(100 * secs / total_s, 1) if total_s > 0 else 0
        acum += pct
        result.append({
            "motivo":     nome,
            "minutos":    round(secs / 60, 1),
            "percentual": pct,
            "acumulado":  round(min(acum, 100.0), 1),
        })
    return result


def get_ordens_funil(dt_inicio: datetime, dt_fim: datetime) -> dict:
    """Contagem de ordens por status para o funil. Retorna {fila, em_producao, finalizado, cancelado}."""
    df = run_query("""
        SELECT tx_status,
               COUNT(*)                                             AS qty,
               COALESCE(SUM(nu_quantidade), 0)                      AS pecas,
               COALESCE(SUM(nu_produzido),  0)                      AS produzido
        FROM dbo.tb_ordem_producao
        WHERE dt_criacao  BETWEEN :inicio AND :fim
           OR dt_inicio   BETWEEN :inicio AND :fim
           OR dt_fim      BETWEEN :inicio AND :fim
           OR tx_status IN ('em_producao', 'fila')
        GROUP BY tx_status
    """, {"inicio": dt_inicio, "fim": dt_fim})
    counts: dict = {}
    for _, r in df.iterrows():
        counts[r["tx_status"]] = {
            "qty":       int(r["qty"]),
            "pecas":     int(r["pecas"])    if r["pecas"]    is not None else 0,
            "produzido": int(r["produzido"]) if r["produzido"] is not None else 0,
        }
    return {s: counts.get(s, {"qty": 0, "pecas": 0, "produzido": 0})
            for s in ("fila", "em_producao", "finalizado", "cancelado")}


def get_historico_linha_detalhe(linha_id: int, dt_inicio: datetime, dt_fim: datetime,
                                turno_id: int = None) -> dict:
    """Payload detalhado de uma linha de produção para o período.
    Se turno_id fornecido, restringe o intervalo ao tempo real do turno.
    """
    if turno_id is not None:
        df_oc = run_query("""
            SELECT dt_real_inicio, dt_real_fim, dt_inicio, dt_fim
            FROM dbo.tb_turno_ocorrencia
            WHERE id_ocorrencia = :id
        """, {"id": turno_id})
        if not df_oc.empty:
            r = df_oc.iloc[0]
            dt_inicio = r["dt_real_inicio"] if r["dt_real_inicio"] is not None else r["dt_inicio"]
            dt_fim    = r["dt_real_fim"]    if r["dt_real_fim"]    is not None else (r["dt_fim"] if r["dt_fim"] is not None else dt_fim)
    df_l = run_query("""
        SELECT tx_name FROM dbo.tb_linha_producao WHERE id_linha_producao = :id
    """, {"id": linha_id})
    if df_l.empty:
        return {}

    nome        = df_l.iloc[0]["tx_name"]
    df_machines = get_machines_by_line_df(linha_id)

    # Máquinas terminais do roteiro (última etapa): apenas elas representam peças acabadas.
    # A mesma peça passa por todas as máquinas, então somar todas multiplicaria a contagem.
    df_term_pre = run_query("""
        SELECT DISTINCT r.id_ihm
        FROM dbo.tb_peca_rota r
        JOIN dbo.tb_peca p ON p.id_peca = r.id_peca
        WHERE p.id_linha_producao = :lid
          AND r.nu_ordem = (
              SELECT MAX(r2.nu_ordem) FROM dbo.tb_peca_rota r2 WHERE r2.id_peca = r.id_peca
          )
    """, {"lid": linha_id})
    term_ids_set: set = set(int(r["id_ihm"]) for _, r in df_term_pre.iterrows())
    if not term_ids_set:
        term_ids_set = set(int(r["id_ihm"]) for _, r in df_machines.iterrows())

    maquinas        = []
    total_produzido = 0
    total_reprovado = 0
    all_oees: list  = []

    all_paradas_agg: dict = {}  # motivo -> minutos (agregado linha)

    for _, machine in df_machines.iterrows():
        mid     = int(machine["id_ihm"])
        metrics = get_metrics_machine(mid, data_inicio=dt_inicio, data_fim=dt_fim)
        prod    = metrics["produzido"] if isinstance(metrics["produzido"], (int, float)) else 0
        repr_   = metrics["reprovado"] if isinstance(metrics["reprovado"], (int, float)) else 0
        oee     = metrics["oee"]       if isinstance(metrics["oee"],       (int, float)) else None
        # Só a máquina terminal conta como saída da linha; refugo acumula de todas as etapas.
        if mid in term_ids_set:
            total_produzido += prod
        total_reprovado += repr_
        if oee is not None:
            all_oees.append(oee)
        pareto_maq = get_pareto_paradas(mid, dt_inicio, dt_fim)
        for p in pareto_maq:
            all_paradas_agg[p["motivo"]] = all_paradas_agg.get(p["motivo"], 0) + p["minutos"]
        maquinas.append({
            "id":              mid,
            "nome":            machine["tx_name"],
            "oee":             oee,
            "disponibilidade": metrics["disponibilidade"],
            "qualidade":       metrics["qualidade"],
            "performance":     metrics["performance"],
            "produzido":       prod,
            "reprovado":       repr_,
            "meta":            metrics["meta"],
            "status":          metrics["status_maquina"],
            "pareto_paradas":  pareto_maq,
        })

    # Pareto consolidado da linha
    total_min = sum(all_paradas_agg.values())
    sorted_agg = sorted(all_paradas_agg.items(), key=lambda x: x[1], reverse=True)
    acum = 0.0
    pareto_linha = []
    for mot, mins in sorted_agg:
        pct = round(100 * mins / total_min, 1) if total_min > 0 else 0
        acum += pct
        pareto_linha.append({
            "motivo":     mot,
            "minutos":    round(mins, 1),
            "percentual": pct,
            "acumulado":  round(min(acum, 100.0), 1),
        })

    # Produção hora a hora — máquinas terminais da rota (já calculado acima)
    term_ids = list(term_ids_set)

    hourly_agg: dict = {}
    for tid in term_ids:
        for entry in get_producao_hora_maquina(tid, dt_inicio, dt_fim):
            h = entry["hora"]
            hourly_agg[h] = hourly_agg.get(h, 0) + entry["produzido"]

    df_meta_hora = run_query(f"""
        SELECT COALESCE(SUM(c.nu_producao_teorica), 0) AS meta_hora
        FROM dbo.tb_config_producao_teorica c
        WHERE c.id_ihm IN ({','.join(str(i) for i in term_ids)})
    """, {}) if term_ids else None
    meta_hora = int(df_meta_hora.iloc[0]["meta_hora"]) if df_meta_hora is not None and not df_meta_hora.empty else 0

    hourly = sorted(
        [{"hora": h, "produzido": v, "meta": meta_hora} for h, v in hourly_agg.items()],
        key=lambda x: x["hora"],
    )

    # Turnos do período
    df_turnos = run_query("""
        SELECT tx_nome, dt_inicio, dt_fim, tx_status, nu_meta, nu_produzido
        FROM dbo.tb_turno_ocorrencia
        WHERE id_linha_producao = :lid
          AND dt_inicio >= :inicio AND dt_fim <= :fim
        ORDER BY dt_inicio
    """, {"lid": linha_id, "inicio": dt_inicio, "fim": dt_fim})

    def _fmt(d):
        return d.strftime("%d/%m %H:%M") if hasattr(d, "strftime") else str(d)

    turnos = []
    for _, t in df_turnos.iterrows():
        nu_m = int(t["nu_meta"]) if t["nu_meta"] is not None else 0
        nu_p = int(t["nu_produzido"]) if t["nu_produzido"] is not None and not pd.isna(t["nu_produzido"]) else 0
        turnos.append({
            "nome":      t["tx_nome"],
            "inicio":    _fmt(t["dt_inicio"]),
            "fim":       _fmt(t["dt_fim"]),
            "status":    t["tx_status"],
            "meta":      nu_m,
            "produzido": nu_p,
            "aderencia": round(100 * nu_p / nu_m, 1) if nu_m > 0 else None,
        })

    # Ordens do período
    df_ordens = run_query("""
        SELECT nu_numero_op, tx_peca, nu_quantidade, tx_status,
               COALESCE(nu_produzido, 0) AS nu_produzido,
               COALESCE(nu_refugo,    0) AS nu_refugo
        FROM dbo.tb_ordem_producao
        WHERE id_linha_producao = :lid
          AND (dt_criacao BETWEEN :inicio AND :fim
               OR  dt_inicio BETWEEN :inicio AND :fim
               OR  tx_status = 'em_producao')
        ORDER BY dt_criacao DESC
    """, {"lid": linha_id, "inicio": dt_inicio, "fim": dt_fim})

    ordens = []
    for _, o in df_ordens.iterrows():
        qtd  = int(o["nu_quantidade"])
        prod = int(o["nu_produzido"])
        ordens.append({
            "numero":     o["nu_numero_op"],
            "peca":       o["tx_peca"],
            "quantidade": qtd,
            "produzido":  prod,
            "refugo":     int(o["nu_refugo"]),
            "status":     o["tx_status"],
            "conclusao":  round(100 * prod / qtd) if qtd > 0 else 0,
        })

    taxa_rej  = round(100 * total_reprovado / (total_produzido + total_reprovado), 1) \
                if (total_produzido + total_reprovado) > 0 else 0.0
    oee_linha = round(sum(all_oees) / len(all_oees), 1) if all_oees else None

    return {
        "id":                   linha_id,
        "nome":                 nome,
        "oee":                  oee_linha,
        "maquinas":             maquinas,
        "producao_hora_a_hora": hourly,
        "turnos":               turnos,
        "ordens":               ordens,
        "taxa_rejeicao":        taxa_rej,
        "total_produzido":      total_produzido,
        "total_reprovado":      total_reprovado,
        "pareto_paradas":       pareto_linha,
    }


def get_historico_maquina_detalhe(maquina_id: int, dt_inicio: datetime, dt_fim: datetime) -> dict:
    """Payload detalhado de uma máquina para o período."""
    df_m = run_query("""
        SELECT tx_name, id_linha_producao FROM dbo.tb_ihm WHERE id_ihm = :id
    """, {"id": maquina_id})
    if df_m.empty:
        return {}

    nome    = df_m.iloc[0]["tx_name"]
    linha_id = int(df_m.iloc[0]["id_linha_producao"])

    # Nome da linha
    df_ln = run_query("SELECT tx_name FROM dbo.tb_linha_producao WHERE id_linha_producao = :id", {"id": linha_id})
    nome_linha = df_ln.iloc[0]["tx_name"] if not df_ln.empty else ""

    metrics = get_metrics_machine(maquina_id, data_inicio=dt_inicio, data_fim=dt_fim)
    hourly  = get_producao_hora_maquina(maquina_id, dt_inicio, dt_fim)
    pareto  = get_pareto_paradas(maquina_id, dt_inicio, dt_fim)

    return {
        "id":                   maquina_id,
        "nome":                 nome,
        "linha":                nome_linha,
        "oee":                  metrics["oee"],
        "disponibilidade":      metrics["disponibilidade"],
        "qualidade":            metrics["qualidade"],
        "performance":          metrics["performance"],
        "produzido":            metrics["produzido"],
        "reprovado":            metrics["reprovado"],
        "meta":                 metrics["meta"],
        "status":               metrics["status_maquina"],
        "operador":             metrics.get("operador", "-"),
        "producao_hora_a_hora": hourly,
        "pareto_paradas":       pareto,
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

    # Distribuição de status
    status_dist = {"produzindo": 0, "alerta": 0, "parada": 0, "manutencao": 0, "limpeza": 0}
    for m in maquinas:
        s = (m["status"] or "").lower()
        if "produz" in s:
            status_dist["produzindo"] += 1
        elif "alerta" in s or "aguardando" in s:
            status_dist["alerta"] += 1
        elif "manuten" in s:
            status_dist["manutencao"] += 1
        elif "limpeza" in s:
            status_dist["limpeza"] += 1
        elif s and s != "-":
            status_dist["parada"] += 1

    # Status geral dinâmico
    n_criticos = status_dist["parada"] + status_dist["manutencao"] + status_dist["alerta"]
    n_total = len(maquinas)
    if n_total == 0:
        status_geral = "Sem máquinas"
    elif n_criticos == 0:
        status_geral = "Operação Normal"
    elif n_criticos == 1:
        status_geral = "1 máquina requer atenção"
    elif n_criticos <= n_total // 2:
        status_geral = f"{n_criticos} máquinas requerem atenção"
    else:
        status_geral = "Atenção — múltiplas paradas"

    # Qualidade global (% de peças boas)
    total_rejeitado = sum(
        m["rejeitos"] for m in maquinas
        if isinstance(m["rejeitos"], (int, float))
    )
    total_all = total_produzido + total_rejeitado
    qualidade_global = round(total_produzido / total_all * 100, 1) if total_all > 0 else None

    # OPs ativas desta linha — usa tb_op_peca_producao para rastreamento em tempo real
    ops_ativas: list = []
    try:
        df_ops = run_query("""
            SELECT o.id_ordem, o.nu_numero_op, o.tx_peca, o.nu_quantidade,
                   o.nu_produzido, o.nu_refugo, o.tx_status, o.nu_prioridade,
                   COALESCE(rt.nu_produzido_rt, 0) AS nu_produzido_rt,
                   COALESCE(rt.nu_refugo_rt,   0) AS nu_refugo_rt
            FROM dbo.tb_ordem_producao o
            LEFT JOIN (
                SELECT id_ordem,
                    SUM(CASE WHEN nu_etapa_atual >= nu_etapas_total AND nu_etapa_erro IS NULL THEN 1 ELSE 0 END) AS nu_produzido_rt,
                    SUM(CASE WHEN nu_etapa_erro  IS NOT NULL THEN 1 ELSE 0 END) AS nu_refugo_rt
                FROM dbo.tb_op_peca_producao
                GROUP BY id_ordem
            ) rt ON rt.id_ordem = o.id_ordem
            WHERE o.id_linha_producao = :id
              AND o.tx_status NOT IN ('concluida', 'cancelada')
            ORDER BY o.nu_prioridade DESC, o.dt_criacao
        """, {"id": line_id})
        for _, op in df_ops.iterrows():
            qtd         = int(op["nu_quantidade"])   if not pd.isna(op["nu_quantidade"])   else 0
            prod_rt     = int(op["nu_produzido_rt"]) if not pd.isna(op["nu_produzido_rt"]) else 0
            prod_static = int(op["nu_produzido"])    if not pd.isna(op["nu_produzido"])    else 0
            # Preferir contagem em tempo real; cair no valor estático se a tabela não tiver dados
            prod   = prod_rt if prod_rt > 0 else prod_static
            refugo_rt     = int(op["nu_refugo_rt"]) if not pd.isna(op["nu_refugo_rt"]) else 0
            refugo_static = int(op["nu_refugo"])     if not pd.isna(op["nu_refugo"])     else 0
            refugo = refugo_rt if refugo_rt > 0 else refugo_static
            ops_ativas.append({
                "id":         int(op["id_ordem"]),
                "numero":     op["nu_numero_op"],
                "peca":       op["tx_peca"],
                "quantidade": qtd,
                "produzido":  prod,
                "refugo":     refugo,
                "status":     op["tx_status"],
                "progresso":  round(prod / qtd * 100, 1) if qtd > 0 else 0,
            })
    except Exception:
        pass

    return {
        "id":                 line_id,
        "nome":               nome_linha,
        "status_geral":       status_geral,
        "ultima_atualizacao": datetime.now().strftime("%H:%M:%S"),
        "kpis": {
            "oee_global":       oee_global,
            "oee_variacao":     None,
            "producao_hoje":    total_produzido,
            "producao_meta":    total_meta,
            "previsao_termino": None,
            "maquinas_ativas":  maquinas_ativas,
            "maquinas_total":   len(maquinas),
            "qualidade_global": qualidade_global,
            "status_dist":      status_dist,
            "equipe":           equipe,
            "equipe_extras":    max(0, len(operadores_vistos) - 5),
            "supervisor":       None,
        },
        "ops_ativas": ops_ativas,
        "maquinas":   maquinas,
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
        # Sem OPs ativas: preserva nu_meta_turno (acumulado do turno), apenas zera nu_meta_ativo
        try:
            run_query_update("""
                UPDATE dbo.tb_ihm SET nu_meta_ativo = 0
                WHERE id_linha_producao = :lid
            """, {"lid": linha_id})
        except Exception:
            pass
        return

    # Estado atual das máquinas para fórmula de acumulação
    df_curr = run_query("""
        SELECT id_ihm,
               COALESCE(nu_meta_turno, 0) AS nu_meta_turno,
               COALESCE(nu_meta_ativo, 0) AS nu_meta_ativo
        FROM dbo.tb_ihm WHERE id_linha_producao = :lid
    """, {"lid": linha_id})
    curr_state = {
        int(r["id_ihm"]): (int(r["nu_meta_turno"]), int(r["nu_meta_ativo"]))
        for _, r in df_curr.iterrows()
    }

    # Carrega todas as máquinas da linha com producao_teorica, agrupadas por tipo
    df_linha = run_query("""
        SELECT i.id_ihm, COALESCE(i.tx_tipo_maquina, '') AS tx_tipo_maquina,
               COALESCE(c.nu_producao_teorica, 0) AS nu_producao_teorica
        FROM dbo.tb_ihm i
        LEFT JOIN dbo.tb_config_producao_teorica c ON c.id_ihm = i.id_ihm
        WHERE i.id_linha_producao = :lid
    """, {"lid": linha_id})
    maquinas_por_tipo: dict = {}
    linha_iids_set: set = set()  # IDs de máquinas que pertencem a esta linha
    for _, m in df_linha.iterrows():
        iid_m = int(m["id_ihm"])
        linha_iids_set.add(iid_m)
        t = m["tx_tipo_maquina"]
        if t:
            maquinas_por_tipo.setdefault(t, []).append({
                "id_ihm": iid_m,
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

        # Rejeições por etapa: reduz meta das máquinas downstream
        rej_by_stage: dict = {}
        try:
            df_rej = run_query("""
                SELECT nu_etapa_erro, COUNT(*) AS cnt
                FROM dbo.tb_op_peca_producao
                WHERE id_ordem = :id AND nu_etapa_erro IS NOT NULL
                GROUP BY nu_etapa_erro
            """, {"id": op_id})
            for _, r in df_rej.iterrows():
                rej_by_stage[int(r["nu_etapa_erro"])] = int(r["cnt"])
        except Exception:
            pass

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
            stage_num = 0
            for step in rota:
                tipo = step["tipo_maquina"]

                if tipo and tipo in seen_tipos:
                    continue

                stage_num += 1
                # Meta efetiva para esta etapa: desconta peças reprovadas em etapas anteriores
                rejected_upstream = sum(v for s, v in rej_by_stage.items() if s < stage_num)
                eff_meta = max(0, meta_op - rejected_upstream)

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

                    # Largest Remainder Method: garante que soma == eff_meta
                    raw_vals = [(iid, eff_meta * pct / 100, cap) for iid, pct, cap in machines_data]
                    floors   = [(iid, math.floor(val), val - math.floor(val), cap)
                                for iid, val, cap in raw_vals]
                    remainder = eff_meta - sum(f[1] for f in floors)
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
                    # Máquina sem tipo definido ou sem paralelas — usa direto da rota,
                    # mas só atribui se a máquina pertence a esta linha.
                    iid = step["id_ihm"]
                    if iid in linha_iids_set:
                        cap_maquina = int(step.get("producao_teorica", 0) * horas)
                        caps[iid]   = cap_maquina
                        contrib     = min(eff_meta, cap_maquina)
                        metas[iid]      = metas.get(iid, 0) + contrib
                        pecas_nome[iid] = pn
        else:
            # Sem roteiro configurado: distribui meta_op em todas as máquinas da linha
            for _, m in df_linha.iterrows():
                iid = int(m["id_ihm"])
                metas[iid]      = metas.get(iid, 0) + meta_op
                pecas_nome[iid] = pn

        # Fallback: roteiro configurado mas nenhuma máquina desta linha foi mapeada
        # (roteiro pertence a outra linha e não há tipo_maquina em comum).
        # Distribui meta_op proporcionalmente pela producao_teorica de cada máquina.
        linha_metas_ativas = {iid for iid in metas if iid in linha_iids_set}
        if peca_id and not linha_metas_ativas:
            total_pt = sum(int(m["nu_producao_teorica"]) for _, m in df_linha.iterrows())
            for _, m in df_linha.iterrows():
                iid = int(m["id_ihm"])
                pt  = int(m["nu_producao_teorica"])
                frac = (pt / total_pt) if total_pt > 0 else (1.0 / max(len(df_linha), 1))
                metas[iid]      = metas.get(iid, 0) + round(meta_op * frac)
                pecas_nome[iid] = pn

    # Garante que a soma de múltiplas OPs não ultrapassa a capacidade da máquina
    for iid in metas:
        if iid in caps:
            metas[iid] = min(metas[iid], caps[iid])

    all_iids = {int(m["id_ihm"]) for _, m in df_linha.iterrows()}

    # Aplica metas com fórmula de acumulação por turno:
    # nu_meta_turno acumula contribuições de todas as OPs do turno;
    # nu_meta_ativo é a contribuição da OP ativa atual.
    # Formula: new_turno = curr_turno + new_ativo - prev_ativo
    for iid, new_ativo in metas.items():
        curr_turno, prev_ativo = curr_state.get(iid, (0, 0))
        new_turno = max(0, curr_turno + new_ativo - prev_ativo)
        try:
            run_query_update("""
                UPDATE dbo.tb_ihm SET nu_meta_turno = :turno, nu_meta_ativo = :ativo WHERE id_ihm = :id
            """, {"turno": new_turno, "ativo": new_ativo, "id": iid})
        except Exception:
            pass
        try:
            update_machine_config(iid, new_turno, pecas_nome.get(iid, ""))
        except Exception:
            pass

    # Máquinas sem contribuição ativa: preserva nu_meta_turno, apenas zera nu_meta_ativo
    for iid in all_iids - set(metas.keys()):
        try:
            run_query_update("""
                UPDATE dbo.tb_ihm SET nu_meta_ativo = 0 WHERE id_ihm = :id
            """, {"id": iid})
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
    Marca _meta_dirty para forçar recalc imediato no próximo tick do background.

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
            _get_producao_refugo_op(linha_id, dt_inicio, peca_id, op_id=ordem_id)
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

    _mark_meta_dirty()
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
    # Prioriza em_andamento; aceita agendado dentro da janela como fallback
    df_turno = run_query("""
        SELECT TOP 1 dt_inicio, dt_fim, dt_real_inicio, tx_status
        FROM dbo.tb_turno_ocorrencia
        WHERE id_linha_producao = :lid
          AND tx_status IN ('em_andamento', 'agendado')
          AND (tx_status = 'em_andamento' OR (dt_inicio <= :agora AND dt_fim >= :agora))
        ORDER BY
          CASE WHEN tx_status = 'em_andamento' THEN 0 ELSE 1 END,
          dt_inicio
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

    row      = df_turno.iloc[0]
    dt_inicio_t = row["dt_inicio"]
    dt_fim_t    = row["dt_fim"]
    duracao     = dt_fim_t - dt_inicio_t
    # Usa tempo real se turno já foi iniciado pelo gerente
    real_inicio = row.get("dt_real_inicio") if "dt_real_inicio" in row.index else None
    if real_inicio is not None and row.get("tx_status") == "em_andamento":
        dt_fim_turno = real_inicio + duracao
    else:
        dt_fim_turno = dt_fim_t
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
    """Conta peças aprovadas nas máquinas terminais da linha desde dt_inicio.
    Usa o delta do registrador 'produzido' (aprovadas) apenas das IHMs terminais
    do roteiro, evitando a multiplicação de contagem em linhas multi-etapa."""
    # Máquinas terminais do roteiro
    df_term_l = run_query("""
        SELECT DISTINCT r.id_ihm
        FROM dbo.tb_peca_rota r
        JOIN dbo.tb_peca p ON p.id_peca = r.id_peca
        WHERE p.id_linha_producao = :lid
          AND r.nu_ordem = (
              SELECT MAX(r2.nu_ordem) FROM dbo.tb_peca_rota r2 WHERE r2.id_peca = r.id_peca
          )
    """, {"lid": linha_id})
    if df_term_l.empty:
        df_term_l = run_query(
            "SELECT id_ihm FROM dbo.tb_ihm WHERE id_linha_producao = :lid",
            {"lid": linha_id}
        )
    if df_term_l.empty:
        return 0
    total = 0
    for _, m in df_term_l.iterrows():
        df = run_query("""
            SELECT MIN(lr.nu_valor_bruto) AS val_inicio,
                   MAX(lr.nu_valor_bruto) AS val_fim
            FROM dbo.tb_log_registrador lr
            JOIN dbo.tb_registrador r ON r.id_registrador = lr.id_registrador
            WHERE lr.id_ihm      = :id
              AND r.tx_descricao = 'produzido'
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


def _get_producao_refugo_op(linha_id: int, dt_inicio: datetime, peca_id: int = None, op_id: int = None) -> dict:
    """Retorna {produzido, refugo} para uma OP.

    Quando op_id é fornecido e a OP possui rastreamento por peça em
    tb_op_peca_producao, usa essa tabela diretamente — fonte de verdade
    por OP que evita cross-contaminação entre OPs paralelas.

    Fallback (sem rastreamento por peça): delta de contador de máquina
    desde dt_inicio, filtrado pelas IHMs terminais do roteiro.
    """
    # Fonte primária: contagem por peça amarrada à OP
    if op_id is not None:
        df_rt = run_query("""
            SELECT
                SUM(CASE WHEN nu_etapa_atual > nu_etapas_total AND nu_etapa_erro IS NULL
                         THEN 1 ELSE 0 END) AS conformes,
                SUM(CASE WHEN nu_etapa_erro IS NOT NULL THEN 1 ELSE 0 END) AS refugo,
                COUNT(*) AS total
            FROM dbo.tb_op_peca_producao
            WHERE id_ordem = :op_id
        """, {"op_id": op_id})
        if not df_rt.empty and not pd.isna(df_rt.iloc[0]["total"]) and int(df_rt.iloc[0]["total"]) > 0:
            return {
                "produzido": int(df_rt.iloc[0]["conformes"]) if not pd.isna(df_rt.iloc[0]["conformes"]) else 0,
                "refugo":    int(df_rt.iloc[0]["refugo"])    if not pd.isna(df_rt.iloc[0]["refugo"])    else 0,
            }

    # Fallback: delta de contador de máquina (sem rastreamento por peça)
    terminal_ihms: list = []
    if peca_id:
        terminal_ihms = _get_terminal_ihms(peca_id)

    if not terminal_ihms:
        df_maquinas = run_query(
            "SELECT id_ihm FROM dbo.tb_ihm WHERE id_linha_producao = :lid",
            {"lid": linha_id}
        )
        if df_maquinas.empty:
            return {"produzido": 0, "refugo": 0}
        terminal_ihms = [int(r["id_ihm"]) for _, r in df_maquinas.iterrows()]

    ids_placeholder = ",".join(str(i) for i in terminal_ihms)
    df = run_query(f"""
        SELECT
            lr.id_ihm,
            r.tx_descricao,
            MAX(CASE WHEN lr.dt_created_at <  :dt THEN lr.nu_valor_bruto ELSE NULL END) AS v_base,
            MAX(CASE WHEN lr.dt_created_at >= :dt THEN lr.nu_valor_bruto ELSE NULL END) AS v_curr,
            MIN(CASE WHEN lr.dt_created_at >= :dt THEN lr.nu_valor_bruto ELSE NULL END) AS v_first
        FROM dbo.tb_log_registrador lr
        JOIN dbo.tb_registrador r ON r.id_registrador = lr.id_registrador
        WHERE lr.id_ihm IN ({ids_placeholder})
          AND r.tx_descricao IN ('produzido', 'reprovado')
        GROUP BY lr.id_ihm, r.tx_descricao
    """, {"dt": dt_inicio})

    conformes = 0
    refugo    = 0
    for _, row in df.iterrows():
        if row["v_curr"] is None:
            continue
        v_curr   = float(row["v_curr"])
        v_base   = float(row["v_base"])  if row["v_base"]  is not None else None
        v_first  = float(row["v_first"]) if row["v_first"] is not None else None
        baseline = v_base if v_base is not None else v_first
        if baseline is None:
            continue
        delta = v_curr - baseline
        if delta <= 0:
            continue
        if row["tx_descricao"] == "produzido":
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
    """Retorna horas restantes no turno ativo.
    Para turnos em_andamento usa dt_real_inicio + duração teórica como referência de fim.
    Para turnos agendados ainda não iniciados usa dt_fim diretamente.
    """
    agora = datetime.now()
    df = run_query("""
        SELECT TOP 1 dt_inicio, dt_fim, dt_real_inicio, tx_status
        FROM dbo.tb_turno_ocorrencia
        WHERE id_linha_producao = :lid
          AND tx_status IN ('em_andamento', 'agendado')
          AND (tx_status = 'em_andamento' OR (dt_inicio <= :agora AND dt_fim >= :agora))
        ORDER BY
          CASE WHEN tx_status = 'em_andamento' THEN 0 ELSE 1 END,
          dt_inicio
    """, {"lid": linha_id, "agora": agora})
    if df.empty:
        return 0.0
    row = df.iloc[0]
    dt_inicio = row["dt_inicio"]
    dt_fim    = row["dt_fim"]
    duracao   = dt_fim - dt_inicio
    if row["tx_status"] == "em_andamento" and row["dt_real_inicio"] is not None:
        expected_end = row["dt_real_inicio"] + duracao
    else:
        expected_end = dt_fim
    return max(0.0, (expected_end - agora).total_seconds() / 3600)


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

    Otimizações de performance:
    - `_ensure_ocorrencias_futuras` por linha: no máximo 1x a cada 5 min
    - Part 3 (recalc de metas): a cada 10s OU imediatamente após mudança de OP
    - `get_lines_df()`: cacheado por 30s
    """
    global _meta_dirty, _last_meta_recalc_ts, _ocorrencias_ts

    _ensure_schema()
    agora    = datetime.now()
    agora_mt = _time.monotonic()

    # === Parte 1: Gerencia ocorrências de turno ===

    # Garante ocorrências futuras para todas as linhas
    # (no máximo 1x a cada _OCORRENCIAS_INTERVAL por linha)
    try:
        df_linhas = get_lines_df()
        for _, linha in df_linhas.iterrows():
            lid = int(linha["id_linha_producao"])
            last = _ocorrencias_ts.get(lid, 0.0)
            if agora_mt - last >= _OCORRENCIAS_INTERVAL:
                _ensure_ocorrencias_futuras(lid)
                _ocorrencias_ts[lid] = agora_mt
    except Exception:
        pass

    # Turnos NÃO são abertos nem fechados automaticamente.
    # O gerente controla manualmente via POST /api/config/turnos/{id}/iniciar e /finalizar.
    # Apenas turnos agendados que já expiraram sem nunca terem sido iniciados
    # são marcados como "finalizado" (turno perdido).
    try:
        run_query_update("""
            UPDATE dbo.tb_turno_ocorrencia
            SET tx_status = 'finalizado', nu_produzido = 0
            WHERE tx_status = 'agendado' AND dt_fim < :agora
        """, {"agora": agora})
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
                producao = _get_producao_refugo_op(int(op["id_linha_producao"]), dt_ini, peca_id, op_id=int(op["id_ordem"])) if dt_ini is not None else {"produzido": 0, "refugo": 0}
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
                producao = _get_producao_refugo_op(int(op["id_linha_producao"]), dt_ini, peca_id, op_id=int(op["id_ordem"]))
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
                producao = _get_producao_refugo_op(int(op["id_linha_producao"]), dt_ini, peca_id, op_id=int(op["id_ordem"]))
                _finalizar_op_automatico(int(op["id_ordem"]), producao["produzido"], producao["refugo"])
            except Exception:
                pass
    except Exception:
        pass

    # === Parte 3: Recalcula metas para linhas com OPs ativas ===
    # Executa imediatamente se _meta_dirty (mudança recente de OP) OU
    # se já passaram _META_RECALC_INTERVAL segundos desde o último recalc.
    deve_recalc = _meta_dirty or (agora_mt - _last_meta_recalc_ts >= _META_RECALC_INTERVAL)
    if deve_recalc:
        _meta_dirty = False
        _last_meta_recalc_ts = agora_mt
    # Aplica redução de meta por rejeições upstream em tempo real.
    if deve_recalc:
        try:
            df_linhas_ativas = run_query("""
                SELECT DISTINCT id_linha_producao
                FROM dbo.tb_ordem_producao
                WHERE tx_status = 'em_producao'
            """, {})
            for _, row in df_linhas_ativas.iterrows():
                try:
                    _recalcular_metas_linha(int(row["id_linha_producao"]))
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


# ─── Sistema de Alertas ────────────────────────────────────────────────────────

_alertas_schema_ensured = False
_last_alert_detection:  float = 0.0
_ALERT_DETECTION_INTERVAL = 10.0

_DEFAULTS_ALERTA = [
    {"tx_tipo": "maquina_parada",        "tx_nome": "Máquina parada",          "nu_limiar": 15,  "tx_severidade": "critico", "tx_descricao": "Alerta quando uma máquina ficar parada por mais de N minutos."},
    {"tx_tipo": "manutencao_prolongada", "tx_nome": "Manutenção prolongada",   "nu_limiar": 60,  "tx_severidade": "critico", "tx_descricao": "Alerta quando uma máquina estiver em manutenção por mais de N minutos."},
    {"tx_tipo": "oee_baixo",             "tx_nome": "OEE abaixo do limiar",    "nu_limiar": 60,  "tx_severidade": "aviso",   "tx_descricao": "Alerta quando o OEE de uma máquina em produção cair abaixo de N%."},
    {"tx_tipo": "refugo_alto",           "tx_nome": "Taxa de refugo elevada",  "nu_limiar": 15,  "tx_severidade": "aviso",   "tx_descricao": "Alerta quando a taxa de refugo ultrapassar N% (mínimo 10 peças)."},
    {"tx_tipo": "op_atrasada",           "tx_nome": "OP com atraso",           "nu_limiar": 60,  "tx_severidade": "aviso",   "tx_descricao": "Alerta quando uma OP estiver em produção por mais de N min com menos de 50% concluída."},
]


def _ensure_alertas_schema():
    global _alertas_schema_ensured
    if _alertas_schema_ensured:
        return
    run_query_update("""
        IF NOT EXISTS (SELECT * FROM sys.objects
                       WHERE object_id = OBJECT_ID(N'dbo.tb_alerta_config') AND type = 'U')
        BEGIN
            CREATE TABLE dbo.tb_alerta_config (
                id_config         INT IDENTITY(1,1) PRIMARY KEY,
                tx_tipo           VARCHAR(50)    NOT NULL,
                tx_nome           NVARCHAR(120)  NOT NULL,
                tx_descricao      NVARCHAR(500)  NULL,
                nu_limiar         DECIMAL(10,2)  NOT NULL DEFAULT 15,
                tx_severidade     VARCHAR(20)    NOT NULL DEFAULT 'aviso',
                id_linha_producao INT            NULL,
                fl_ativo          BIT            NOT NULL DEFAULT 1,
                dt_criacao        DATETIME       DEFAULT GETDATE()
            )
        END
    """)
    run_query_update("""
        IF NOT EXISTS (SELECT * FROM sys.objects
                       WHERE object_id = OBJECT_ID(N'dbo.tb_alerta') AND type = 'U')
        BEGIN
            CREATE TABLE dbo.tb_alerta (
                id_alerta            INT IDENTITY(1,1) PRIMARY KEY,
                id_config            INT             NULL,
                tx_tipo              VARCHAR(50)     NOT NULL,
                tx_severidade        VARCHAR(20)     NOT NULL DEFAULT 'aviso',
                tx_titulo            NVARCHAR(255)   NOT NULL,
                tx_descricao         NVARCHAR(1000)  NULL,
                id_linha_producao    INT             NULL,
                id_ihm               INT             NULL,
                id_ordem             INT             NULL,
                nu_valor             DECIMAL(10,2)   NULL,
                nu_limiar            DECIMAL(10,2)   NULL,
                tx_status            VARCHAR(20)     NOT NULL DEFAULT 'ativo',
                tx_reconhecido_por   NVARCHAR(120)   NULL,
                dt_reconhecido       DATETIME        NULL,
                tx_resolucao         NVARCHAR(500)   NULL,
                dt_criacao           DATETIME        DEFAULT GETDATE(),
                dt_resolucao         DATETIME        NULL
            )
        END
    """)
    df_count = run_query("SELECT COUNT(*) AS n FROM dbo.tb_alerta_config", {})
    if not df_count.empty and int(df_count.iloc[0]["n"]) == 0:
        for d in _DEFAULTS_ALERTA:
            run_query_update("""
                INSERT INTO dbo.tb_alerta_config
                    (tx_tipo, tx_nome, tx_descricao, nu_limiar, tx_severidade, fl_ativo)
                VALUES (:tipo, :nome, :desc, :limiar, :sev, 1)
            """, {"tipo": d["tx_tipo"], "nome": d["tx_nome"], "desc": d["tx_descricao"],
                  "limiar": d["nu_limiar"], "sev": d["tx_severidade"]})
    _alertas_schema_ensured = True


def _criar_alerta_interno(tipo, severidade, titulo, descricao,
                          id_ihm=None, id_linha=None, id_ordem=None,
                          nu_valor=None, nu_limiar=None, id_config=None):
    try:
        run_query_update("""
            INSERT INTO dbo.tb_alerta
                (id_config, tx_tipo, tx_severidade, tx_titulo, tx_descricao,
                 id_linha_producao, id_ihm, id_ordem, nu_valor, nu_limiar, tx_status)
            VALUES
                (:cfg, :tipo, :sev, :titulo, :desc,
                 :id_linha, :id_ihm, :id_ordem, :valor, :limiar, 'ativo')
        """, {"cfg": id_config, "tipo": tipo, "sev": severidade,
              "titulo": titulo, "desc": descricao,
              "id_linha": id_linha, "id_ihm": id_ihm, "id_ordem": id_ordem,
              "valor": nu_valor, "limiar": nu_limiar})
    except Exception:
        pass


def _resolver_alerta_interno(id_alerta: int,
                             resolucao: str = "Condição normalizada automaticamente."):
    try:
        run_query_update("""
            UPDATE dbo.tb_alerta
            SET tx_status    = 'resolvido',
                tx_resolucao = :res,
                dt_resolucao = GETDATE()
            WHERE id_alerta  = :id
              AND tx_status IN ('ativo', 'reconhecido')
        """, {"res": resolucao, "id": id_alerta})
    except Exception:
        pass


def _handle_alert(condition_met, tipo, severidade, titulo, descricao,
                  id_ihm, id_linha, id_ordem, nu_valor, nu_limiar, id_config, alert_keys):
    key = (tipo, id_ihm, id_ordem)
    if condition_met:
        if key not in alert_keys:
            _criar_alerta_interno(tipo=tipo, severidade=severidade,
                                  titulo=titulo, descricao=descricao,
                                  id_ihm=id_ihm, id_linha=id_linha, id_ordem=id_ordem,
                                  nu_valor=nu_valor, nu_limiar=nu_limiar, id_config=id_config)
    else:
        if key in alert_keys:
            _resolver_alerta_interno(alert_keys[key])


def _check_op_atrasada(cfg, alert_keys):
    limiar = float(cfg["nu_limiar"])
    sev    = cfg["tx_severidade"]
    id_cfg = int(cfg["id_config"])

    df = run_query("""
        SELECT
            o.id_ordem, o.nu_numero_op, o.tx_peca, o.nu_quantidade,
            o.id_linha_producao, l.tx_name AS nome_linha,
            DATEDIFF(MINUTE, o.dt_inicio, GETDATE()) AS minutos_em_producao,
            COALESCE(rt.n_concluido, 0) AS n_concluido
        FROM dbo.tb_ordem_producao o
        JOIN dbo.tb_linha_producao l ON l.id_linha_producao = o.id_linha_producao
        LEFT JOIN (
            SELECT id_ordem,
                SUM(CASE WHEN nu_etapa_atual > nu_etapas_total
                          AND nu_etapa_erro IS NULL THEN 1 ELSE 0 END) AS n_concluido
            FROM dbo.tb_op_peca_producao
            GROUP BY id_ordem
        ) rt ON rt.id_ordem = o.id_ordem
        WHERE o.tx_status = 'em_producao'
          AND o.dt_inicio IS NOT NULL
    """, {})

    ids_em_producao = set(int(r["id_ordem"]) for _, r in df.iterrows()) if not df.empty else set()
    for (tipo, id_ihm, id_ordem), id_alerta in list(alert_keys.items()):
        if tipo != "op_atrasada" or id_ordem is None:
            continue
        if id_ordem not in ids_em_producao:
            _resolver_alerta_interno(id_alerta, "OP finalizada ou cancelada.")

    if df.empty:
        return

    for _, row in df.iterrows():
        id_ordem  = int(row["id_ordem"])
        qtd       = int(row["nu_quantidade"])
        concluido = int(row["n_concluido"])
        id_linha  = int(row["id_linha_producao"])
        minutos   = float(row["minutos_em_producao"]) if not pd.isna(row["minutos_em_producao"]) else 0
        pct       = round(concluido / qtd * 100, 1) if qtd > 0 else 0.0
        cond      = (minutos >= limiar and pct < 50.0)
        titulo    = f"OP atrasada: {row['nu_numero_op']}"
        descricao = (f"OP {row['nu_numero_op']} ({row['tx_peca']}) em produção há {minutos:.0f} min "
                     f"com {pct:.0f}% concluída ({concluido}/{qtd} peças).")
        _handle_alert(condition_met=cond, tipo="op_atrasada", severidade=sev,
                      titulo=titulo, descricao=descricao,
                      id_ihm=None, id_linha=id_linha, id_ordem=id_ordem,
                      nu_valor=pct, nu_limiar=50.0, id_config=id_cfg,
                      alert_keys=alert_keys)


def _detectar_e_criar_alertas():
    _ensure_alertas_schema()

    df_cfgs = run_query("""
        SELECT id_config, tx_tipo, nu_limiar, tx_severidade, tx_nome, id_linha_producao
        FROM dbo.tb_alerta_config WHERE fl_ativo = 1
    """, {})
    if df_cfgs.empty:
        return
    configs = df_cfgs.to_dict(orient="records")

    df_ativos = run_query("""
        SELECT id_alerta, tx_tipo, id_ihm, id_ordem
        FROM dbo.tb_alerta WHERE tx_status IN ('ativo', 'reconhecido')
    """, {})
    alert_keys: dict = {}
    for _, row in df_ativos.iterrows():
        ihm  = int(row["id_ihm"])   if row["id_ihm"]   is not None and not pd.isna(row["id_ihm"])   else None
        ord_ = int(row["id_ordem"]) if row["id_ordem"] is not None and not pd.isna(row["id_ordem"]) else None
        alert_keys[(row["tx_tipo"], ihm, ord_)] = int(row["id_alerta"])

    df_m = run_query("""
        WITH ms AS (
            SELECT
                m.id_ihm, m.tx_name AS nome, m.id_linha_producao,
                l.tx_name AS nome_linha,
                s.status_val,
                p.produzido,
                r.reprovado,
                COALESCE(m.nu_meta_turno, 0) AS meta
            FROM dbo.tb_ihm m
            JOIN dbo.tb_linha_producao l
              ON l.id_linha_producao = m.id_linha_producao
            OUTER APPLY (
                SELECT TOP 1 CAST(lr.nu_valor_bruto AS INT) AS status_val
                FROM dbo.tb_log_registrador lr
                JOIN dbo.tb_registrador reg ON reg.id_registrador = lr.id_registrador
                WHERE lr.id_ihm = m.id_ihm AND reg.tx_descricao = 'status'
                ORDER BY lr.dt_created_at DESC
            ) s
            OUTER APPLY (
                SELECT TOP 1 CAST(lr.nu_valor_bruto AS INT) AS produzido
                FROM dbo.tb_log_registrador lr
                JOIN dbo.tb_registrador reg ON reg.id_registrador = lr.id_registrador
                WHERE lr.id_ihm = m.id_ihm AND reg.tx_descricao = 'produzido'
                ORDER BY lr.dt_created_at DESC
            ) p
            OUTER APPLY (
                SELECT TOP 1 CAST(lr.nu_valor_bruto AS INT) AS reprovado
                FROM dbo.tb_log_registrador lr
                JOIN dbo.tb_registrador reg ON reg.id_registrador = lr.id_registrador
                WHERE lr.id_ihm = m.id_ihm AND reg.tx_descricao = 'reprovado'
                ORDER BY lr.dt_created_at DESC
            ) r
            WHERE s.status_val IS NOT NULL
        )
        SELECT ms.*, dur.minutos_no_status
        FROM ms
        OUTER APPLY (
            SELECT TOP 1
                DATEDIFF(MINUTE, lr.dt_created_at, GETDATE()) AS minutos_no_status
            FROM dbo.tb_log_registrador lr
            JOIN dbo.tb_registrador reg ON reg.id_registrador = lr.id_registrador
            WHERE lr.id_ihm          = ms.id_ihm
              AND reg.tx_descricao   = 'status'
              AND CAST(lr.nu_valor_bruto AS INT) <> ms.status_val
            ORDER BY lr.dt_created_at DESC
        ) dur
    """, {})

    oee_map: dict = {}
    try:
        ov = get_overview_data()
        for linha in ov.get("linhas", []):
            for m in linha.get("maquinas", []):
                oee_map[m["id"]] = m.get("oee") or 0
    except Exception:
        pass

    for _, m_row in df_m.iterrows():
        id_ihm     = int(m_row["id_ihm"])
        id_linha   = int(m_row["id_linha_producao"])
        nome       = m_row["nome"]
        nome_linha = m_row["nome_linha"]
        status     = int(m_row["status_val"])
        produzido  = int(m_row["produzido"])  if m_row["produzido"]  is not None and not pd.isna(m_row["produzido"])  else 0
        reprovado  = int(m_row["reprovado"])  if m_row["reprovado"]  is not None and not pd.isna(m_row["reprovado"])  else 0
        minutos    = float(m_row["minutos_no_status"]) if m_row["minutos_no_status"] is not None and not pd.isna(m_row["minutos_no_status"]) else 999
        oee        = oee_map.get(id_ihm, 0) or 0
        total_pcs  = produzido + reprovado

        for cfg in configs:
            if cfg["id_linha_producao"] is not None and not pd.isna(cfg["id_linha_producao"]):
                if int(cfg["id_linha_producao"]) != id_linha:
                    continue
            tipo   = cfg["tx_tipo"]
            limiar = float(cfg["nu_limiar"])
            sev    = cfg["tx_severidade"]
            id_cfg = int(cfg["id_config"])

            if tipo == "maquina_parada":
                cond      = (status == 0 and minutos >= limiar)
                titulo    = f"Máquina parada: {nome}"
                descricao = f"{nome} ({nome_linha}) está parada há {minutos:.0f} min (limiar: {limiar:.0f} min)."
                valor     = minutos
            elif tipo == "manutencao_prolongada":
                cond      = (status in (51, 52) and minutos >= limiar)
                titulo    = f"Manutenção prolongada: {nome}"
                descricao = f"{nome} ({nome_linha}) em manutenção há {minutos:.0f} min (limiar: {limiar:.0f} min)."
                valor     = minutos
            elif tipo == "oee_baixo":
                cond      = (status == 49 and oee > 0 and oee < limiar)
                titulo    = f"OEE baixo: {nome}"
                descricao = f"{nome} ({nome_linha}) com OEE de {oee:.1f}% abaixo do limiar de {limiar:.0f}%."
                valor     = oee
            elif tipo == "refugo_alto":
                taxa      = round(reprovado / total_pcs * 100, 1) if total_pcs >= 10 else 0
                cond      = (total_pcs >= 10 and taxa > limiar)
                titulo    = f"Refugo alto: {nome}"
                descricao = f"{nome} ({nome_linha}) com {taxa:.1f}% de refugo ({reprovado}/{total_pcs} peças). Limiar: {limiar:.0f}%."
                valor     = taxa
            else:
                continue

            _handle_alert(condition_met=cond, tipo=tipo, severidade=sev,
                          titulo=titulo, descricao=descricao,
                          id_ihm=id_ihm, id_linha=id_linha, id_ordem=None,
                          nu_valor=valor, nu_limiar=limiar, id_config=id_cfg,
                          alert_keys=alert_keys)

    for cfg in configs:
        if cfg["tx_tipo"] == "op_atrasada":
            _check_op_atrasada(cfg, alert_keys)


def detectar_alertas_throttled():
    global _last_alert_detection
    now = _time.monotonic()
    if now - _last_alert_detection < _ALERT_DETECTION_INTERVAL:
        return
    _last_alert_detection = now
    try:
        _detectar_e_criar_alertas()
    except Exception:
        pass


def get_alertas(status: str = None, severidade: str = None, linha_id: int = None,
                tipo: str = None, limite: int = 200) -> list:
    _ensure_alertas_schema()
    where  = ["1=1"]
    params: dict = {"lim": limite}
    if status:
        where.append("a.tx_status = :status");     params["status"]  = status
    if severidade:
        where.append("a.tx_severidade = :sev");    params["sev"]     = severidade
    if linha_id:
        where.append("a.id_linha_producao = :lid"); params["lid"]    = linha_id
    if tipo:
        where.append("a.tx_tipo = :tipo");          params["tipo"]   = tipo

    df = run_query(f"""
        SELECT TOP (:lim)
            a.id_alerta, a.tx_tipo, a.tx_severidade, a.tx_titulo, a.tx_descricao,
            a.id_linha_producao, l.tx_name  AS nome_linha,
            a.id_ihm,            m.tx_name  AS nome_maquina,
            a.id_ordem,          o.nu_numero_op,
            a.nu_valor, a.nu_limiar,
            a.tx_status, a.tx_reconhecido_por, a.dt_reconhecido,
            a.tx_resolucao, a.dt_criacao, a.dt_resolucao
        FROM dbo.tb_alerta a
        LEFT JOIN dbo.tb_linha_producao  l ON l.id_linha_producao = a.id_linha_producao
        LEFT JOIN dbo.tb_ihm             m ON m.id_ihm             = a.id_ihm
        LEFT JOIN dbo.tb_ordem_producao  o ON o.id_ordem           = a.id_ordem
        WHERE {' AND '.join(where)}
        ORDER BY
            CASE a.tx_status WHEN 'ativo' THEN 0 WHEN 'reconhecido' THEN 1 ELSE 2 END,
            CASE a.tx_severidade WHEN 'critico' THEN 0 WHEN 'aviso' THEN 1 ELSE 2 END,
            a.dt_criacao DESC
    """, params)

    result = []
    for _, r in df.iterrows():
        def _int(v):   return int(v)        if v is not None and not pd.isna(v) else None
        def _float(v): return float(v)      if v is not None and not pd.isna(v) else None
        def _dt(v):    return v.isoformat() if v is not None                    else None
        result.append({
            "id":              int(r["id_alerta"]),
            "tipo":            r["tx_tipo"],
            "severidade":      r["tx_severidade"],
            "titulo":          r["tx_titulo"],
            "descricao":       r["tx_descricao"],
            "id_linha":        _int(r["id_linha_producao"]),
            "nome_linha":      r["nome_linha"],
            "id_ihm":          _int(r["id_ihm"]),
            "nome_maquina":    r["nome_maquina"],
            "id_ordem":        _int(r["id_ordem"]),
            "numero_op":       r["nu_numero_op"],
            "nu_valor":        _float(r["nu_valor"]),
            "nu_limiar":       _float(r["nu_limiar"]),
            "status":          r["tx_status"],
            "reconhecido_por": r["tx_reconhecido_por"],
            "dt_reconhecido":  _dt(r["dt_reconhecido"]),
            "resolucao":       r["tx_resolucao"],
            "dt_criacao":      _dt(r["dt_criacao"]),
            "dt_resolucao":    _dt(r["dt_resolucao"]),
        })
    return result


def get_alertas_stats() -> dict:
    _ensure_alertas_schema()
    df = run_query("""
        SELECT
            SUM(CASE WHEN tx_status IN ('ativo','reconhecido')                             THEN 1 ELSE 0 END) AS total_ativos,
            SUM(CASE WHEN tx_status = 'ativo'                                              THEN 1 ELSE 0 END) AS nao_reconhecidos,
            SUM(CASE WHEN tx_status = 'reconhecido'                                        THEN 1 ELSE 0 END) AS reconhecidos,
            SUM(CASE WHEN tx_status IN ('ativo','reconhecido') AND tx_severidade='critico' THEN 1 ELSE 0 END) AS criticos,
            SUM(CASE WHEN CAST(dt_criacao AS DATE) = CAST(GETDATE() AS DATE)               THEN 1 ELSE 0 END) AS hoje,
            SUM(CASE WHEN dt_criacao >= DATEADD(DAY,-7,GETDATE())                          THEN 1 ELSE 0 END) AS semana
        FROM dbo.tb_alerta
    """, {})
    if df.empty:
        return {"total_ativos": 0, "nao_reconhecidos": 0, "reconhecidos": 0,
                "criticos": 0, "hoje": 0, "semana": 0}
    r = df.iloc[0]
    def _i(v): return int(v) if v is not None and not pd.isna(v) else 0
    return {"total_ativos": _i(r["total_ativos"]), "nao_reconhecidos": _i(r["nao_reconhecidos"]),
            "reconhecidos":  _i(r["reconhecidos"]),  "criticos": _i(r["criticos"]),
            "hoje":          _i(r["hoje"]),           "semana":   _i(r["semana"])}


def reconhecer_alerta(id_alerta: int, reconhecido_por: str = "Operador") -> None:
    _ensure_alertas_schema()
    run_query_update("""
        UPDATE dbo.tb_alerta
        SET tx_status = 'reconhecido', tx_reconhecido_por = :por, dt_reconhecido = GETDATE()
        WHERE id_alerta = :id AND tx_status = 'ativo'
    """, {"por": reconhecido_por, "id": id_alerta})


def resolver_alerta(id_alerta: int, resolucao: str = None) -> None:
    _ensure_alertas_schema()
    run_query_update("""
        UPDATE dbo.tb_alerta
        SET tx_status    = 'resolvido',
            tx_resolucao = :res,
            dt_resolucao = GETDATE()
        WHERE id_alerta = :id AND tx_status IN ('ativo', 'reconhecido')
    """, {"res": resolucao, "id": id_alerta})


def get_alertas_config() -> list:
    _ensure_alertas_schema()
    df = run_query("""
        SELECT c.id_config, c.tx_tipo, c.tx_nome, c.tx_descricao, c.nu_limiar,
               c.tx_severidade, c.id_linha_producao, l.tx_name AS nome_linha, c.fl_ativo
        FROM dbo.tb_alerta_config c
        LEFT JOIN dbo.tb_linha_producao l ON l.id_linha_producao = c.id_linha_producao
        ORDER BY c.id_config
    """, {})
    result = []
    for _, r in df.iterrows():
        result.append({
            "id":         int(r["id_config"]),
            "tipo":       r["tx_tipo"],
            "nome":       r["tx_nome"],
            "descricao":  r["tx_descricao"],
            "limiar":     float(r["nu_limiar"]),
            "severidade": r["tx_severidade"],
            "id_linha":   int(r["id_linha_producao"]) if r["id_linha_producao"] is not None and not pd.isna(r["id_linha_producao"]) else None,
            "nome_linha": r["nome_linha"],
            "ativo":      bool(r["fl_ativo"]),
        })
    return result


def save_alerta_config(data: dict) -> int:
    _ensure_alertas_schema()
    id_cfg = data.get("id")
    p = {
        "tipo":     data["tipo"],
        "nome":     data["nome"],
        "desc":     data.get("descricao", ""),
        "limiar":   data["limiar"],
        "sev":      data["severidade"],
        "id_linha": data.get("id_linha"),
        "ativo":    1 if data.get("ativo", True) else 0,
    }
    if id_cfg:
        run_query_update("""
            UPDATE dbo.tb_alerta_config
            SET tx_tipo=:tipo, tx_nome=:nome, tx_descricao=:desc,
                nu_limiar=:limiar, tx_severidade=:sev,
                id_linha_producao=:id_linha, fl_ativo=:ativo
            WHERE id_config=:id
        """, {**p, "id": id_cfg})
        return int(id_cfg)
    return int(run_query_insert("""
        INSERT INTO dbo.tb_alerta_config
            (tx_tipo, tx_nome, tx_descricao, nu_limiar, tx_severidade, id_linha_producao, fl_ativo)
        OUTPUT INSERTED.id_config
        VALUES (:tipo, :nome, :desc, :limiar, :sev, :id_linha, :ativo)
    """, p))


def delete_alerta_config(id_config: int) -> None:
    _ensure_alertas_schema()
    run_query_update("DELETE FROM dbo.tb_alerta_config WHERE id_config=:id", {"id": id_config})


def toggle_alerta_config(id_config: int, ativo: bool) -> None:
    _ensure_alertas_schema()
    run_query_update("UPDATE dbo.tb_alerta_config SET fl_ativo=:a WHERE id_config=:id",
                     {"a": 1 if ativo else 0, "id": id_config})
