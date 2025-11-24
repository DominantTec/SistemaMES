from src.monitoramento.logger import logger
from src.monitoramento.database import get_connection_db
from src.monitoramento.ihm_client import get_connection_ihm
from src.monitoramento.data_processor import read_registers
from src.monitoramento.data_processor import insert_registers_values
import datetime
import time
from dotenv import load_dotenv
import os


def main():
    conn_ihm = None
    conn_db = None

    try:
        if load_dotenv():
            logger.info("Variáveis carregadas com sucesso! (main)")
        else:
            logger.error("Variáveis não carregadas! (main)")
        ids_ihm = str(os.environ['IHMS']).split(',')
        # id_ihm = ids_ihm[0]
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

        erros_maximo = 10
        erros = 0
        while erros <= erros_maximo:
            for k, id_ihm in enumerate(ids_ihm):
                try:
                    logger.info(
                        f"========================================== {id_ihm} ==========================================")

                    # hora_atual = datetime.datetime.now()
                    # if hora_atual.hour == 4 and hora_atual.minute >= 5:
                    #     logger.info(
                    #         "Horário limite alcançado, interrompendo o loop")
                    #     break

                    values, insert_values = read_registers(
                        id_ihm, conn_ihm[k], conn_db)

                    insert_registers_values(conn_db, values, insert_values)

                    time.sleep(0.1)
                except ConnectionError as ce:
                    while True:
                        erros += 1
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
