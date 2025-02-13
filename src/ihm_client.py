from pymodbus.client import ModbusTcpClient
from src.logger import logger

def get_connection_ihm(ip, porta):
    try:
        client = ModbusTcpClient(f"{ip}", port=porta)
        if client.connect():
            logger.info("Conexão com a ihm bem-sucedida!")
            return client
        else:
            logger.info("Falha ao conectar à IHM.")
            return None
    except Exception as e:
        logger.info("Erro ao conectar ao IHM:", e)
        return None