import pyodbc
from src.logger import logger

def get_connection_db(driver, server, database):
    try:
        conn = pyodbc.connect(f'DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;')
        logger.info("Conexão com o banco bem-sucedida!")
        return conn
    except Exception as e:
        logger.info("Erro ao conectar ao banco de dados:", e)
        return None