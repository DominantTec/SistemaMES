import pyodbc
from logger import logger
import os


def get_connection_db(driver=None, server=None, database=None):
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

        conn = pyodbc.connect(connection_string)
        logger.info("Conexão com o banco bem-sucedida!")
        return conn
    except Exception as e:
        logger.error("Erro ao conectar ao banco de dados: %s", e)
        return None
