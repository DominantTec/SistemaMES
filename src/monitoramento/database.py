import pyodbc
from logger import logger
import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()


def get_connection_db(driver=None, server=None, database=None):
    try:
        driver = os.getenv('DB_DRIVER', '{FreeTDS}')
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

        conn = pyodbc.connect(connection_string)
        logger.info("Conexão com o banco bem-sucedida!")
        return conn
    except Exception as e:
        logger.error("Erro ao conectar ao banco de dados: %s", e)
        return None


def execute_select(query: str, params: dict | None = None, connection=None) -> pd.DataFrame:
    """
    Executa uma query SELECT com parâmetros e retorna um DataFrame.

    Args:
        query (str): Query SQL com placeholders '?'
        params (dict): Dicionário com parâmetros

    Returns:
        pd.DataFrame
    """
    try:
        cursor = connection.cursor()

        if params:
            cursor.execute(query, list(params.values()))
        else:
            cursor.execute(query)

        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()

        df = pd.DataFrame.from_records(rows, columns=columns)

        return df

    except Exception as e:
        logger.error("Erro ao executar SELECT: %s", e)
        raise


def insert_dataframe(df: pd.DataFrame, table_name: str, connection=None):
    """
    Insere dados de um DataFrame em uma tabela SQL Server.

    Args:
        df (pd.DataFrame): DataFrame com dados
        table_name (str): Nome da tabela
    """
    try:
        cursor = connection.cursor()

        columns = ", ".join(df.columns)
        placeholders = ", ".join(["?"] * len(df.columns))

        query = f"""
        INSERT INTO {table_name} ({columns})
        VALUES ({placeholders})
        """

        cursor.fast_executemany = True  # Performance boost
        cursor.executemany(query, df.values.tolist())

        connection.commit()
        logger.info(
            f"{len(df)} registros inseridos com sucesso em {table_name}")

    except Exception as e:
        if connection:
            connection.rollback()
        logger.error("Erro ao inserir dados: %s", e)
        raise
