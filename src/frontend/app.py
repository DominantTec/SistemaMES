import streamlit as st
from services.db import run_query

st.title("🔌 Teste de Conexão com o Banco MES")

st.write("Tentando conectar ao banco...")

try:
    tabelas = run_query("SELECT name FROM sys.tables;")

    st.success("Conexão bem-sucedida! 🎉")
    st.write("Tabelas encontradas:")
    st.table(tabelas)

except Exception as e:
    st.error("❌ Erro ao conectar")
    st.code(str(e))