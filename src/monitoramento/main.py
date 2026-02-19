from logger import logger
from database import get_connection_db, execute_select, insert_dataframe
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

            # Consulta se é necessário atualização via FTP
            update_needed = execute_select('SELECT bl_needed FROM tb_ftp_needed WHERE id_ihm = ?',
                                           {'id_ihm': id_ihm},
                                           conn_db)['bl_needed'].to_list()[0]

            # Caso necessário, baixa arquivo via FTP
            if update_needed:
                logger.info(
                    f'IHM {id_ihm} precisa de atualização do bd via FTP.')
                logger.info('Atualização via FTP ainda em construção.')

                # Le arquivo FTP
                # logger.info('Buscando arquivo via FTP.')
                # logger.info('Fazendo o download do arquivo via FTP.')
                # logger.info('Lendo as bases do CSV.')

                # Inclui informações na base de dados
                # logger.info('Atualizando as informações do banco de dados.')

                # Faz marcação de FTP feito
                logger.info('Marcando atualização FTP como feita.')
            else:
                logger.info(
                    f'IHM {id_ihm} não precisa de atualização do bd via FTP.')

        while True:
            for k, id_ihm in enumerate(ids_ihm):
                try:
                    logger.info(
                        f"========================================== {id_ihm} ==========================================")

                    values, insert_values = read_registers(
                        id_ihm, conn_ihm[k], conn_db)

                    insert_registers_values(
                        id_ihm, conn_db, values, insert_values)

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
