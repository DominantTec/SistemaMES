import os
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus


def get_connection():
    """Retorna conexão com SQL Server usando variáveis do .env."""
    try:
        driver = "{FreeTDS}"
        server = os.getenv('DB_HOST')
        port = os.getenv('DB_PORT')
        database = os.getenv("DB_NAME")
        user = os.getenv("DB_USER")
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

        engine = create_engine(connection_url)

        return engine

    except Exception as e:
        raise Exception(
            f"Erro ao conectar ao banco: {e}\nConnection string: {connection_string}")


def run_query(sql, params=None):
    """Executa um SELECT e retorna um dataframe."""
    try:
        engine = get_connection()
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
        engine = get_connection()
        with engine.begin() as conn:
            result = conn.execute(text(sql), params or {})
            return result.rowcount
    except Exception as e:
        raise Exception(f"Erro ao executar UPDATE: {e}\nSQL: {sql}")
