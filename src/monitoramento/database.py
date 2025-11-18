import pyodbc
from src.monitoramento.logger import logger
from dotenv import load_dotenv
import os

if load_dotenv():
    logger.info("Variáveis carregadas com sucesso!")
else:
    logger.error("Variáveis não carregadas!")


def get_connection_db(driver, server, database):
    # try:
    password = os.environ['MSSQL_SA_PASSWORD']
    connection_string = (
        f"DRIVER={driver};"
        f"SERVER={server};"
        f"DATABASE={database};"
        "UID=sa;"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
        "Encrypt=no;"
    )
    print(connection_string)
    conn = pyodbc.connect(connection_string)
    logger.info("Conexão com o banco bem-sucedida!")
    return conn
    # except Exception as e:
    #     logger.info("Erro ao conectar ao banco de dados:", e)
    #     return None
