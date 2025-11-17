import streamlit as st

# Título da página
st.title("Exemplo Simples de Tela com Streamlit")

# Texto introdutório
st.write("Bem-vindo! Esta é uma tela simples criada com Streamlit.")

# Input de texto
nome = st.text_input("Digite seu nome:")

# Slider
idade = st.slider("Selecione sua idade:", 0, 100, 25)

# Botão
if st.button("Enviar"):
    st.success(f"Olá, {nome}! Você tem {idade} anos.")

# Checkbox
mostrar_info = st.checkbox("Mostrar informações extras")

if mostrar_info:
    st.info("Streamlit é uma biblioteca Python para criar interfaces web de forma simples e rápida.")