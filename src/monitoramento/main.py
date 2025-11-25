from logger import logger
from database import get_connection_db
from ihm_client import get_connection_ihm
from data_processor import read_registers
from data_processor import insert_registers_values
import time
import os


def main():
    conn_ihm = None
    conn_db = None

    try:
        ids_ihm = str(os.environ['IHMS']).split(',')
        conn_db = get_connection_db()
        conn_ihm = []
        for id_ihm in ids_ihm:
            connection = get_connection_ihm(id_ihm, conn_db)

            while connection is None:
                logger.info(
                    "Falha ao conectar com a IHM. Tentando novamente...")
                time.sleep(10)
                connection = get_connection_ihm(id_ihm, conn_db)

            conn_ihm.append(connection)

        while True:
            for k, id_ihm in enumerate(ids_ihm):
                try:
                    logger.info(
                        f"========================================== {id_ihm} ==========================================")

                    values, insert_values = read_registers(
                        id_ihm, conn_ihm[k], conn_db)

                    insert_registers_values(conn_db, values, insert_values)

                    time.sleep(0.1)
                except ConnectionError as ce:
                    while True:
                        logger.info(f"{ce}")
                        logger.info(
                            "Tentando reestabelecer conexão com a IHM...")
                        conn_ihm[k] = get_connection_ihm(id_ihm, conn_db)

                        if conn_ihm[k] is None:
                            logger.info(
                                "Falha ao tentar reestabelecer a conexão")
                            time.sleep(10)
                        else:
                            logger.info("Conexão reestabelecida com sucesso")
                            break

                except Exception as e:
                    raise e

    except Exception as e:
        logger.info(f"EXECUÇÃO IMTERROMPIDA: Erro na função principal: {e}")
    finally:
        if conn_db:
            conn_db.close()
        for conn in conn_ihm:
            if conn:
                conn.close()


if __name__ == "__main__":
    main()
