import streamlit as st
from services.db import run_query
from services.queries import get_machine_timeline, get_active_machines
from datetime import datetime, time, timedelta
import pandas as pd

st.set_page_config(page_title="Detalhes da Máquina", layout="wide")

# ============================
# Ler ID da máquina pela URL
# ============================
maq__id = st.query_params.get("maq_id", 0)

maq_id = st.selectbox('Máquina Selecionada:', get_active_machines(
    1)['id_ihm'].to_list(), get_active_machines(1)['id_ihm'].to_list().index(maq__id) if maq__id in get_active_machines(1)['id_ihm'].to_list() else 0)

if not maq_id:
    st.error("Nenhuma máquina selecionada.")
    st.stop()

maq_id = int(maq_id)

# ============================
# Buscar os dados da máquina
# ============================
info_ihm = run_query("""
    SELECT tx_name
    FROM tb_ihm
    WHERE id_ihm = :id
""", {"id": maq_id})

if len(info_ihm) == 0:
    st.error("Máquina não encontrada.")
    st.stop()

nome_maquina = info_ihm["tx_name"][0]

st.title(f"🖥️{nome_maquina}")

# ============================================================
# 📅 1. DEFINIÇÃO DO TURNO PADRÃO
# ============================================================
agora = datetime.now()

if agora.time() < time(8, 0):
    turno_inicio_default = (agora - timedelta(days=1)
                            ).replace(hour=8, minute=0, second=0)
else:
    turno_inicio_default = agora.replace(hour=8, minute=0, second=0)

turno_fim_default = agora

# ============================================================
# Inicializar session_state
# ============================================================
if "filtro_data_inicio" not in st.session_state:
    st.session_state["filtro_data_inicio"] = turno_inicio_default.date()

if "filtro_hora_inicio" not in st.session_state:
    st.session_state["filtro_hora_inicio"] = turno_inicio_default.time()

if "filtro_data_fim" not in st.session_state:
    st.session_state["filtro_data_fim"] = turno_fim_default.date()

if "filtro_hora_fim" not in st.session_state:
    st.session_state["filtro_hora_fim"] = turno_fim_default.time()


# ============================================================
# 🧭 2. INTERFACE DOS FILTROS
# ============================================================
st.markdown("## 🔍 Filtros de Período do Turno")

col1, col2, col3, col4 = st.columns(4)

with col1:
    dt_inicio = st.date_input(
        "Data Inicial",
        st.session_state["filtro_data_inicio"],
        format="DD/MM/YYYY"
    )
    st.session_state["filtro_data_inicio"] = dt_inicio

with col2:
    hr_inicio = st.time_input(
        "Hora Inicial",
        st.session_state["filtro_hora_inicio"],
        step=timedelta(minutes=1)
    )
    st.session_state["filtro_hora_inicio"] = hr_inicio

with col3:
    dt_fim = st.date_input(
        "Data Final",
        st.session_state["filtro_data_fim"],
        format="DD/MM/YYYY"
    )
    st.session_state["filtro_data_fim"] = dt_fim

with col4:
    hr_fim = st.time_input(
        "Hora Final",
        st.session_state["filtro_hora_fim"],
        step=timedelta(minutes=1)
    )
    st.session_state["filtro_hora_fim"] = hr_fim

# Criar objetos datetime
data_inicio = datetime.combine(dt_inicio, hr_inicio)
data_fim = datetime.combine(dt_fim, hr_fim)

if data_fim <= data_inicio:
    st.warning("⚠ A data final deve ser maior que a data inicial.")

# =====================================================
# 3️⃣ Gerar gráfico de pizza (se houver registros)
# =====================================================
st.write("## 🥧 Distribuição de Status da Máquina")

registros = get_machine_timeline(maq_id, data_inicio, data_fim)

if len(registros) < 2:
    st.warning("⚠ Não há registros suficientes no período para montar o gráfico.")
