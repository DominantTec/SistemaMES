from logger import logger

# Função para ler os registradores e montar a string de insert no banco de dados


def read_registers(id_ihm, conn_ihm, conn_db):
    try:
        insert_values = ""
        values = []
        cursor = conn_db.cursor()
        select_registers = f"SELECT id_registrador, endereco, descricao FROM tb_registradores WHERE id_ihm = {id_ihm} ORDER BY id_registrador ASC"
        cursor.execute(select_registers)
        registers = cursor.fetchall()

        # logger.info("------------------------------REGISTERS VALUE------------------------------")
        for register in registers:
            try:
                valor_registrador = conn_ihm.read_holding_registers(
                    address=register.endereco,
                    count=1
                ).registers[0]

                insert_values += f"(@BatchID, {id_ihm}, {register.id_registrador}, {valor_registrador}),"
                values.append(valor_registrador)

                logger.info(
                    f"{register.endereco}   |   {valor_registrador}   |   {register.descricao}")

            except Exception as e:
                # Perda de conexão Modbus (erro 10054)
                if "[WinError 10054]" in str(e):
                    logger.error(f"Conexão com a IHM perdida: {e}")
                    raise ConnectionError(
                        "Conexão perdida com a IHM, identificado pelo erro [WinError 10054]")

                insert_values += f"(@BatchID, {id_ihm}, {register.id_registrador}, NULL),"
                values.append(None)
                logger.error(
                    f"Erro ao ler o registrador no endereço {register.endereco}: {e}")

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
        query_count = f"SELECT COUNT(*) FROM [MES_Core].[dbo].[tb_logs_registradores] WHERE id_ihm = {id_ihm}"
        cursor.execute(query_count)
        count = cursor.fetchone()

        # Tabela vazia → inserir primeiro registro sem comparação
        if count[0] == 0:
            logger.info(
                "A tabela logs_registradores está vazia. Inserindo novo registro...")

            insert_log_string = f"""
                DECLARE @BatchID BIGINT;

                SET @BatchID = NEXT VALUE FOR LogBatchSequence;

                INSERT INTO tb_fila_batch_ids (batch_id, status)
                VALUES (@BatchID, 0);

                INSERT INTO tb_logs_registradores (batch_id, id_ihm, id_registrador, valor_bruto)
                VALUES
                {insert_values};
            """

            cursor.execute(insert_log_string)
            conn_db.commit()
            logger.info("Dados inseridos com sucesso!")
            return

        # Buscar último batch_id registrado
        select_batch_id = f"""
            SELECT TOP 1 batch_id
            FROM [MES_Core].[dbo].[tb_logs_registradores]
            WHERE id_ihm = {id_ihm}
            ORDER BY batch_id DESC
        """
        cursor.execute(select_batch_id)
        batch_id = cursor.fetchone()

        # Carregar últimos valores para comparação
        select_last_values = f"""
            SELECT valor_bruto
            FROM [MES_Core].[dbo].[tb_logs_registradores]
            WHERE batch_id = {batch_id[0]}
            ORDER BY id_log_registradores ASC
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
            DECLARE @BatchID BIGINT;

            SET @BatchID = NEXT VALUE FOR LogBatchSequence;

            INSERT INTO tb_fila_batch_ids (batch_id, status)
            VALUES (@BatchID, 0);

            INSERT INTO tb_fila_paradas (batch_id, status)
            VALUES (@BatchID, 0);

            INSERT INTO tb_logs_registradores (batch_id, id_ihm, id_registrador, valor_bruto)
            VALUES
            {insert_values};
        """

        cursor.execute(insert_log_string)
        conn_db.commit()
        logger.info("Dados inseridos com sucesso!")

    except Exception as e:
        logger.info(f"Erro ao executar a operação: {e}")
