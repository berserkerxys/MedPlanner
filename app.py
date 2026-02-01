import streamlit as st
import pandas as pd
import time
from datetime import datetime
from sidebar_v2 import render_sidebar
from database import get_resumo, salvar_resumo, verificar_login, criar_usuario

st.set_page_config(page_title="MedPlanner Elite", page_icon="🩺", layout="wide")

# CSS para Nav Superior
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .stTabs [data-baseweb="tab-list"] { justify-content: center; gap: 20px; border-bottom: 2px solid #f0f2f6; }
    .stTabs [data-baseweb="tab"] { font-size: 16px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

if 'logado' not in st.session_state: st.session_state.logado = False
if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0

def app_principal():
    u = st.session_state.username
    render_sidebar()
    
    st.markdown("<h2 style='text-align:center;'>🩺 MEDPLANNER PRO</h2>", unsafe_allow_html=True)
    
    # Pomodoro Topo
    with st.expander("⏲️ Foco Pomodoro", expanded=False):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            mode = st.radio("Modo:", ["Estudo (25m)", "Pausa (5m)"], horizontal=True)
            if st.button("🚀 Iniciar", use_container_width=True):
                s = 25*60 if "Estudo" in mode else 5*60
                ph = st.empty()
                while s > 0:
                    m, sec = divmod(s, 60)
                    ph.markdown(f"<h1 style='text-align:center;'>{m:02d}:{sec:02d}</h1>", unsafe_allow_html=True)
                    time.sleep(1); s -= 1
                st.balloons()

    # ABAS PRINCIPAIS
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 PERFORMANCE", "📅 AGENDA", "📚 VIDEOTECA", "📝 RESUMOS", "👤 PERFIL"])
    
    with tab1:
        from dashboard import render_dashboard
        render_dashboard(None)
    with tab2:
        from agenda import render_agenda
        render_agenda(None)
    with tab3:
        from videoteca import render_videoteca
        render_videoteca(None)
    with tab4:
        render_resumos_ui(u)
    with tab5:
        render_perfil_aluno()

def render_resumos_ui(u):
    st.header("📝 Meus Resumos")
    areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
    for area in areas:
        with st.expander(f"📘 {area}", expanded=False):
            txt = st.text_area(f"Notas de {area}:", value=get_resumo(u, area), height=300, key=f"t_{area}")
            if st.button(f"Salvar {area}", key=f"s_{area}"):
                if salvar_resumo(u, area, txt): st.toast("Salvo!")

def render_perfil_aluno():
    from database import get_status_gamer
    status, _ = get_status_gamer(st.session_state.username, st.session_state.data_nonce)
    st.header("👤 Perfil do Aluno")
    if status:
        st.write(f"**Nível:** {status['nivel']} - {status['titulo']}")
        st.write(f"**XP Total:** {status['xp_total']}")
        st.progress(status['xp_atual']/1000)

def tela_login():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.title("🩺 Login")
        t1, t2 = st.tabs(["Entrar", "Criar Conta"])
        with t1:
            with st.form("l"):
                u = st.text_input("User"); p = st.text_input("Senha", type="password")
                if st.form_submit_button("Entrar", use_container_width=True, type="primary"):
                    ok, res = verificar_login(u, p)
                    if ok:
                        st.session_state.logado, st.session_state.username, st.session_state.u_nome = True, u, res
                        st.rerun()
                    else: st.error("Erro")
        with t2:
            with st.form("r"):
                nu = st.text_input("User"); nn = st.text_input("Nome"); np = st.text_input("Senha", type="password")
                if st.form_submit_button("Criar", use_container_width=True):
                    ok, m = criar_usuario(nu, np, nn)
                    st.success(m) if ok else st.error(m)

if st.session_state.logado: app_principal()
else: tela_login()