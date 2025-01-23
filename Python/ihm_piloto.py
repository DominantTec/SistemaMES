from pymodbus.client import ModbusTcpClient
import pyodbc
import json
import datetime
import time

# Função para carregar o arquivo JSON de condiguração
def carregar_configuracao(arquivo):
    with open(arquivo, 'r') as file:
        config = json.load(file)
    return config

# Função para conectar ao banco de dados
def get_connection_db(driver, server, database):
    try:
        conn = pyodbc.connect(f'DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;')
        datetime_log_str = datetime.datetime.now().isoformat()
        print(f"{datetime_log_str} | Conexão com o banco bem-sucedida!")
        return conn
    except Exception as e:
        datetime_log_str = datetime.datetime.now().isoformat()
        print(f"{datetime_log_str} | Erro ao conectar ao banco de dados:", e)
        return None
    
# Função para conectar a IHM
def get_connection_ihm(ip, porta):
    try:
        client = ModbusTcpClient(f"{ip}", port=porta)
        if client.connect():
            datetime_log_str = datetime.datetime.now().isoformat()
            print(f"{datetime_log_str} | Conexão com a ihm bem-sucedida!")
            return client
        else:
            datetime_log_str = datetime.datetime.now().isoformat()
            print(f"{datetime_log_str} | Falha ao conectar à IHM.")
            return None
    except Exception as e:
        datetime_log_str = datetime.datetime.now().isoformat()
        print(f"{datetime_log_str} | Erro ao conectar ao IHM:", e)
        return None
    
# Função para ler os registradores e montar a string de insert no banco de dados
def read_registers(config, conn_ihm):
    try:
        registradores = config['registradores']
        colunas = ""
        valores = ""

        for registrador in registradores:
            colunas += f"{registrador['coluna_banco']}, "

            try:
                resultado = conn_ihm.read_holding_registers(address=registrador['endereco'], count=1)
                if not resultado.isError():
                    valor_registrador = resultado.registers[0]
                    valores += f"{str(valor_registrador)}, "
                else:
                    valores += "NULL, "
            except Exception as e:
                valores += "NULL, "
                datetime_log_str = datetime.datetime.now().isoformat()
                print(f"{datetime_log_str} | Erro ao ler o registrador no endereço {registrador['endereco']}: {e}")

        colunas = colunas[:-2]
        valores = valores[:-2]

        datetime_log_str = datetime.datetime.now().isoformat()
        print(f"{datetime_log_str} | dados capturados da IHM com sucesso")
        return colunas, valores
    except Exception as e:
        datetime_log_str = datetime.datetime.now().isoformat()
        print(f"{datetime_log_str} | falha ao capturar os dados da IHM: ", e)

# Função para inserir os dados dos registradores no banco
def insert_registers_values(conn_db, tabela, colunas, valores):
    if conn_db:
        try:
            cursor = conn_db.cursor()
            
            # Verificar se a tabela está vazia
            query_count = f"SELECT COUNT(*) FROM {tabela}"
            cursor.execute(query_count)
            count = cursor.fetchone()

            # Se a tabela estiver vazia, não há nada para comparar
            if count[0] == 0:
                datetime_log_str = datetime.datetime.now().isoformat()
                print(f"{datetime_log_str} | A tabela {tabela} está vazia. Inserindo novo registro...")
                
                insert_string = f"INSERT INTO {tabela} ({colunas}) VALUES ({valores})"
                cursor.execute(insert_string)
                conn_db.commit()  # Salva a transação
                
                datetime_log_str = datetime.datetime.now().isoformat()
                print(f"{datetime_log_str} | Dados inseridos com sucesso!")
                return

            # Executar SELECT para obter os últimos valores
            query = f"SELECT TOP 1 {colunas} FROM {tabela} ORDER BY Id DESC"
            cursor.execute(query)
            row = cursor.fetchone()

            # Converter os valores do SELECT em uma string formatada
            if row:
                valores_atuais = ', '.join(map(str, row))

                datetime_log_str = datetime.datetime.now().isoformat()
                print(f"{datetime_log_str} | Valores atuais no banco: {valores_atuais}")
                print(f"{datetime_log_str} | Valores obtidos da IHM: {valores}")

                # Comparar com os valores desejados
                if valores_atuais == valores:
                    datetime_log_str = datetime.datetime.now().isoformat()
                    print(f"{datetime_log_str} | Nenhuma alteração detectada. Registro não inserido.")
                    return
                else:
                    datetime_log_str = datetime.datetime.now().isoformat()
                    print(f"{datetime_log_str} | Alteração detectada. Inserindo novo registro...")

                    # Realizar o INSERT
                    insert_string = f"INSERT INTO {tabela} ({colunas}) VALUES ({valores})"
                    cursor.execute(insert_string)
                    conn_db.commit()  # Salva a transação

                    datetime_log_str = datetime.datetime.now().isoformat()
                    print(f"{datetime_log_str} | Dados inseridos com sucesso!")
        except Exception as e:
            datetime_log_str = datetime.datetime.now().isoformat()
            print(f"{datetime_log_str} | Erro ao executar a operação:", e)


def main():
    conn_db = None
    conn_ihm = None

    try:
        config = carregar_configuracao('../Json/ihm_piloto.json')

        conn_db = get_connection_db(config['banco']['conn_driver'], config['banco']['conn_server'], config['banco']['conn_database'])
        conn_ihm = get_connection_ihm(f"{config['ihm']['ip']}", config['ihm']['port'])

        while True:
            print("=====================================================================================")

            hora_atual = datetime.datetime.now()
            if hora_atual.hour == 13 and hora_atual.minute >= 5:
                datetime_log_str = datetime.datetime.now().isoformat()
                print(f"{datetime_log_str} | Horário limite alcançado, interrompendo o loop")
                break

            colunas, valores = read_registers(config, conn_ihm)

            insert_registers_values(conn_db, config['ihm']['tabela'], colunas, valores)

            time.sleep(0.2)
    except Exception as e:
        print(f"Erro na função principal: {e}")
    finally:
        if conn_db:
            conn_db.close()
        if conn_ihm:
            conn_ihm.close()

main()