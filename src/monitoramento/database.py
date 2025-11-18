import pyodbc
from src.monitoramento.logger import logger
from dotenv import load_dotenv
import os

if load_dotenv():
    logger.info("Variáveis carregadas com sucesso! (database)")
else:
    logger.error("Variáveis não carregadas! (database)")


def get_connection_db(driver=None, server=None, database=None):
    try:
        password = os.environ['DB_PASSWORD']
        if not driver:
            driver = os.environ['DRIVER_OUT_CONTAINER']
        if not server:
            server = os.environ['DB_SERVER_OUT_CONTAINER']
        if not database:
            database = os.environ['DB_NAME']
        connection_string = (
            f"DRIVER={driver};"
            f"SERVER={server};"
            f"DATABASE={database};"
            "UID=sa;"
            f"PWD={password};"
            "TrustServerCertificate=yes;"
            "Encrypt=no;"
        )
        conn = pyodbc.connect(connection_string)
        logger.info("Conexão com o banco bem-sucedida!")
        return conn
    except Exception as e:
        logger.info("Erro ao conectar ao banco de dados:", e)
        return None
