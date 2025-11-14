import pyodbc
import os
from dotenv import load_dotenv

load_dotenv("../../.env")   # ajustado só pra teste rápido

server = "localhost,1433"
database = "IHM_Testes_2"
user = "sa"
password = os.getenv("MSSQL_SA_PASSWORD")

print("Senha usada:", password)

try:
    conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost,1433;"
    "DATABASE=IHM_Testes_2;"
    "UID=sa;"
    "PWD=Domin4nt2025@;"
    "Encrypt=no;"
    "TrustServerCertificate=yes;"
)

    print("Conectou!")
except Exception as e:
    print("Erro:", e)