import os
import pandas as pd
from sqlalchemy import create_engine, text, event
from sqlalchemy.pool import QueuePool
from urllib.parse import quote_plus

# ── Engine singleton ──────────────────────────────────────────────────────────
# Criada uma única vez na inicialização. Compartilhada entre todas as queries.
# pool_size=10  — conexões mantidas abertas permanentemente
# max_overflow=20 — conexões extras permitidas em picos (além do pool_size)
# pool_timeout=30 — segundos para esperar por uma conexão livre
# pool_recycle=1800 — recicla conexões a cada 30 min (evita conexões mortas)
# pool_pre_ping=True — verifica se conexão ainda está viva antes de usar

_engine = None


def _build_engine():
    driver   = "{FreeTDS}"
    server   = os.getenv("DB_HOST")
    port     = os.getenv("DB_PORT")
    database = os.getenv("DB_NAME")
    user     = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")

    connection_string = (
        f"DRIVER={driver};"
        f"SERVER={server};"
        f"PORT={port};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
        "Encrypt=no;"
    )
    connection_url = f"mssql+pyodbc:///?odbc_connect={quote_plus(connection_string)}"

    return create_engine(
        connection_url,
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
    )


def get_engine():
    """Retorna o engine singleton, criando-o na primeira chamada."""
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


# Mantido por compatibilidade com código que chama get_connection()
def get_connection():
    return get_engine()


def run_query(sql, params=None):
    """Executa um SELECT e retorna um DataFrame."""
    try:
        engine = get_engine()
        df = pd.read_sql(text(sql), engine, params=params)
        return df
    except Exception as e:
        raise Exception(f"Erro ao executar query: {e}\nSQL: {sql}")


def run_query_update(sql, params=None):
    """
    Executa um UPDATE/DELETE/INSERT genérico (sem retorno de ID).
    Retorna a quantidade de linhas afetadas.
    """
    try:
        engine = get_engine()
        with engine.begin() as conn:
            result = conn.execute(text(sql), params or {})
            return result.rowcount
    except Exception as e:
        raise Exception(f"Erro ao executar UPDATE: {e}\nSQL: {sql}")


def run_query_insert(sql, params=None):
    """Executa INSERT com OUTPUT INSERTED e retorna o primeiro valor da linha."""
    try:
        engine = get_engine()
        with engine.begin() as conn:
            result = conn.execute(text(sql), params or {})
            row = result.fetchone()
            return row[0] if row else None
    except Exception as e:
        raise Exception(f"Erro ao executar INSERT: {e}\nSQL: {sql}")
