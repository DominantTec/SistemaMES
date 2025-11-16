import streamlit as st
from services.db import run_query

st.set_page_config(page_title="Detalhes da Máquina", layout="wide")

# ============================
# Ler ID da máquina pela URL
# ============================
maq_id = st.query_params.get("maq_id", None)

if not maq_id:
    st.error("Nenhuma máquina selecionada.")
    st.stop()

maq_id = int(maq_id)

# ============================
# Buscar os dados da máquina
# ============================
info_ihm = run_query("""
    SELECT *
    FROM ihms
    WHERE id = ?
""", [maq_id])

if not info_ihm:
    st.error("Máquina não encontrada.")
    st.stop()

ihm = info_ihm[0]

# Último status geral
status_data = run_query("""
    SELECT TOP 1 *
    FROM maqteste_status_geral
    WHERE id_ihm = ?
    ORDER BY datahora DESC
""", [maq_id])

st.title(f"🖥️ Máquina: {ihm['nome_maquina']}")

st.write("### 📌 Informações Gerais")
st.write(f"- **Acumulado:** {ihm['acumulado']}")
st.write(f"- **Operador:** {ihm['operador'] or '--'}")
st.write(f"- **Manutentor:** {ihm['manutentor'] or '--'}")

if status_data:
    st.write("---")
    s = status_data[0]
    st.write("### 🟦 Último Registro")
    st.json(s)

st.write("---")
st.write("### 📊 Gráficos (em construção)")
st.info("Aqui você poderá adicionar gráficos de status, OEE, paradas, etc.")