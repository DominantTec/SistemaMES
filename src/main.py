from src.logger import logger
from src.config import load_config, get_args
from src.database import get_connection_db
from src.ihm_client import get_connection_ihm
from src.data_processor import read_registers
from src.data_processor import insert_registers_values
import datetime
import time

def main():
    conn_ihm = None
    conn_db = None

    try:

        args = get_args()
        config = load_config(args.config_path)
        id_ihm = config['ihm']['id']
        conn_db = get_connection_db(config['banco']['conn_driver'], config['banco']['conn_server'], config['banco']['conn_database'])
        conn_ihm = get_connection_ihm(id_ihm, conn_db)

        while conn_ihm is None:
            logger.info("Falha ao conectar com a IHM. Tentando novamente...")
            time.sleep(10)
            conn_ihm = get_connection_ihm(id_ihm, conn_db)

        while True:
            try:
                logger.info("=====================================================================================")

                hora_atual = datetime.datetime.now()
                if hora_atual.hour == 00 and hora_atual.minute >= 5:
                    logger.info("Horário limite alcançado, interrompendo o loop")
                    break

                values, insert_values = read_registers(id_ihm, conn_ihm, conn_db)

                insert_registers_values(conn_db, values, insert_values)

                time.sleep(0.1)
            except ConnectionError as ce:
                while True:
                    logger.info(f"{ce}")
                    logger.info("Tentando reestabelecer conexão com a IHM...")
                    conn_ihm = get_connection_ihm(id_ihm, conn_db)

                    if conn_ihm is None:
                        logger.info("Falha ao tentar reestabelecer a conexão")
                        time.sleep(10)
                    else:
                        logger.info("Conexão reestabelecida com sucesso")
                        break

                    # if conn_ihm == None:
                    #     logger.info("Falha ao tentar reestabelecer a conexão")
                    #     time.sleep(10)
                    # else:
                    #     if str(conn_ihm) == f"ModbusTcpClient {ip_ihm}:{port_ihm}":
                    #         logger.info("conexão reestabelecida com sucesso")
                    #         break
                    #     else:
                    #         logger.info("Falha ao tentar reestabelecer a conexão")
                    #         time.sleep(10)
            except Exception as e:
                raise e


    except Exception as e:
        logger.info(f"EXECUÇÃO IMTERROMPIDA: Erro na função principal: {e}")
    finally:
        if conn_db:
            conn_db.close()
        if conn_ihm:
            conn_ihm.close()

if __name__ == "__main__":
    main()