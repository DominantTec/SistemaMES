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
# Buscar os dados fixos da máquina (tabela IHMS)
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


# ============================
# Buscar o último registro operacional (tabela maqteste_status_geral)
# ============================
status_data = run_query("""
    SELECT TOP 1 *
    FROM maqteste_status_geral
    WHERE id_ihm = ?
    ORDER BY datahora DESC
""", [maq_id])

ultimo = status_data[0] if status_data else None


# ============================
# TÍTULO
# ============================
st.title(f"🖥️ Máquina: {ihm['nome_maquina']}")


# ============================
# 📌 Informações Operacionais Recentes
# ============================
st.write("### 📌 Informações Recentes (maqteste_status_geral)")

if ultimo:
    st.write(f"- **Status:** {ultimo['status_maquina']}")
    st.write(f"- **Acumulado:** {ultimo['total_produzido']}")
    st.write(f"- **Operador:** {ultimo['operador'] or '--'}")
    st.write(f"- **Manutentor:** {ultimo['manutentor'] or '--'}")
    st.write(f"- **Meta:** {ultimo['meta']}")
    st.write(f"- **OEE:** {ultimo['oee']} %")
    st.write(f"- **Eficiência:** {ultimo['eficiencia']} %")
    st.write(f"- **Qualidade:** {ultimo['qualidade']} %")
else:
    st.warning("Nenhum registro encontrado em 'maqteste_status_geral'.")


# ============================
# 📌 Informações Fixas da Máquina (da tabela IHMS)
# ============================
st.write("---")
st.write("### 🧩 Dados Fixos da Máquina (ihms)")

st.write(f"- **IP:** {ihm['ip_address']}")
st.write(f"- **Porta:** {ihm['port_number']}")
st.write(f"- **Linha de Produção:** {ihm['id_linha_producao']}")


# ============================
# Área futura para gráficos
# ============================
st.write("---")
st.write("### 📊 Gráficos (em construção)")
st.info("Aqui você poderá adicionar gráficos de status, OEE, paradas, etc.")