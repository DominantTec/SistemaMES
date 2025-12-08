import logging
import streamlit as st
from services.modbus import get_registers_values, post_registers_values
from services.queries import get_active_machines

st.title("Settings")

logging.error(get_active_machines(1))

machine = st.selectbox("Máquina", get_active_machines(1)
                       ['nome_maquina'].to_list())


# Meta -> Registrador
# meta = st.text_area('Meta', value=get_registers_values(0))
meta = st.number_input('Meta', min_value=0, step=1,
                       value=get_registers_values(machine, 0))

# Operador -> FTP

# Botão
if st.button('Processa meta'):
    if post_registers_values(machine, 0, int(meta)):
        st.success('Funcionou')
    else:
        st.error('N Funcionou')
