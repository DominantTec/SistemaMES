import streamlit as st
from datetime import datetime
from random import randint, choice

st.set_page_config(page_title="PCP Monitor", layout="wide")

# =========================
# CSS (layout + componentes)
# =========================
st.markdown("""
<style>
/* ---------- Base ---------- */
.block-container { padding-top: 0.8rem; }
h1,h2,h3,h4,p { margin: 0; }

:root{
  --bg: #F7F8FA;
  --card: #FFFFFF;
  --muted: #6B7280;
  --text: #111827;
  --line: #E5E7EB;
  --blue: #0B5ED7;
  --green: #16A34A;
  --amber: #D97706;
  --red: #DC2626;
}

/* Remove espaço extra no topo do main */
section.main > div { background: var(--bg); }

/* ---------- Topbar ---------- */
.topbar{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:16px;
  padding: 12px 14px;
  border:1px solid var(--line);
  border-radius: 12px;
  background: var(--card);
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.topbar-left{
  display:flex;
  align-items:center;
  gap:10px;
}
.brand-badge{
  width:34px;height:34px;border-radius:10px;
  background:#E8F1FF;color:var(--blue);
  display:flex;align-items:center;justify-content:center;
  font-weight:800;
}
.topbar-title{
  font-size:18px;
  font-weight:700;
  color: var(--text);
}
.metrics{
  display:flex;
  align-items:center;
  gap:18px;
  color: var(--text);
  font-size: 13px;
}
.metric{
  display:flex;
  gap:8px;
  align-items:center;
  padding: 6px 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: #FBFBFC;
}
.metric .k { color: var(--muted); }
.metric .v { font-weight: 700; }
.topbar-right{
  display:flex;
  align-items:center;
  gap:12px;
}
.clock{
  font-size:12px;
  color: var(--muted);
  padding: 6px 10px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: #FBFBFC;
}
.avatar{
  width:30px;height:30px;border-radius:999px;
  background:#D1D5DB;
}

/* ---------- Events strip ---------- */
.events{
  margin-top: 10px;
  padding: 10px 14px;
  border:1px solid var(--line);
  border-radius: 12px;
  background: var(--card);
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
  display:flex;
  gap:10px;
  align-items:center;
  color: var(--text);
  font-size: 12px;
}
.events .label{
  font-weight: 700;
  color: var(--muted);
  min-width: 125px;
}
.event-item{
  display:flex;
  gap:8px;
  align-items:center;
  padding: 0 10px;
  border-left: 1px solid var(--line);
  white-space: nowrap;
}
.dot{
  width:7px;height:7px;border-radius:999px;
  display:inline-block;
}
.dot.green{ background: var(--green); }
.dot.amber{ background: var(--amber); }
.dot.red{ background: var(--red); }

/* ---------- Line section ---------- */
.line-section{
  margin-top: 14px;
}
.line-header{
  display:flex;
  align-items:center;
  justify-content:space-between;
  margin: 6px 2px 10px 2px;
}
.line-badge{
  display:inline-flex;
  align-items:center;
  gap:10px;
  font-weight: 800;
  color: #FFFFFF;
  background: #2563EB;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
}
.line-meta{
  font-size: 12px;
  color: var(--muted);
}

/* ---------- Machine cards grid ---------- */
.machine-grid{
  display:grid;
  grid-template-columns: repeat(4, minmax(220px, 1fr));
  gap: 12px;
}

/* Responsivo (se tela menor) */
@media (max-width: 1200px){
  .machine-grid{ grid-template-columns: repeat(2, minmax(220px, 1fr)); }
}
@media (max-width: 700px){
  .machine-grid{ grid-template-columns: 1fr; }
}

/* ---------- Machine card ---------- */
.mcard{
  border:1px solid var(--line);
  border-radius: 12px;
  background: var(--card);
  padding: 12px 12px 10px 12px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.mhead{
  display:flex;
  align-items:center;
  justify-content:space-between;
  margin-bottom: 8px;
}
.mname{
  font-weight: 800;
  color: #F9FAFB;
  background: #E5E7EB;
  border-radius: 10px;
  padding: 6px 10px;
  font-size: 11px;
}
.mname.ok{ background: #D1FAE5; color:#065F46; }
.mname.warn{ background: #FEF3C7; color:#92400E; }
.mname.bad{ background: #FEE2E2; color:#991B1B; }

.mmeta{
  font-size: 11px;
  color: var(--muted);
}

.oee{
  margin-top: 6px;
  display:flex;
  align-items:flex-end;
  justify-content:space-between;
}
.oee .label{ font-size: 11px; color: var(--muted); font-weight: 700; }
.oee .value{ font-size: 22px; font-weight: 900; color: var(--text); }

.bars{
  margin-top: 8px;
  display:flex;
  flex-direction:column;
  gap: 6px;
}
.bar-row{
  display:grid;
  grid-template-columns: 48px 1fr 40px;
  gap: 8px;
  align-items:center;
  font-size: 11px;
  color: var(--muted);
}
.track{
  width:100%;
  height: 6px;
  border-radius: 999px;
  background: #EEF0F3;
  overflow:hidden;
}
.fill{
  height:100%;
  border-radius: 999px;
}
.fill.green{ background: var(--green); }
.fill.amber{ background: var(--amber); }
.fill.red{ background: var(--red); }

.prodline{
  margin-top: 10px;
  font-size: 11px;
  color: var(--muted);
  display:flex;
  justify-content:space-between;
  border-top: 1px solid var(--line);
  padding-top: 8px;
}

/* Sidebar tweaks */
[data-testid="stSidebar"]{
  background: #F3F4F6;
}
.sidebar-brand{
  display:flex;align-items:center;gap:10px;
  padding: 6px 4px 12px 4px;
}
.sidebar-logo{
  width:34px;height:34px;border-radius:10px;
  background:#E8F1FF;color:var(--blue);
  display:flex;align-items:center;justify-content:center;
  font-weight:900;
}
.sidebar-title{
  font-weight: 800;
  color: var(--text);
}
.small-muted{ color: var(--muted); font-size: 12px; }

/* Helper chips */
.chip{
  display:inline-flex;
  align-items:center;
  gap:8px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: #FFFFFF;
}
</style>
""", unsafe_allow_html=True)

