from pymodbus.client import ModbusTcpClient
from logger import logger


def get_connection_ihm(id_ihm, conn_db):
    try:
        cursor = conn_db.cursor()
        select_ihms = f"SELECT tx_ip_address, tx_port_number FROM tb_ihm WHERE id_ihm = {id_ihm}"
        cursor.execute(select_ihms)
        result = cursor.fetchone()

        if result is None:  # Verifica se o SELECT retornou algo
            logger.info(f"Nenhuma IHM encontrada com ID {id_ihm}.")
            return None

        ip, port = result

        client = ModbusTcpClient(f"{ip}", port=port)
        if client.connect():
            logger.info(f"Conexão com a ihm {id_ihm} bem-sucedida!")
            return client
        else:
            logger.info(f"Falha ao conectar com a IHM {ip}:{port}")
            return None

    except Exception as e:
        logger.error("Erro ao conectar ao IHM: %s", e)
        return None
