import streamlit as st
from pages._mock_db import authenticate_user

st.set_page_config(
    page_title="Portal de Controle",
    layout="wide"
)

ROLE_HOME = {
    "gerente": "pages/01_Visao_Geral_Chao_de_Fabrica.py",
    "controlador": "pages/01_Visao_Geral_Chao_de_Fabrica.py",
    "visualizador": "pages/01_Visao_Geral_Chao_de_Fabrica.py"
}

left, center, right = st.columns([1, 2, 1])

with center:
    st.markdown(
        """
        <div style="text-align:center; margin-bottom: 18px;">
          <div style="
              display: inline-flex;
              align-items: center;
              gap: 8px;
              padding: 6px 12px;
              border-radius: 999px;
              border: 1px solid #E5E7EB;
              background: #FFFFFF;
              font-size: 14px;
              color: #111827;
          ">
              <span style="
                  display:inline-flex;
                  width:24px;
                  height:24px;
                  border-radius: 8px;
                  background:#E8F1FF;
                  align-items:center;
                  justify-content:center;
                  font-weight:700;
                  color:#1D4ED8;
              ">◻</span>
              Sistema PCP Integrado
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Título
    st.markdown(
        "<h1 style='text-align:center; margin: 0;'>Bem-vindo ao Portal de Controle</h1>",
        unsafe_allow_html=True
    )

    # Subtítulo
    st.markdown(
        "<p style='text-align:center; color:#6B7280; margin-top: 6px;'>Selecione o seu perfil de acesso para entrar no sistema. Cada módulo é otimizado para suas funções específicas na fábrica.</p>",
        unsafe_allow_html=True
    )

st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

st.markdown("""
<style>
.role-card{
  border:1px solid #D1D5DB;
  border-radius:14px;
  padding:22px;
  background:#FFFFFF;
  box-shadow:0 1px 2px rgba(0,0,0,0.04);
  transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}

.role-card:hover{
  transform: translateY(-6px);
  box-shadow:0 10px 20px rgba(0,0,0,0.10);
  border-color:#0B5ED7;
}

.role-icon{
  width:54px;
  height:54px;
  border-radius:999px;

  /* estado normal: cinza claro + ícone escuro */
  background:#E5E7EB;
  color:#111827;

  display:flex;
  align-items:center;
  justify-content:center;

  margin:0 auto 14px auto;

  transition: background .18s ease, color .18s ease, transform .18s ease;
}

/* no hover do card: bolinha azul + ícone branco */
.role-card:hover .role-icon{
  background:#0B5ED7;
  color:#FFFFFF;
  transform: translateY(-1px);
}

/* SVG herda cor do container via currentColor */
.role-icon svg{
  width:22px;
  height:22px;
  display:block;
  stroke: currentColor;
}

.role-title{
  text-align:center;
  margin:0 0 8px 0;
}

.role-desc{
  text-align:center;
  color:#6B7280;
  margin:0 0 16px 0;
  font-size:14px;
}

.role-list{
  color:#374151;
  font-size:14px;
  line-height:1.8;
}

.role-btn{
  display:inline-block;
  padding:10px 16px;
  border-radius:10px;
  background:#E5E7EB;     /* cinza no estado normal */
  color:#111827;          /* texto preto */
  text-decoration:none;
  font-weight:600;
  font-size:14px;
  width:100%;
  box-sizing:border-box;
  transition: background .18s ease, color .18s ease;
}

/* Quando passar o mouse no CARD, o botão muda */
.role-card:hover .role-btn{
  background:#0B5ED7;
  color:#FFFFFF;
}

/* Opcional: cursor de clique no card todo */
.role-card{ cursor: pointer; }
</style>
""", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3, gap="large")

with c1:
    st.markdown("""
<div class="role-card">
  <div class="role-icon">
    <svg viewBox="0 0 24 24" fill="none" stroke-width="2">
      <rect x="3" y="4" width="18" height="12" rx="2"></rect>
      <path d="M8 20h8"></path>
      <path d="M12 16v4"></path>
    </svg>
  </div>
  <h3 class="role-title">Visualizador</h3>
  <p class="role-desc">Acesso destinado a monitores no chão de fábrica e áreas comuns. Focado em visualização rápida de status e metas.</p>
  <div class="role-list">
    <div>✓ Monitoramento em tempo real</div>
    <div>✓ Dashboard de TV (Modo Kiosk)</div>
    <div>✓ Sem permissão de edição</div>
  </div>
  <div style="height:16px;"></div>
  <div style="text-align:center;">
    <button class="role-btn">Acessar Painel →</button>
  </div>
</div>
""", unsafe_allow_html=True)

with c2:
    st.markdown("""
<div class="role-card">
  <div class="role-icon">
    <svg viewBox="0 0 24 24" fill="none" stroke-width="2">
      <path d="M4 7h16"></path>
      <path d="M4 17h16"></path>
      <circle cx="9" cy="7" r="2"></circle>
      <circle cx="15" cy="17" r="2"></circle>
    </svg>
  </div>
  <h3 class="role-title">Controlador</h3>
  <p class="role-desc">Perfil operacional para apontamento de produção, registro de paradas e acompanhamento básico do processo produtivo.</p>
  <div class="role-list">
    <div>✓ Apontamento de produção</div>
    <div>✓ Registro de paradas</div>
    <div>✓ Gestão de alertas básicos</div>
  </div>
  <div style="height:16px;"></div>
  <div style="text-align:center;">
    <button class="role-btn">Acessar Sistema →</button>
  </div>
</div>
""", unsafe_allow_html=True)

with c3:
    st.markdown("""
<div class="role-card">
  <div class="role-icon">
    <svg viewBox="0 0 24 24" fill="none" stroke-width="2">
      <path d="M12 2l7 4v6c0 5-3 9-7 10C8 21 5 17 5 12V6l7-4z"></path>
      <path d="M9 12l2 2 4-4"></path>
    </svg>
  </div>
  <h3 class="role-title">Gerente</h3>
  <p class="role-desc">Acesso gerencial com visão completa da operação, relatórios estratégicos e controle total dos parâmetros do sistema.</p>
  <div class="role-list">
    <div>✓ Relatórios gerenciais completos</div>
    <div>✓ Edição de parâmetros e metas</div>
    <div>✓ Controle total do sistema</div>
  </div>
  <div style="height:16px;"></div>
  <div style="text-align:center;">
  </div>
</div>
""", unsafe_allow_html=True)
    if st.button("Login Administrativo →", key="btn_gerente", use_container_width=True):
        st.session_state.desired_role = "gerente"
        st.session_state.show_login = True

def render_login_dialog():
    # só renderiza quando for pra abrir
    if not st.session_state.get("show_login", False):
        return

    desired_role = st.session_state.get("desired_role", None)
    if desired_role not in ("visualizador", "controlador", "gerente"):
        st.session_state.show_login = False
        st.error("Perfil de acesso inválido.")
        return

    def _form_body():
        st.caption(f"Entrar como **{desired_role}**")

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Usuário", key="login_username")
            password = st.text_input("Senha", type="password", key="login_password")

            c1, c2 = st.columns(2)
            submit = c1.form_submit_button("Entrar", use_container_width=True)
            cancel = c2.form_submit_button("Cancelar", use_container_width=True)

        if cancel:
            st.session_state.show_login = False
            return

        if submit:
            ok, msg, user = authenticate_user(username, password, desired_role)

            if not ok:
                st.error(msg)
                return

            st.session_state.auth_user = user
            st.session_state.is_authenticated = True
            st.session_state.auth_role = user["tx_role"]
            st.session_state.show_login = False
            st.success(msg)
            target = ROLE_HOME.get(desired_role)
            if target:
                st.switch_page(target)

    if hasattr(st, "dialog"):
        @st.dialog("Login")
        def _login_dialog():
            _form_body()

        _login_dialog()

    else:
        st.markdown(
            """
            <style>
              .login-fallback {
                max-width: 520px;
                margin: 0 auto;
                border: 1px solid #E5E7EB;
                border-radius: 16px;
                padding: 18px;
                background: #FFFFFF;
                box-shadow: 0 10px 24px rgba(0,0,0,0.12);
              }
            </style>
            """,
            unsafe_allow_html=True
        )
        st.markdown("<div class='login-fallback'>", unsafe_allow_html=True)
        _form_body()
        st.markdown("</div>", unsafe_allow_html=True)

        
render_login_dialog()