# =========================
# Dados mocados
# =========================
def make_mock_events():
    # (hora, maquina, mensagem, severidade)
    severities = ["green", "amber", "red"]
    msgs = [
        "Parada de setup iniciada",
        "Retorno de operação",
        "Falha de comunicação Driver 12",
        "Troca de ferramenta",
        "Microparada detectada",
        "Alarme de segurança",
    ]
    machines = ["CUSI_02", "MAQ_24", "MAQ_26", "MAQ_25", "MAQ_37", "MAQ_34"]
    items = []
    for _ in range(3):
        hh = randint(14, 15)
        mm = randint(0, 59)
        items.append((f"{hh:02d}:{mm:02d}", choice(machines), choice(msgs), choice(severities)))
    return items

def score_color(pct: float):
    # similar ao print: verde ok, amarelo intermediário, vermelho ruim
    if pct >= 70:
        return "green"
    if pct >= 40:
        return "amber"
    return "red"

def header_color_for_machine(oee: float):
    if oee >= 70:
        return "ok"
    if oee >= 40:
        return "warn"
    return "bad"

def make_mock_factory():
    # Estrutura: linhas -> máquinas
    def machine(name):
        oee = round(randint(120, 850) / 10, 1)  # 12.0 a 85.0 (aprox)
        disp = randint(40, 100)
        qual = randint(40, 100)
        prod = randint(40, 100)
        # produção: atual / meta
        meta = randint(250, 850)
        atual = int(meta * (randint(40, 110) / 100))
        return {
            "name": name,
            "oee": oee,
            "disp": disp,
            "qual": qual,
            "prod": prod,
            "atual": atual,
            "meta": meta,
        }

    linhas = [
        {
            "code": "LINHA 505",
            "meta_hora": 850,
            "realizado": 812,
            "pct": 95,
            "machines": [machine("CUSI_02"), machine("MAQ_24"), machine("MAQ_26"), machine("MAQ_25")],
        },
        {
            "code": "LINHA 504",
            "meta_hora": 1200,
            "realizado": 1150,
            "pct": 98,
            "machines": [machine("PRENSA_27"), machine("MAQ_10"), machine("MAQ_39"), machine("MAQ_37"), machine("MAQ_34"), machine("MAQ_33")],
        },
        {
            "code": "LINHA 506",
            "meta_hora": 500,
            "realizado": 320,
            "pct": 64,
            "machines": [machine("MAQ_38"), machine("MAQ_32")],
        },
    ]
    return linhas

# =========================
# Componentes de UI
# =========================
def render_topbar(oee_global: float, active_machines: str):
    now = datetime.now().strftime("%d/%m/%Y • %H:%M:%S")
    st.markdown(f"""
<div class="topbar">
  <div class="topbar-left">
    <div class="brand-badge">∿</div>
    <div>
      <div class="topbar-title">Monitoramento de Chão de Fábrica</div>
    </div>
  </div>

  <div class="metrics">
    <div class="metric"><span class="k">OEE Global:</span> <span class="v">{oee_global:.1f}%</span></div>
    <div class="metric"><span class="k">Máquinas Ativas:</span> <span class="v">{active_machines}</span></div>
  </div>

  <div class="topbar-right">
    <div class="clock">{now}</div>
    <div class="avatar"></div>
  </div>
</div>
""", unsafe_allow_html=True)

