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
#  Controle de expansão (session_state)
# ======================================================
if "linha_expandida" not in st.session_state:
    st.session_state["linha_expandida"] = None  # vamos guardar como string


# ======================================================
# 1️⃣ PROCESSAR CLIQUE (antes de renderizar a página)
# ======================================================
query = st.query_params

if "toggle_linha" in query:
    clicked = str(query["toggle_linha"])  # garante string

    # alterna expandir / retrair
    if st.session_state["linha_expandida"] == clicked:
        st.session_state["linha_expandida"] = None
    else:
        st.session_state["linha_expandida"] = clicked

    st.query_params.clear()
    st.rerun()


# ======================================================
# 2️⃣ RENDERIZAR LISTA DE LINHAS
# ======================================================
linhas = run_query("SELECT id, nome FROM linhas_producao ORDER BY id")

for linha in linhas:
    linha_id_raw = linha["id"]
    linha_id = str(linha_id_raw)
    linha_nome = linha["nome"]

    expandida = st.session_state["linha_expandida"] == linha_id

    toggle_params = urlencode({"toggle_linha": linha_id})

    # Cabeçalho clicável
    st.markdown(
        f"""<a href="?{toggle_params}" target="_self" style="text-decoration:none;">
<h3 style="cursor:pointer; color:white; margin-bottom:5px;">
  {'🔽' if expandida else '▶️'} {linha_nome}
</h3>
</a>""",
        unsafe_allow_html=True,
    )


    # ======================================================
    #  Carregar máquinas desta linha
    # ======================================================
    maquinas = run_query(
        "SELECT id, nome_maquina FROM ihms WHERE id_linha_producao = ? ORDER BY id",
        [linha_id_raw],
    )

    cards_html = '<div style="display:block; overflow-x:auto; white-space:nowrap; padding-bottom:10px;">'

    for maq in maquinas:
        maq_id_raw = maq["id"]
        maq_id = str(maq_id_raw)
        nome_maquina = maq["nome_maquina"]

        # ================================
        # 🔍 ÚLTIMO REGISTRO DA MÁQUINA
        # ================================
        ultimo = run_query(
            """
            SELECT TOP 1
                status_maquina,
                meta,
                produzido,
                reprovado,
                total_produzido,
                operador,
                manutentor
            FROM maqteste_status_geral
            WHERE id_ihm = ?
            ORDER BY datahora DESC
            """,
            [maq_id_raw],
        )

        if ultimo:
            ultimo = ultimo[0]
        else:
            ultimo = {
                "status_maquina": "sem status",
                "meta": "--",
                "produzido": 0,
                "reprovado": 0,
                "total_produzido": 0,
                "operador": "--",
                "manutentor": "--",
            }

        # Normalizar status
        status = normalizar_status(ultimo["status_maquina"])
        meta = ultimo["meta"]
        acumulado = ultimo["total_produzido"]  # acumulado real
        operador = ultimo["operador"]
        manutentor = ultimo["manutentor"]

        color = STATUS_COLORS.get(status, "#d9d9d9")

        # ================================
        # 🔽 DETALHES EXIBIDOS NA EXPANSÃO
        # ================================
        if expandida:
            detalhes_html = f"""
                <div style="margin-top:10px; text-align:left; color:black; font-size:12px;">
                    <b>Status:</b> {status.capitalize()}<br>
                    <b>OEE:</b> -- %<br>
                    <b>Eficiência:</b> -- %<br>
                    <b>Qualidade:</b> -- %<br>
                    <b>Meta:</b> {meta}<br>
                    <b>Produzido:</b> {ultimo['produzido']}<br>
                    <b>Reprovado:</b> {ultimo['reprovado']}<br>
                    <b>Total Produzido:</b> {ultimo['total_produzido']}<br>
                    <b>Operador:</b> {operador}<br>
                    <b>Manutentor:</b> {manutentor}<br>
                </div>
            """
        else:
            detalhes_html = ""

        # ================================
        # 👉 LINK PARA A PÁGINA /machine
        # ================================
        params = urlencode({"maq_id": maq_id})
        link = f"/machine?{params}"

        # ================================
        # 🎨 CARD DA MÁQUINA
        # ================================
        cards_html += (
            f'<a href="{link}" target="_self" '
            'style="text-decoration:none; display:inline-block; margin-right:15px;">'
            '<div style="'
            'width:230px;'
            f'min-height:{"260px" if expandida else "120px"};'
            'background-color:white;'
            'padding:0;'
            'border-radius:10px;'
            'text-align:center;'
            'cursor:pointer;'
            'box-sizing:border-box;'
            'white-space:normal;'
            'color:black;'
            'border:1px solid #ddd;'
            '">'
            f'<div style="width:100%; height:25px; background-color:{color};'
            'border-radius:10px 10px 0 0;"></div>'
            '<div style="padding:12px;">'
            f'<b style="font-size:16px;">{nome_maquina}</b><br>'
            f'<span style="font-size:13px;">{status.capitalize()}</span>'
            f'{detalhes_html}'
            '</div>'
            '</div>'
            '</a>'
        )

    cards_html += "</div>"
    st.markdown(cards_html, unsafe_allow_html=True)

    st.markdown("---")