import streamlit as st
from services.db import run_query
from urllib.parse import urlencode

st.set_page_config(page_title="Visão Geral MES", layout="wide")

st.title("🏭 Visão Geral da Produção")

# Paleta de cores dos status
STATUS_COLORS = {
    "máquina produzindo": "#96d779",
    "máquina em manutenção": "#f7c76c",
    "máquina sem produção": "#e57373",
    "desligada": "#3d3d3d",
    "sem status": "#3d3d3d",
}

def normalizar_status(status):
    if not status:
        return "sem status"
    return status.strip().lower()

# ======================================================
# Controle de expansão
# ======================================================
if "linha_expandida" not in st.session_state:
    st.session_state["linha_expandida"] = None

# ======================================================
# 1️⃣ PROCESSAR O CLIQUE ANTES DE RENDERIZAR A PÁGINA
# ======================================================
query = st.query_params

if "toggle_linha" in query:

    clicked = int(query["toggle_linha"])
    st.session_state["linha_expandida"] = (
        clicked if clicked != st.session_state["linha_expandida"] else None
    )

    # Limpando URL
    st.query_params.clear()

    # Recarrega página
    st.rerun()

# ======================================================
# 2️⃣ AGORA RENDERIZA AS LINHAS
# ======================================================
linhas = run_query("SELECT id, nome FROM linhas_producao ORDER BY id")

for linha in linhas:
    linha_id = linha["id"]
    linha_nome = linha["nome"]

    expandida = st.session_state["linha_expandida"] == linha_id

    toggle_params = urlencode({"toggle_linha": linha_id})

    st.markdown(
        f"""
        <a href="?{toggle_params}" target="_self" style="text-decoration:none;">
            <h3 style="cursor:pointer; color:white; margin-bottom:5px;">
                {'🔽' if expandida else '▶️'} {linha_nome}
            </h3>
        </a>
        """,
        unsafe_allow_html=True,
    )


    # Carregar máquinas
    maquinas = run_query(
        "SELECT id, nome_maquina FROM ihms WHERE id_linha_producao = ? ORDER BY id",
        [linha_id],
    )

    # Container horizontal dos cards
    cards_html = '<div style="display:block; overflow-x:auto; white-space:nowrap; padding-bottom:10px;">'

    for maq in maquinas:

        maq_id = maq["id"]
        nome_maquina = maq["nome_maquina"]

        status_query = run_query(
            """
            SELECT TOP 1 status_maquina
            FROM maqteste_status_geral
            WHERE id_ihm = ?
            ORDER BY datahora DESC
            """,
            [maq_id],
        )

        status = normalizar_status(status_query[0]["status_maquina"] if status_query else "sem status")
        color = STATUS_COLORS.get(status, "#d9d9d9")

        params = urlencode({"maq": maq_id, "nome": nome_maquina})
        link = f"?{params}"

        cards_html += f'''
<a href="{link}" style="text-decoration:none; display:inline-block; margin-right:15px;">
  <div style="
    width:230px;
    background-color:{color};
    padding:20px;
    border-radius:10px;
    text-align:center;
    cursor:pointer;
    box-sizing:border-box;
    white-space:normal;
  ">
    <b style="font-size:18px; color:white;">{nome_maquina}</b><br>
    <span style="font-size:14px; color:white;">{status.capitalize()}</span>
  </div>
</a>
'''

    cards_html += "</div>"
    st.markdown(cards_html, unsafe_allow_html=True)

    # SE ESTA LINHA ESTÁ EXPANDIDA
    if expandida:
        st.markdown("#### 🔎 Detalhes da linha")
        st.info(f"Visão expandida da linha **{linha_nome}**.")
    
    st.markdown("---")