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

# Estado de expansão das linhas
if "linhas_expandidas" not in st.session_state:
    st.session_state.linhas_expandidas = {}

# ======================================================
#  RENDERIZAR LISTA DE LINHAS DE PRODUÇÃO
# ======================================================
linhas = get_active_lines()

for i, linha in linhas.iterrows():

    linha_id = str(linha["id_linha_producao"])
    linha_nome = linha["tx_name"]

    # inicialização
    if linha_id not in st.session_state.linhas_expandidas:
        st.session_state.linhas_expandidas[linha_id] = False

    # botão toggle primeiro (ANTES de calcular o ícone)
    if st.button(
        f"{'🔽' if st.session_state.linhas_expandidas[linha_id] else '▶️'} {linha_nome}",
        key=f"toggle_{linha_id}"
    ):
        # alterna
        st.session_state.linhas_expandidas[linha_id] = not st.session_state.linhas_expandidas[linha_id]
        st.rerun()   # <<< ESTA LINHA É ESSENCIAL

    # depois do clique, agora sim o estado está atualizado
    expandida = st.session_state.linhas_expandidas[linha_id]
    icon = "🔽" if expandida else "▶️"

    # ======================================================
    #  CARREGAR MÁQUINAS ATIVAS
    # ======================================================
    maquinas = get_active_machines(linha_id)

    cards_html = (
        '<div style="display:block; overflow-x:auto; white-space:nowrap; '
        'padding-bottom:10px;">'
    )

    # ======================================================
    #  LOOP DAS MÁQUINAS
    # ======================================================
    for m, maq in maquinas.iterrows():

        maq_id_raw = maq["id_ihm"]
        nome_maquina = maq["tx_name"]

        # Carregar métricas da máquina
        ultimo = get_metrics_machine(maq_id_raw)
        color = STATUS_COLORS.get(ultimo["status_maquina"], "#d9d9d9")

        # ======================================================
        #  DETALHES QUANDO EXPANDIDO
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
        #  CARD HTML
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
