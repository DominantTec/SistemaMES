import streamlit as st
from urllib.parse import urlencode

from services.queries import (
    get_active_lines,
    get_active_machines,
    get_metrics_machine
)


# ======================================================
#  CONFIG STREAMLIT
# ======================================================
st.set_page_config(page_title="Visão Geral MES", layout="wide")
st.title("🏭 Visão Geral da Produção")

# Paleta de cores dos status
STATUS_COLORS = {
    "Produzindo": "#96d779",
    "Limpeza": "#f7c76c",
    "Parada": "#e57373",
    "Passar Padrão": "#3d3d3d"
}

# ======================================================
#  CONTROLE DE EXPANSÃO VIA session_state
# ======================================================
if "linha_expandida" not in st.session_state:
    st.session_state["linha_expandida"] = None  # vamos guardar como string


# ======================================================
#  PROCESSA CLIQUE DO USUÁRIO ANTES DE RENDERIZAR
# ======================================================
query = st.query_params

if "toggle_linha" in query:
    clicked = str(query["toggle_linha"])

    if st.session_state["linha_expandida"] == clicked:
        st.session_state["linha_expandida"] = None
    else:
        st.session_state["linha_expandida"] = clicked

    st.query_params.clear()
    st.rerun()


# ======================================================
#  RENDERIZAR LISTA DE LINHAS DE PRODUÇÃO
# ======================================================
linhas = get_active_lines()

for i, linha in linhas.iterrows():
    linha_id_raw = linha['id_linha_producao']
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
    #  CARREGAR MÁQUINAS ATIVAS
    # ======================================================
    maquinas = get_active_machines(linha_id_raw)

    cards_html = (
        '<div style="display:block; overflow-x:auto; white-space:nowrap; '
        'padding-bottom:10px;">'
    )

    for m, maq in maquinas.iterrows():
        maq_id_raw = maq["id_ihm"]
        nome_maquina = maq["nome_maquina"]

        # Carregar métricas da máquina
        ultimo = get_metrics_machine(maq_id_raw)

        color = STATUS_COLORS.get(ultimo["status_maquina"], "#d9d9d9")

        # ======================================================
        #  DETALHES MOSTRADOS SOMENTE QUANDO EXPANDIDO
        # ======================================================
        if expandida:
            detalhes_html = f"""
                <div style="margin-top:10px; text-align:left; color:black; font-size:12px;">
                    <b>Status:</b> {ultimo["status_maquina"].capitalize()}<br>
                    <b>OEE:</b> {ultimo['oee']} %<br>
                    <b>Eficiência:</b> {ultimo['eficiencia']} %<br>
                    <b>Qualidade:</b> {ultimo['qualidade']} %<br>
                    <b>Meta:</b> {ultimo["meta"]}<br>
                    <b>Produzido:</b> {ultimo['produzido']}<br>
                    <b>Reprovado:</b> {ultimo['reprovado']}<br>
                    <b>Total Produzido:</b> {ultimo['total_produzido']}<br>
                    <b>Operador:</b> {ultimo["operador"]}<br>
                    <b>Manutentor:</b> {ultimo["manutentor"]}<br>
                </div>
            """
        else:
            detalhes_html = ""

        # ======================================================
        #  LINK PARA A PÁGINA /machine
        # ======================================================
        link = f"/machine?{urlencode({'maq_id': str(maq_id_raw)})}"

        # ======================================================
        #  CARD DA MÁQUINA
        # ======================================================
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
            f'<span style="font-size:13px;">{ultimo["status_maquina"].capitalize()}</span>'
            f'{detalhes_html}'
            '</div>'
            '</div>'
            '</a>'
        )

    cards_html += "</div>"
    st.markdown(cards_html, unsafe_allow_html=True)

    st.markdown("---")
