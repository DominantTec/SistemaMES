import os
import pyodbc
from pathlib import Path
from dotenv import load_dotenv

# === Carregar .env na raiz do projeto ===
ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(ENV_PATH)

def get_connection():
    """Retorna conexão com SQL Server usando variáveis do .env."""
    try:
        driver = "{ODBC Driver 17 for SQL Server}"
        server = f"{os.getenv('DB_HOST')},{os.getenv('DB_PORT')}"
        database = os.getenv("DB_NAME")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")

        connection_string = (
            f"DRIVER={driver};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={user};"
            f"PWD={password};"
            "TrustServerCertificate=yes;"
            "Encrypt=no;"
        )

        # Teste de conexão
        conn = pyodbc.connect(connection_string, timeout=3)
        return conn

    except Exception as e:
        raise Exception(f"Erro ao conectar ao banco: {e}\nConnection string: {connection_string}")

def run_query(sql, params=None):
    """Executa um SELECT e retorna lista de dicts."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(sql, params or [])
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    except Exception as e:
        raise Exception(f"Erro ao executar query: {e}\nSQL: {sql}")

    finally:
        cursor.close()
        conn.close()