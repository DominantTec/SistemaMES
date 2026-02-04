import logging
import streamlit as st
from services.modbus import get_registers_values, post_registers_values
from services.queries import get_active_machines, get_machine_hours, get_possible_pieces, get_selected_piece, get_meta, insert_meta
from services.utils import get_weekday_start, get_last_day_month, fill_month_database, post_working_hours, to_time
from datetime import datetime

st.title("Settings")

machine = st.selectbox("Máquina", get_active_machines(1)
                       ['tx_name'].to_list())
machine_id = {"MAQUINA_1": 1, "MAQUINA_2": 2}[machine]

# Operador -> Registrador
with st.form("form_operador"):
    operator = st.number_input('Operador', min_value=0, step=1,
                               value=get_registers_values(machine, 0))
    submit_operador = st.form_submit_button("Muda operador")

if submit_operador:
    if post_registers_values(machine, 0, int(operator)):
        st.success('Funcionou')
    else:
        st.error('Não Funcionou')

# Meta e peça da máquina
with st.form("form_meta"):
    col1, col2 = st.columns(2)
    with col1:
        possible_pieces = get_possible_pieces(machine_id)
        peca = st.selectbox("Peça", possible_pieces, index=possible_pieces.index(
            get_selected_piece(machine_id)))
    with col2:
        meta = st.number_input('Meta', min_value=0, step=1,
                               value=get_meta(machine_id))
    submit_meta = st.form_submit_button("Ajustar Meta")

if submit_meta:
    if insert_meta(machine_id, peca, meta):
        st.success('Meta ajustada!')
    else:
        st.error('Meta não ajustada!')


# Calendário funcionamento
st.write("Calendário Funcionamento")
today = datetime.now()
col1, col2 = st.columns(2)
with col1:
    month_funcionamento = st.selectbox("Mês", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], index=[
        1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].index(today.month))
with col2:
    year_funcionamento = st.selectbox("Ano", [2025, 2026], index=[
                                      2025, 2026].index(today.year))
machine_hours = get_machine_hours(machine_id)

first_month_day = datetime(year_funcionamento, month_funcionamento, 1)
if len(machine_hours[(machine_hours['dt_inicio'] == first_month_day.day) & (machine_hours['dt_inicio'] == first_month_day.month) & (machine_hours['dt_inicio'] == first_month_day.year)]) == 0:
    fill_month_database(first_month_day)
    machine_hours = get_machine_hours(machine_id)

machine_hours['dia'] = machine_hours['dt_inicio'].apply(lambda x: x.day)
machine_hours['mes'] = machine_hours['dt_inicio'].apply(lambda x: x.month)
machine_hours['ano'] = machine_hours['dt_inicio'].apply(lambda x: x.year)

ctx_key = f"ctx_{machine_id}_{year_funcionamento}_{month_funcionamento}"
if st.session_state.get("calendar_ctx") != ctx_key:
    st.session_state["calendar_ctx"] = ctx_key
    for k in list(st.session_state.keys()):
        if k.endswith("_start") or k.endswith("_end"):
            del st.session_state[k]

weekday = get_weekday_start(
    datetime(year_funcionamento, month_funcionamento, 1))

cols = st.columns(7)
week = ['Segunda', 'Terça', 'Quarta',
        'Quinta', 'Sexta', 'Sábado', 'Domingo']
for k, col in enumerate(cols):
    with col:
        st.write(week[k])

with st.form("form_calendar"):
    for day in range(1, get_last_day_month(first_month_day) + 1):
        weekday_loop = (weekday + day - 1) % 7
        if weekday_loop == 0 or day == 1:
            cols = st.columns(7)

        row = machine_hours[(machine_hours['dia'] == day) &
                            (machine_hours['mes'] == month_funcionamento) &
                            (machine_hours['ano'] == year_funcionamento)]
        start_bd = row['dt_inicio'].to_list()[0]
        end_bd = row['dt_fim'].to_list()[0]

        start_key = f"{day}_start"
        end_key = f"{day}_end"

        if start_key not in st.session_state:
            st.session_state[start_key] = start_bd
        if end_key not in st.session_state:
            st.session_state[end_key] = end_bd

        with cols[weekday_loop]:
            st.write(day)
            st.time_input("De:", key=start_key)
            st.time_input("Até:", key=end_key)

        if weekday_loop == 6:
            st.divider()

    submit_calendar = st.form_submit_button("Processa mudanças")

if submit_calendar:
    updates = 0
    for day in range(1, get_last_day_month(first_month_day) + 1):
        row = machine_hours[(machine_hours['dia'] == day) &
                            (machine_hours['mes'] == month_funcionamento) &
                            (machine_hours['ano'] == year_funcionamento)]
        start_bd = row['dt_inicio'].to_list()[0]
        end_bd = row['dt_fim'].to_list()[0]

        start_key = f"{day}_start"
        end_key = f"{day}_end"

        if (to_time(st.session_state[start_key]) != to_time(start_bd) or to_time(st.session_state[end_key]) != to_time(end_bd)):
            post_working_hours(
                datetime(year_funcionamento, month_funcionamento, day),
                machine_id,
                datetime(year_funcionamento, month_funcionamento, day,
                         st.session_state[start_key].hour, st.session_state[start_key].minute),
                datetime(year_funcionamento, month_funcionamento, day,
                         st.session_state[end_key].hour, st.session_state[end_key].minute),
            )
            updates += 1

    if updates:
        st.success(f"Atualizado horas ({updates} dia(s)).")
    else:
        st.info("Nenhuma alteração para salvar.")
