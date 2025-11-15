import streamlit as st
from services.db import run_query
from urllib.parse import urlencode

st.set_page_config(page_title="Visão Geral MES", layout="wide")

st.title("🏭 Visão Geral da Produção")

# Paleta de cores para os status
STATUS_COLORS = {
    "máquina produzindo": "#96d779",
    "máquina em manutenção": "#f7c76c",
    "máquina sem produção": "#e57373",
    "desligada": "#3d3d3d",
    "sem status": "#3d3d3d",
}


def normalizar_status(status: str | None) -> str:
    if not status:
        return "sem status"
    return status.strip().lower()


# ============================
# Linhas de produção
# ============================
linhas = run_query("SELECT id, nome FROM linhas_producao ORDER BY id")

for linha in linhas:
    linha_id = linha["id"]
    linha_nome = linha["nome"]

    st.markdown(f"### {linha_nome} ↗")

    maquinas = run_query(
        "SELECT id, nome_maquina FROM ihms WHERE id_linha_producao = ? ORDER BY id",
        [linha_id],
    )

    if not maquinas:
        st.info("Nenhuma máquina cadastrada para esta linha.")
        st.markdown("---")
        continue

    # ============================
    # Monta o container horizontal com todos os cards
    # ============================
    cards_html = (
        '<div style="display:block; overflow-x:auto; white-space:nowrap; padding-bottom:10px;">'
    )

    for maq in maquinas:
        maq_id = maq["id"]
        nome_maquina = maq["nome_maquina"]

        status_query = run_query(
            """
            SELECT TOP 1 status_maquina
            FROM maqteste_status_geral
            WHERE id_ihm = ?
            ORDER BY datahora DESC
            """,
            [maq_id],
        )

        status = normalizar_status(
            status_query[0]["status_maquina"] if status_query else "sem status"
        )
        color = STATUS_COLORS.get(status, "#d9d9d9")

        params = urlencode({"maq": maq_id, "nome": nome_maquina})
        link = f"?{params}"

        # Repara que NÃO tem espaços antes de <a> nem de <div> na primeira coluna
        cards_html += f'''
<a href="{link}" style="text-decoration:none; display:inline-block; vertical-align:top; margin-right:15px;">
  <div style="
    width:230px;
    background-color:{color};
    padding:20px;
    border-radius:10px;
    text-align:center;
    cursor:pointer;
    box-sizing:border-box;
    transition:0.2s;
    white-space:normal;
  ">
    <b style="font-size:18px; color:white;">{nome_maquina}</b><br>
    <span style="font-size:14px; color:white;">{status.capitalize()}</span>
  </div>
</a>'''

    cards_html += "</div>"

    # Agora o HTML é interpretado corretamente
    st.markdown(cards_html, unsafe_allow_html=True)

    st.markdown("---")