import struct

from logger import logger

_schema_checked = False


def _ensure_registrador_schema(conn_db):
    """Garante a coluna nu_qtd_words em tb_registrador (1=WORD 16bit, 2=REAL 32bit). Idempotente."""
    global _schema_checked
    if _schema_checked:
        return
    try:
        cursor = conn_db.cursor()
        cursor.execute("""
            IF NOT EXISTS (
                SELECT * FROM sys.columns
                WHERE object_id = OBJECT_ID('dbo.tb_registrador') AND name = 'nu_qtd_words'
            )
                ALTER TABLE dbo.tb_registrador ADD nu_qtd_words INT NOT NULL DEFAULT 1
        """)
        conn_db.commit()
        _schema_checked = True
    except Exception as e:
        logger.warning(f"Falha ao garantir coluna nu_qtd_words: {e}")


def sync_meta_to_ihm(id_ihm, conn_ihm, conn_db):
    """Compara a meta configurada no banco com a que está na IHM.
    Se forem diferentes, escreve o valor do banco na IHM via Modbus."""
    try:
        cursor = conn_db.cursor()

        # Endereço Modbus do registrador de meta
        cursor.execute(f"""
            SELECT nu_endereco FROM tb_registrador
            WHERE id_ihm = {id_ihm} AND tx_descricao = 'meta'
        """)
        row = cursor.fetchone()
        if not row:
            return
        endereco_meta = int(row[0])

        # Último valor de meta definido pelo usuário no banco (ignora zeros da IHM)
        cursor.execute(f"""
            SELECT TOP 1 nu_valor_bruto
            FROM tb_log_registrador
            WHERE id_registrador = (
                SELECT id_registrador FROM tb_registrador
                WHERE id_ihm = {id_ihm} AND tx_descricao = 'meta'
            )
            AND nu_valor_bruto > 0
            ORDER BY dt_created_at DESC
        """)
        row_meta = cursor.fetchone()
        if not row_meta:
            return
        meta_db = int(row_meta[0])

        # Meta atual na IHM
        meta_ihm = conn_ihm.read_holding_registers(address=endereco_meta, count=1).registers[0]

        if meta_db != meta_ihm:
            conn_ihm.write_registers(address=endereco_meta, values=[meta_db])
            logger.info(f"IHM {id_ihm}: meta sincronizada na IHM ({meta_ihm} → {meta_db})")

    except Exception as e:
        logger.warning(f"IHM {id_ihm}: falha ao sincronizar meta: {e}")


# Função para ler os registradores e montar a string de insert no banco de dados


def read_registers(id_ihm, conn_ihm, conn_db):
    try:
        _ensure_registrador_schema(conn_db)
        insert_values = ""
        values = []
        cursor = conn_db.cursor()
        select_registers = f"SELECT id_registrador, nu_endereco, tx_descricao, nu_qtd_words FROM tb_registrador WHERE id_ihm = {id_ihm} ORDER BY id_registrador ASC"
        cursor.execute(select_registers)
        registers = cursor.fetchall()

        # logger.info("------------------------------REGISTERS VALUE------------------------------")
        for register in registers:
            try:
                qtd_words = int(register.nu_qtd_words or 1)
                regs = conn_ihm.read_holding_registers(
                    address=register.nu_endereco,
                    count=qtd_words
                ).registers

                if qtd_words == 2:
                    # REAL (float 32 bits) = 2 registradores, word baixa primeiro (Delta/DVP)
                    valor_registrador = round(
                        struct.unpack("<f", struct.pack("<HH", regs[0], regs[1]))[0], 4)
                else:
                    valor_registrador = regs[0]

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
        last_values = [float(row[0]) for row in cursor.fetchall()]

        # Se valores iguais → não insere (compara como float por causa dos registradores REAL)
        if [None if v is None else float(v) for v in values] == last_values:
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