import logging
import streamlit as st
from services.modbus import get_registers_values, post_registers_values
from services.queries import get_active_machines, get_machine_hours
from services.utils import get_weekday_start

st.title("Settings")

machine = st.selectbox("Máquina", get_active_machines(1)
                       ['nome_maquina'].to_list())


# Operador -> Registrador
meta = st.number_input('Operador', min_value=0, step=1,
                       value=get_registers_values(machine, 0))

# Calendário funcionamento
st.write("Calendário Funcionamento")
col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
week = ['Segunda', 'Terça', 'Quarta',
        'Quinta', 'Sexta', 'Sábado', 'Domingo']
week_cols = [col1, col2, col3, col4, col5, col6, col7]
for k, col in enumerate(week_cols):
    with col:
        st.write(week[k])
weekday = get_weekday_start()
machine_hours = get_machine_hours({"MAQ1": 1, "MAQ2": 2}[machine])
for day in range(1, 32):
    weekday_loop = (weekday + day - 1) % 7
    if weekday_loop == 0:
        col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    week_cols = [col1, col2, col3, col4, col5, col6, col7]
    with week_cols[weekday_loop]:
        st.write(day)
        st.time_input(
            f'De:', key=f'{day}_start', value=machine_hours[machine_hours['dia'] == day]['horario_inicio'].to_list()[0])
        st.time_input(
            f'Até:', key=f'{day}_end', value=machine_hours[machine_hours['dia'] == day]['horario_fim'].to_list()[0])
    if weekday_loop == 6:
        st.divider()


# Botão
if st.button('Processa mudanças'):
    if post_registers_values(machine, 0, int(meta)):
        st.success('Funcionou')
    else:
        st.error('Não Funcionou')
