from src.logger import logger

# Função para ler os registradores e montar a string de insert no banco de dados
def read_registers(id_ihm, conn_ihm, conn_db):
    try:
        insert_values = ""
        values = []
        cursor = conn_db.cursor()
        select_registers = f"SELECT id, endereco, descricao FROM registradores WHERE id_ihm = {id_ihm} ORDER BY id ASC"
        cursor.execute(select_registers)
        registers = cursor.fetchall()

        #logger.info("------------------------------REGISTERS VALUE------------------------------")
        for register in registers:
            try:
                valor_registrador = conn_ihm.read_holding_registers(address=register.endereco, count=1).registers[0]
                insert_values += f"(@BatchID, {id_ihm}, {register.id}, {valor_registrador}),"
                values.append(valor_registrador)

                logger.info(f"{register.endereco}   |   {valor_registrador}   |   {register.descricao}")
            except Exception as e:
                if "[WinError 10054]" in str(e):
                    logger.info(f"Conexão com a IHM perdida: {e}")
                    raise ConnectionError("Conexão perdida com a IHM, identificado pelo erro [WinError 10054]")
                
                insert_values += f"(@BatchID, {id_ihm}, {register.id}, NULL),"
                values.append('None')
                logger.info(f"Erro ao ler o registrador no endereço {register['endereco']}: {e}")

        insert_values = insert_values[:-1]

        return values, insert_values
    except ConnectionError as ce:
        raise ce
    except Exception as e:
        logger.info(f"falha ao capturar os dados da IHM: ", e)


# Função para inserir os dados no banco de dados
def insert_registers_values(conn_db, values, insert_values):
    if conn_db:
        try:
            cursor = conn_db.cursor()

            # Verificar se a tabela está vazia
            query_count = f"SELECT COUNT(*) FROM [IHM_Testes_2].[dbo].[logs_registradores]"
            cursor.execute(query_count)
            count = cursor.fetchone()

            # Se a tabela estiver vazia, não há nada para comparar
            if count[0] == 0:
                logger.info("A tabela [IHM_Testes_2].[dbo].[logs_registradores] está vazia. Inserindo novo registro...")
                
                insert_log_string = f"""
                                    DECLARE @BatchID BIGINT;

                                    -- Obtém o próximo valor da SEQUENCE
                                    SET @BatchID = NEXT VALUE FOR LogBatchSequence;

                                    -- Exemplo de inserção de dados nos logs
                                    INSERT INTO Logs_Registradores (batch_id, id_ihm, id_registrador, valor_bruto)
                                    VALUES
                                    {insert_values}"""
                
                cursor.execute(insert_log_string)
                conn_db.commit()
                
                logger.info("Dados inseridos com sucesso!")
                return

            select_batch_id = f"""SELECT TOP 1 batch_id FROM [IHM_Testes_2].[dbo].[logs_registradores]
                                ORDER BY batch_id DESC"""
            cursor.execute(select_batch_id)
            batch_id = cursor.fetchone()

            select_last_values = f"""SELECT [valor_bruto] FROM [IHM_Testes_2].[dbo].[logs_registradores]
                                    WHERE batch_id = {batch_id[0]}
                                    ORDER BY id ASC"""
            cursor.execute(select_last_values)
            last_values = [int(row[0]) for row in cursor.fetchall()]

            if values == last_values:
                logger.info("Nenhuma alteração detectada. Registro não inserido.")
                return
            else:
                logger.info("Alteração detectada. Inserindo novo registro...")

                insert_log_string = f"""
                                    DECLARE @BatchID BIGINT;

                                    -- Obtém o próximo valor da SEQUENCE
                                    SET @BatchID = NEXT VALUE FOR LogBatchSequence;

                                    -- Exemplo de inserção de dados nos logs
                                    INSERT INTO Logs_Registradores (batch_id, id_ihm, id_registrador, valor_bruto)
                                    VALUES
                                    {insert_values}"""
                
                cursor.execute(insert_log_string)
                conn_db.commit()

                logger.info("Dados inseridos com sucesso!")

        except Exception as e:
            logger.info(f"Erro ao executar a operação:", e)
    else:
        raise ConnectionError("Conexão com o banco inválida passada por parametro na função insert_registers_values.")