import logging
import streamlit as st
from services.modbus import get_registers_values, post_registers_values
from services.queries import get_active_machines, get_machine_hours
from services.utils import get_weekday_start, get_last_day_month, fill_month_database
from datetime import datetime

st.title("Settings")

machine = st.selectbox("Máquina", get_active_machines(1)
                       ['nome_maquina'].to_list())


# Operador -> Registrador
meta = st.number_input('Operador', min_value=0, step=1,
                       value=get_registers_values(machine, 0))

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
col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
week = ['Segunda', 'Terça', 'Quarta',
        'Quinta', 'Sexta', 'Sábado', 'Domingo']
week_cols = [col1, col2, col3, col4, col5, col6, col7]
for k, col in enumerate(week_cols):
    with col:
        st.write(week[k])
weekday = get_weekday_start(
    datetime(year_funcionamento, month_funcionamento, 1))
machine_hours = get_machine_hours({"MAQ1": 1, "MAQ2": 2}[machine])
first_month_day = datetime(year_funcionamento, month_funcionamento, 1)
if len(machine_hours[(machine_hours['dia'] == first_month_day.day) & (machine_hours['mes'] == first_month_day.month) & (machine_hours['ano'] == first_month_day.year)]) == 0:
    fill_month_database(first_month_day)
    machine_hours = get_machine_hours({"MAQ1": 1, "MAQ2": 2}[machine])
for day in range(1, get_last_day_month(first_month_day) + 1):
    weekday_loop = (weekday + day - 1) % 7
    if weekday_loop == 0:
        col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    week_cols = [col1, col2, col3, col4, col5, col6, col7]
    with week_cols[weekday_loop]:
        st.write(day)
        st.session_state[f'{day}_start'] = machine_hours[(machine_hours['dia'] == day) & (
            machine_hours['mes'] == month_funcionamento) & (machine_hours['ano'] == year_funcionamento)]['horario_inicio'].to_list()[0]
        st.time_input(
            f'De:', key=f'{day}_start')
        st.session_state[f'{day}_end'] = machine_hours[(machine_hours['dia'] == day) & (
            machine_hours['mes'] == month_funcionamento) & (machine_hours['ano'] == year_funcionamento)]['horario_fim'].to_list()[0]
        st.time_input(
            f'Até:', key=f'{day}_end')
    if weekday_loop == 6:
        st.divider()


# Botão
if st.button('Processa mudanças'):
    if post_registers_values(machine, 0, int(meta)):
        st.success('Funcionou')
    else:
        st.error('Não Funcionou')
