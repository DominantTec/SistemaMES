import streamlit as st
from datetime import datetime

st.set_page_config(page_title="PCP Monitor", layout="wide")

# =========================
# MOCKS (depois você troca)
# =========================
page_title = "Monitoramento de Chão de Fábrica"
oee_global = 78.4
maquinas_ativas = 28
maquinas_total = 32
now_str = datetime.now().strftime("%d/%m/%Y - %H:%M:%S")

ultimos_eventos = [
    {"hora": "14:32", "maq": "CUSI_02", "msg": "Parada de setup iniciada", "tipo": "warn"},
    {"hora": "14:28", "maq": "MAQ_24",  "msg": "Retorno de operação",      "tipo": "ok"},
    {"hora": "14:15", "maq": "MAQ_26",  "msg": "Falha de comunicação Driver 12", "tipo": "err"},
]

# =========================
# CSS
# =========================
st.markdown("""
<style>
/* ---- Topbar ---- */
.topbar{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:16px;
  padding: 10px 14px;
  border: 1px solid #E5E7EB;
  border-radius: 14px;
  background: #FFFFFF;
}
.topbar-left{
  display:flex;
  align-items:baseline;
  gap:12px;
  flex-wrap:wrap;
}
.topbar-title{
  font-size: 22px;
  font-weight: 800;
  color:#111827;
  margin:0;
}
.topbar-divider{
  width:1px;
  height:20px;
  background:#E5E7EB;
}
.kpi{
  display:flex;
  align-items:center;
  gap:8px;
  color:#374151;
  font-size: 14px;
}
.kpi b{
  color:#111827;
  font-size: 15px;
}
.topbar-right{
  display:flex;
  align-items:center;
  gap:10px;
}
.time-pill{
  padding: 8px 10px;
  border: 1px solid #E5E7EB;
  border-radius: 10px;
  background:#F9FAFB;
  font-weight: 700;
  color:#111827;
  font-size: 13px;
}

/* ---- Eventos ---- */
.events-row{
  margin-top: 10px;
  padding: 10px 14px;
  border: 1px solid #E5E7EB;
  border-radius: 14px;
  background: #FFFFFF;
  display:flex;
  gap:12px;
  align-items:center;
  overflow:hidden;
}
.events-label{
  font-weight:800;
  color:#111827;
  white-space:nowrap;
}
.event-item{
  display:flex;
  align-items:center;
  gap:10px;
  padding: 0 10px;
  border-left: 1px solid #333232;
  white-space:nowrap;
  color:#374151;
  font-size: 14px;
}
.event-time{
  color:#6B7280;
  font-variant-numeric: tabular-nums;
}
.event-maq{
  font-weight:800;
  color:#111827;
}
.dot{
  width:10px;
  height:10px;
  border-radius:999px;
  display:inline-block;
}
.dot-ok{ background:#22C55E; }
.dot-warn{ background:#F59E0B; }
.dot-err{ background:#EF4444; }
</style>
""", unsafe_allow_html=True)

# =========================
# TOPO: título + KPIs
# =========================
teto_html = f"""
  <div class="topbar">
    <div class="topbar-left">
      <div class="topbar-title">{page_title}</div>
      <div class="topbar-divider"></div>
      <div class="kpi">
        <span class="dot dot-ok"></span>
        <span>OEE Global:</span>
        <b>{oee_global:.1f}%</b>
      </div>
      <div class="kpi">
        <span style="opacity:.65;">⚡</span>
        <span>Máquinas Ativas:</span>
        <b>{maquinas_ativas}/{maquinas_total}</b>
      </div>
    </div>

    <div class="topbar-right">
      <div style="width:34px; height:34px; border-radius:999px; background:#E5E7EB;"></div>
    </div>
  </div>
"""
def dot_class(tipo):
    return {
        "ok": "dot-ok",
        "warn": "dot-warn",
        "err": "dot-err",
    }.get(tipo, "dot-warn")

events_html = f"""
  <div class='events-row'><div class='events-label'>ÚLTIMOS EVENTOS</div>
  
  <div class="event-item">
    <span class="event-time">{ultimos_eventos[0]["hora"]}</span>
    <span class="dot {dot_class(ultimos_eventos[0]["tipo"])}"></span>
    <span class="event-maq">{ultimos_eventos[0]["maq"]}</span>
    <span class="event-msg">{ultimos_eventos[0]["msg"]}</span>
  </div>

  <div class="event-item">
    <span class="event-time">{ultimos_eventos[1]["hora"]}</span>
    <span class="dot {dot_class(ultimos_eventos[1]["tipo"])}"></span>
    <span class="event-maq">{ultimos_eventos[1]["maq"]}</span>
    <span class="event-msg">{ultimos_eventos[1]["msg"]}</span>
  </div>

  <div class="event-item">
    <span class="event-time">{ultimos_eventos[2]["hora"]}</span>
    <span class="dot {dot_class(ultimos_eventos[2]["tipo"])}"></span>
    <span class="event-maq">{ultimos_eventos[2]["maq"]}</span>
    <span class="event-msg">{ultimos_eventos[2]["msg"]}</span>
  </div>
"""
st.markdown(teto_html, unsafe_allow_html=True)
st.markdown(events_html, unsafe_allow_html=True)