else:
    # dict status -> minutos
    tempos = {}

    for i in range(len(registros) - 1):
        atual = registros.loc[i]
        proximo = registros.loc[i + 1]

        status = atual["status_maquina"]
        t1 = atual["dt_created_at"]
        t2 = proximo["dt_created_at"]

        duracao_min = (t2 - t1).total_seconds() / 60
        tempos[status] = tempos.get(status, 0) + duracao_min

    # Último registro
    ultimo_status = registros["status_maquina"].to_list()[-1]
    duracao_ultimo = (
        data_fim - registros["dt_created_at"].to_list()[-1]).total_seconds() / 60
    tempos[ultimo_status] = tempos.get(ultimo_status, 0) + duracao_ultimo

    # converter em DataFrame
    df = pd.DataFrame({
        "status": list(tempos.keys()),
        "minutos": list(tempos.values())
    })

    pie_chart_spec = {
        "mark": {"type": "arc", "outerRadius": 120},
        "encoding": {
            "theta": {"field": "minutos", "type": "quantitative"},
            "color": {"field": "status", "type": "nominal"},
            "tooltip": [
                {"field": "status", "type": "nominal"},
                {"field": "minutos", "type": "quantitative"}
            ]
        }
    }

    st.vega_lite_chart(df, pie_chart_spec, use_container_width=True)

    st.write("## 🟦 Timeline de Status da Máquina")

if len(registros) < 2:
    st.warning("⚠ Não há registros suficientes para gerar timeline.")
else:
    # Construir intervalos
    timeline_rows = []

    for i in range(len(registros) - 1):
        atual = registros.loc[i]
        proximo = registros.loc[i + 1]

        timeline_rows.append({
            "status": atual["status_maquina"],
            "inicio": atual["dt_created_at"],
            "fim": proximo["dt_created_at"]
        })

    # último registro dura até o final do período
    timeline_rows.append({
        "status": registros["status_maquina"].to_list()[-1],
        "inicio": registros["dt_created_at"].to_list()[-1],
        "fim": data_fim
    })

    df_timeline = pd.DataFrame(timeline_rows)

    # Especificação do Vega-Lite
    timeline_spec = {
        "mark": "bar",
        "encoding": {
            "x": {"field": "inicio", "type": "temporal", "title": "Início"},
            "x2": {"field": "fim"},
            "y": {"field": "status", "type": "nominal", "title": "Status"},
            "color": {"field": "status", "type": "nominal"},
            "tooltip": [
                {"field": "status", "type": "nominal"},
                {"field": "inicio", "type": "temporal"},
                {"field": "fim", "type": "temporal"}
            ]
        }
    }

    st.vega_lite_chart(df_timeline, timeline_spec, use_container_width=True)
    # ============================================================
# 🎯 META X REALIZADO — GRÁFICO RADIAL (BONITÃO E CORRETO)
# ============================================================

st.write("## 🎯 Meta x Realizado (Radial)")

# META mockada
META = 110

# Buscar último registro dentro do período
registro_final = registros[registros['dt_created_at']
                           == registros['dt_created_at'].max()]

if len(registro_final) == 0:
    st.warning("Não há dados suficientes no período para gerar o gráfico.")
else:
    total_realizado = int(registro_final["total_produzido"].to_list()[0])

    # Calcular percentual (0 a 100)
    percentual = min((total_realizado / META) * 100, 100)

    # Criar DataFrame com 2 valores: progresso e restante
    df_radial = pd.DataFrame({
        "categoria": ["Realizado", "Restante"],
        "valor": [percentual, 100 - percentual]
    })

    # Gráfico radial correto
    radial_spec = {
        "mark": {
            "type": "arc",
            "innerRadius": 60,
            "outerRadius": 100
        },
        "encoding": {
            "theta": {"field": "valor", "type": "quantitative"},
            "color": {
                "field": "categoria",
                "scale": {
                    "domain": ["Realizado", "Restante"],
                    "range": ["#10b981", "#e5e7eb"]  # verde + cinza claro
                }
            },
            "tooltip": [
                {"field": "categoria", "type": "nominal"},
                {"field": "valor", "type": "quantitative"}
            ]
        },
        "view": {"stroke": None}
    }

    st.vega_lite_chart(df_radial, radial_spec, use_container_width=True)

    st.metric(
        label="Progresso da Meta",
        value=f"{percentual:.1f}%",
        delta=f"{total_realizado}/{META} unidades"
    )
