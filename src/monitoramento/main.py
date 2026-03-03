from logger import logger
from database import get_connection_db, execute_select, insert_dataframe
from ftp_services import connect_ftp, list_files, download_file, read_ftp_file
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
                try:
                    logger.info(
                        f'IHM {id_ihm} precisa de atualização do bd via FTP.')
                    logger.info('Atualização via FTP ainda em construção.')

                    host_ftp = execute_select('SELECT tx_ip_address FROM tb_ihm WHERE id_ihm = ?',
                                              {'id_ihm': id_ihm},
                                              conn_db)['tx_ip_address'].to_list()[0]

                    logger.info('Buscando arquivo via FTP.')
                    ftp_connection = connect_ftp(
                        host_ftp, os.environ['FTP_USER'], os.environ['FTP_PASSWORD'])

                    logger.info('Listando os arquivos via FTP.')
                    temp_file = 'apoio.csv'
                    ftp_files = list_files(ftp_connection, '/')

                    logger.info('Fazendo o download do arquivo via FTP.')
                    for file in ftp_files:
                        if file.endswith('.csv'):
                            download_file(ftp_connection, '/', file, temp_file)
                            break

                    logger.info('Lendo as bases do CSV.')
                    tables_dict = read_ftp_file(temp_file)

                    depara_tables = {
                        'Matriculas': ('tb_depara_operador', {'Codigo': 'nu_cod_operador', 'Nome': 'tx_operador'})
                    }

                    for key in tables_dict:
                        if key == 'Matriculas':
                            logger.info(
                                f'Atualizando as informações de {depara_tables[key][0]} do banco de dados.')
                            insert_dataframe(tables_dict[key][['Codigo', 'Nome']].rename(
                                columns=depara_tables[key][1]), depara_tables[key][0], conn_db)

                    logger.info('Deletando arquivo utilizado.')
                    os.remove(temp_file)

                    # Faz marcação de FTP feito
                    logger.info('Marcando atualização FTP como feita.')
                except Exception as e:
                    logger.error('Erro ao executar a atualização FTP.')
                    raise e
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
