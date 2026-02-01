import streamlit as st
import pandas as pd
import time
from datetime import datetime
from sidebar_v2 import render_sidebar
from database import get_resumo, salvar_resumo

st.set_page_config(page_title="MedPlanner Elite", page_icon="🩺", layout="wide")

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
    render_sidebar()
    
    st.markdown("<h1 class='main-title'>🩺 MEDPLANNER ELITE</h1>", unsafe_allow_html=True)
    
    with st.expander("⏲️ Ferramenta Pomodoro", expanded=False):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            mode = st.radio("Ciclo:", ["Estudo (25m)", "Pausa (5m)"], horizontal=True, label_visibility="collapsed")
            placeholder = st.empty()
            if st.button("🚀 Iniciar Ciclo", use_container_width=True):
                secs = 25*60 if "Estudo" in mode else 5*60
                while secs > 0:
                    mm, ss = divmod(secs, 60)
                    placeholder.markdown(f"<h2 style='text-align:center;'>⏳ {mm:02d}:{ss:02d}</h2>", unsafe_allow_html=True)
                    time.sleep(1); secs -= 1
                st.balloons()
            else: placeholder.markdown(f"<h2 style='text-align:center;'>⏳ {'25:00' if 'Estudo' in mode else '05:00'}</h2>", unsafe_allow_html=True)

    # TOP NAV
    tab_perf, tab_agen, tab_vide, tab_resu, tab_perf_u = st.tabs([
        "📊 PERFORMANCE", "📅 AGENDA SRS", "📚 VIDEOTECA", "📝 MEUS RESUMOS", "👤 PERFIL"
    ])
    
    with tab_perf:
        from dashboard import render_dashboard
        render_dashboard(None)
    with tab_agen:
        from agenda import render_agenda
        render_agenda(None)
    with tab_vide:
        from videoteca import render_videoteca
        render_videoteca(None)
    with tab_resu:
        render_resumos_ui(u)
    with tab_perf_u:
        render_perfil_aluno()

def render_resumos_ui(u):
    st.header("📝 Meus Resumos Estruturados")
    areas = ["Cirurgia", "Clínica Médica", "Ginecologia e Obstetrícia", "Pediatria", "Preventiva"]
    for area in areas:
        with st.expander(f"📚 {area.upper()}", expanded=False):
            txt_db = get_resumo(u, area)
            texto = st.text_area("Notas:", value=txt_db, height=300, key=f"txt_{area}")
            if st.button(f"➕ Guardar Notas de {area}", key=f"save_{area}", type="primary", use_container_width=True):
                if salvar_resumo(u, area, texto):
                    st.toast(f"Notas de {area} guardadas!")
                else: st.error("Erro.")

def render_perfil_aluno():
    from database import get_status_gamer
    status, _ = get_status_gamer(st.session_state.username, st.session_state.data_nonce)
    if status:
        c1, c2 = st.columns([1, 2])
        c1.markdown("<h1 style='font-size: 150px; text-align: center;'>👨‍⚕️</h1>", unsafe_allow_html=True)
        with c2:
            st.subheader(st.session_state.u_nome)
            st.markdown(f"**Título:** {status['titulo']}")
            st.markdown(f"**Nível:** {status['nivel']}")
            st.markdown(f"**Meta Diária:** {status['meta_diaria']} q/dia")
            st.markdown(f"**XP Total:** {status['xp_total']} pts")

# LOGIN
def tela_login():
    from database import verificar_login, criar_usuario
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
                        st.session_state.logado, st.session_state.username, st.session_state.u_nome = True, u, res
                        st.rerun()
                    else: st.error("Inválido.")
        with t2:
            with st.form("reg"):
                nu, nn, np = st.text_input("ID"), st.text_input("Nome"), st.text_input("Senha", type="password")
                if st.form_submit_button("Cadastrar", use_container_width=True):
                    ok, m = criar_usuario(nu, np, nn)
                    st.success(m) if ok else st.error(m)

if st.session_state.logado: app_principal()
else: tela_login()