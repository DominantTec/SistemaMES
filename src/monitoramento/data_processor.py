from logger import logger

# Função para ler os registradores e montar a string de insert no banco de dados


def read_registers(id_ihm, conn_ihm, conn_db):
    try:
        insert_values = ""
        values = []
        cursor = conn_db.cursor()
        select_registers = f"SELECT id_registrador, nu_endereco, tx_descricao FROM tb_registrador WHERE id_ihm = {id_ihm} ORDER BY id_registrador ASC"
        cursor.execute(select_registers)
        registers = cursor.fetchall()

        # logger.info("------------------------------REGISTERS VALUE------------------------------")
        for register in registers:
            try:
                valor_registrador = conn_ihm.read_holding_registers(
                    address=register.nu_endereco,
                    count=1
                ).registers[0]

                insert_values += f"({id_ihm}, {register.id_registrador}, {valor_registrador}),"
                values.append(valor_registrador)

                logger.info(
                    f"{register.nu_endereco}   |   {valor_registrador}   |   {register.tx_descricao}")

            except Exception as e:
                # Perda de conexão Modbus (erro 10054)
                if "[WinError 10054]" in str(e):
                    logger.error(f"Conexão com a IHM perdida: {e}")
                    raise ConnectionError(
                        "Conexão perdida com a IHM, identificado pelo erro [WinError 10054]")

                insert_values += f"({id_ihm}, {register.id_registrador}, NULL),"
                values.append(None)
                logger.error(
                    f"Erro ao ler o registrador no endereço {register.nu_endereco}: {e}")

        insert_values = insert_values[:-1]  # remove última vírgula
        return values, insert_values

    except ConnectionError as ce:
        raise ce
    except Exception as e:
        logger.info(f"Falha ao capturar os dados da IHM: {e}")


# Função para inserir os dados no banco de dados
def insert_registers_values(id_ihm, conn_db, values, insert_values):
    if not conn_db:
        raise ConnectionError(
            "Conexão com o banco inválida passada por parâmetro na função insert_registers_values.")

    try:
        cursor = conn_db.cursor()

        # Verificar se a tabela está vazia
        query_count = f"SELECT COUNT(*) FROM [MES_Core].[dbo].[tb_log_registrador] WHERE id_ihm = {id_ihm}"
        cursor.execute(query_count)
        count = cursor.fetchone()

        # Tabela vazia → inserir primeiro registro sem comparação
        if count[0] == 0:
            logger.info(
                "A tabela tb_log_registrador está vazia. Inserindo novo registro...")

            insert_log_string = f"""
                INSERT INTO tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto)
                VALUES
                {insert_values}
            """

            cursor.execute(insert_log_string)
            conn_db.commit()
            logger.info("Dados inseridos com sucesso!")
            return

        # Buscar último registro registrado
        select_last_time = f"""
            SELECT TOP 1 dt_created_at
            FROM [MES_Core].[dbo].[tb_log_registrador]
            WHERE id_ihm = {id_ihm}
            ORDER BY dt_created_at DESC
        """
        cursor.execute(select_last_time)
        last_time = cursor.fetchone()

        # Carregar últimos valores para comparação
        select_last_values = f"""
            SELECT nu_valor_bruto
            FROM [MES_Core].[dbo].[tb_log_registrador]
            WHERE dt_created_at = '{last_time[0]}'
            ORDER BY id_log_registrador ASC
        """
        cursor.execute(select_last_values)
        last_values = [int(row[0]) for row in cursor.fetchall()]

        # Se valores iguais → não insere
        if values == last_values:
            logger.info("Nenhuma alteração detectada. Registro não inserido.")
            return

        # Caso contrário → inserir novo registro
        logger.info("Alteração detectada. Inserindo novo registro...")

        insert_log_string = f"""
            INSERT INTO tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto)
            VALUES
            {insert_values}
        """

        cursor.execute(insert_log_string)
        conn_db.commit()
        logger.info("Dados inseridos com sucesso!")

    except Exception as e:
        logger.info(f"Erro ao executar a operação: {e}")