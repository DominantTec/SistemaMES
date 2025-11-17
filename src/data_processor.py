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

        # logger.info("------------------------------REGISTERS VALUE------------------------------")
        for register in registers:
            try:
                valor_registrador = conn_ihm.read_holding_registers(
                    address=register.endereco,
                    count=1
                ).registers[0]

                insert_values += f"(@BatchID, {id_ihm}, {register.id}, {valor_registrador}),"
                values.append(valor_registrador)

                logger.info(f"{register.endereco}   |   {valor_registrador}   |   {register.descricao}")

            except Exception as e:
                # Perda de conexão Modbus (erro 10054)
                if "[WinError 10054]" in str(e):
                    logger.info(f"Conexão com a IHM perdida: {e}")
                    raise ConnectionError("Conexão perdida com a IHM, identificado pelo erro [WinError 10054]")

                insert_values += f"(@BatchID, {id_ihm}, {register.id}, NULL),"
                values.append(None)
                logger.info(f"Erro ao ler o registrador no endereço {register.endereco}: {e}")

        insert_values = insert_values[:-1]  # remove última vírgula
        return values, insert_values

    except ConnectionError as ce:
        raise ce
    except Exception as e:
        logger.info(f"Falha ao capturar os dados da IHM: {e}")


# Função para inserir os dados no banco de dados
def insert_registers_values(conn_db, values, insert_values):
    if not conn_db:
        raise ConnectionError("Conexão com o banco inválida passada por parâmetro na função insert_registers_values.")

    try:
        cursor = conn_db.cursor()

        # Verificar se a tabela está vazia
        query_count = "SELECT COUNT(*) FROM [IHM_Testes_2].[dbo].[logs_registradores]"
        cursor.execute(query_count)
        count = cursor.fetchone()

        # Tabela vazia → inserir primeiro registro sem comparação
        if count[0] == 0:
            logger.info("A tabela logs_registradores está vazia. Inserindo novo registro...")

            insert_log_string = f"""
                DECLARE @BatchID BIGINT;

                SET @BatchID = NEXT VALUE FOR LogBatchSequence;

                INSERT INTO fila_batch_ids (batch_id, status)
                VALUES (@BatchID, 0);

                INSERT INTO Logs_Registradores (batch_id, id_ihm, id_registrador, valor_bruto)
                VALUES
                {insert_values};
            """

            cursor.execute(insert_log_string)
            conn_db.commit()
            logger.info("Dados inseridos com sucesso!")
            return

        # Buscar último batch_id registrado
        select_batch_id = """
            SELECT TOP 1 batch_id
            FROM [IHM_Testes_2].[dbo].[logs_registradores]
            ORDER BY batch_id DESC
        """
        cursor.execute(select_batch_id)
        batch_id = cursor.fetchone()

        # Carregar últimos valores para comparação
        select_last_values = f"""
            SELECT valor_bruto
            FROM [IHM_Testes_2].[dbo].[logs_registradores]
            WHERE batch_id = {batch_id[0]}
            ORDER BY id ASC
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

            INSERT INTO fila_batch_ids (batch_id, status)
            VALUES (@BatchID, 0);

            INSERT INTO fila_paradas (batch_id, status)
            VALUES (@BatchID, 0);

            INSERT INTO Logs_Registradores (batch_id, id_ihm, id_registrador, valor_bruto)
            VALUES
            {insert_values};
        """

        cursor.execute(insert_log_string)
        conn_db.commit()
        logger.info("Dados inseridos com sucesso!")

    except Exception as e:
        logger.info(f"Erro ao executar a operação: {e}")


# ================================
# MÉTRICAS MOCKADAS (FRONTEND)
# ================================
def get_metrics_machine(df_timeline=None, machine='MAQ1', time_window=None):
    """
    Retorna métricas mockadas para a máquina selecionada.
    Será substituído pelo cálculo real no backend.
    """

    if machine == 'MAQ1':
        qualidade = 0.5
        eficiencia = 0.6
        meta = 200
        acumulado = 98
        operador = 'fulano'
        manutentor = 'siclano'
        status = 'parada'

    elif machine == 'MAQ2':
        qualidade = 0.7
        eficiencia = 0.8
        meta = 200
        acumulado = 135
        operador = 'fulano'
        manutentor = 'siclano'
        status = 'parada'

    else:
        qualidade = eficiencia = meta = acumulado = 0
        operador = manutentor = status = "desconhecido"

    return {
        "OEE": round(qualidade * eficiencia, 2),
        "qualidade": qualidade,
        "eficiencia": eficiencia,
        "meta": meta,
        "acumulado": acumulado,
        "operador": operador,
        "manutentor": manutentor,
        "status": status
    }