def render_events(events):
    # events: list[(hhmm, machine, msg, sev)]
    parts = []
    for hhmm, machine, msg, sev in events:
        parts.append(f"""
<div class="event-item">
  <span class="dot {sev}"></span>
  <span style="color:var(--muted);">{hhmm}</span>
  <strong>{machine}</strong>
  <span style="color:var(--muted);">{msg}</span>
</div>
""")
    st.markdown(f"""
<div class="events">
  <div class="label">ÚLTIMOS EVENTOS:</div>
  {''.join(parts)}
</div>
""", unsafe_allow_html=True)

def render_machine_card(m):
    oee = m["oee"]
    disp = m["disp"]
    qual = m["qual"]
    prod = m["prod"]
    atual = m["atual"]
    meta = m["meta"]

    head_class = header_color_for_machine(oee)

    def bar(color, value):
        return f"""
<div class="bar-row">
  <div>{color}</div>
  <div class="track"><div class="fill {score_color(value)}" style="width:{value}%;"></div></div>
  <div style="text-align:right; color: var(--muted);">{value}%</div>
</div>
"""

    # Labels curtos igual ao print
    st.markdown(f"""
<div class="mcard">
  <div class="mhead">
    <div class="mname {head_class}">{m['name']}</div>
    <div class="mmeta"></div>
  </div>

  <div class="oee">
    <div class="label">OEE ATUAL</div>
    <div class="value">{oee:.1f}%</div>
  </div>

  <div class="bars">
    <div class="bar-row">
      <div>Disp.</div>
      <div class="track"><div class="fill {score_color(disp)}" style="width:{disp}%;"></div></div>
      <div style="text-align:right;">{disp}%</div>
    </div>
    <div class="bar-row">
      <div>Qual.</div>
      <div class="track"><div class="fill {score_color(qual)}" style="width:{qual}%;"></div></div>
      <div style="text-align:right;">{qual}%</div>
    </div>
    <div class="bar-row">
      <div>Prod.</div>
      <div class="track"><div class="fill {score_color(prod)}" style="width:{prod}%;"></div></div>
      <div style="text-align:right;">{prod}%</div>
    </div>
  </div>

  <div class="prodline">
    <div>Prod.</div>
    <div><strong style="color:var(--text);">{atual}</strong> / {meta}</div>
  </div>
</div>
""", unsafe_allow_html=True)

def render_line_section(line):
    # Header da linha (badge + meta)
    st.markdown(f"""
<div class="line-section">
  <div class="line-header">
    <div class="line-badge">{line['code']}</div>
    <div class="line-meta">Meta Hora: <strong style="color:var(--text);">{line['meta_hora']}</strong> • Realizado: <strong style="color:var(--text);">{line['realizado']}</strong> ({line['pct']}%)</div>
  </div>
</div>
""", unsafe_allow_html=True)

    # Grid de cards
    st.markdown('<div class="machine-grid">', unsafe_allow_html=True)
    cols = st.columns(4)
    i = 0
    for m in line["machines"]:
        with cols[i % 4]:
            render_machine_card(m)
        i += 1
        if i % 4 == 0 and i < len(line["machines"]):
            cols = st.columns(4)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# Sidebar
# =========================
with st.sidebar:
    st.markdown("""
<div class="sidebar-brand">
  <div class="sidebar-logo">∿</div>
  <div>
    <div class="sidebar-title">PCP Monitor</div>
    <div class="small-muted">Visão principal</div>
  </div>
</div>
""", unsafe_allow_html=True)

    st.markdown("### Menu")
    st.radio(
        label="",
        options=["Visão Geral", "Ordens em Aberto"],
        index=0
    )

    st.markdown("### Linhas de Produção")
    st.checkbox("Linha 505", value=True)
    st.checkbox("Linha 504", value=True)
    st.checkbox("Linha 506", value=True)

    st.markdown("---")
    st.markdown("**Turno Atual:** T2")
    st.progress(0.65)
    st.caption("Encerra em 04:32h")

# =========================
# Main
# =========================
# Topbar + Eventos
render_topbar(oee_global=78.4, active_machines="28/32")
render_events(make_mock_events())

# Linhas e cards
factory = make_mock_factory()
for line in factory:
    render_line_section(line)