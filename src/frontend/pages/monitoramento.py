import streamlit as st
from datetime import datetime
from ui.styles import BASE_CSS
from ui.components import render_topbar, render_last_events

st.set_page_config(page_title="PCP Monitor", layout="wide")

# mocks
page_title = "Monitoramento de Chão de Fábrica"
oee_global = 78.4
maquinas_ativas = 28
maquinas_total = 32
now_str = datetime.now().strftime("%d/%m/%Y - %H:%M:%S")  # se quiser usar depois

ultimos_eventos = [
    {"hora": "14:32", "maq": "CUSI_02", "msg": "Parada de setup iniciada", "tipo": "warn"},
    {"hora": "14:28", "maq": "MAQ_24",  "msg": "Retorno de operação",      "tipo": "ok"},
    {"hora": "14:15", "maq": "MAQ_26",  "msg": "Falha de comunicação Driver 12", "tipo": "err"},
]

# render
st.markdown(BASE_CSS, unsafe_allow_html=True)
st.markdown(render_topbar(page_title, oee_global, maquinas_ativas, maquinas_total), unsafe_allow_html=True)
st.markdown(render_last_events(ultimos_eventos), unsafe_allow_html=True)