import streamlit as st
import pandas as pd
import time
from datetime import datetime
from sidebar_v2 import render_sidebar
from database import verificar_login, criar_usuario

st.set_page_config(page_title="MedPlanner Pro", page_icon="🩺", layout="wide")

st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .main-title { font-weight: 800; color: #1e293b; text-align: center; margin-bottom: 20px; }
    .stTabs [data-baseweb="tab-list"] { justify-content: center; gap: 30px; border-bottom: 1px solid #e2e8f0; }
</style>
""", unsafe_allow_html=True)

if 'logado' not in st.session_state: st.session_state.logado = False
if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0

def app_principal():
    u = st.session_state.username
    menu = render_sidebar()
    
    st.markdown("<h1 class='main-title'>🩺 MEDPLANNER PRO</h1>", unsafe_allow_html=True)
    
    # Navegação baseada na Sidebar
    if menu == "📊 Performance":
        from dashboard import render_dashboard
        render_dashboard(None)
    elif menu == "📅 Agenda SRS":
        from agenda import render_agenda
        render_agenda(None)
    elif menu == "📚 Videoteca":
        from videoteca import render_videoteca
        render_videoteca(None)
    elif menu == "📝 Resumos":
        render_resumos_ui(u)
    elif menu == "👤 Perfil":
        render_perfil_aluno()

def render_resumos_ui(u):
    from database import get_resumo, salvar_resumo
    st.header("📝 Meus Resumos")
    areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
    for area in areas:
        with st.expander(f"📚 {area}", expanded=False):
            txt = st.text_area(f"Notas de {area}:", value=get_resumo(u, area), height=300, key=f"t_{area}")
            if st.button(f"Guardar {area}", key=f"s_{area}"):
                if salvar_resumo(u, area, txt): st.toast("Salvo!")

def render_perfil_aluno():
    from database import get_status_gamer
    status, _ = get_status_gamer(st.session_state.username, st.session_state.data_nonce)
    st.header("👤 Perfil")
    if status:
        st.write(f"**Nível:** {status['nivel']} - {status['titulo']}")
        st.progress(status['xp_atual']/1000)

def tela_login():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h1 style='text-align:center;'>🩺 MedPlanner</h1>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["Entrar", "Criar Conta"])
        with t1:
            with st.form("login"):
                u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
                if st.form_submit_button("Aceder", type="primary", use_container_width=True):
                    ok, res = verificar_login(u, p)
                    if ok:
                        st.session_state.logado = True; st.session_state.username = u; st.session_state.u_nome = res
                        st.rerun()
                    else: st.error("Inválido.")
        with t2:
            with st.form("reg"):
                nu = st.text_input("ID"); nn = st.text_input("Nome"); np = st.text_input("Senha", type="password")
                if st.form_submit_button("Cadastrar"):
                    ok, m = criar_usuario(nu, np, nn)
                    st.success(m) if ok else st.error(m)

if st.session_state.logado:
    app_principal()
else:
    tela_login()