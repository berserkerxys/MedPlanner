import streamlit as st
import pandas as pd
import time
from datetime import datetime
from sidebar_v2 import render_sidebar
from database import get_resumo, salvar_resumo

st.set_page_config(page_title="MedPlanner Elite", page_icon="🩺", layout="wide")

# CSS Elite para Top Nav e Resumos
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .main-title { font-weight: 800; color: #1e293b; margin-bottom: 0px; text-align: center; }
    .stTabs [data-baseweb="tab-list"] { justify-content: center; gap: 30px; border-bottom: 1px solid #e2e8f0; padding-bottom: 10px; }
    .stTabs [data-baseweb="tab"] { font-weight: 600; font-size: 1.1rem; color: #64748b; }
    .stTabs [aria-selected="true"] { color: #1e293b !important; border-bottom: 3px solid #1e293b !important; }
</style>
""", unsafe_allow_html=True)

if 'logado' not in st.session_state: st.session_state.logado = False
if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0

def app_principal():
    u = st.session_state.username
    render_sidebar()
    
    # CABEÇALHO CENTRALIZADO
    st.markdown("<h1 class='main-title'>🩺 MEDPLANNER ELITE</h1>", unsafe_allow_html=True)
    
    # POMODORO NO TOPO
    with st.expander("⏲️ Ferramenta Pomodoro de Foco", expanded=False):
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

    # TOP NAV - SEÇÕES DO SITE
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
        render_resumos(u)
    with tab_perf_u:
        render_perfil_aluno()

def render_resumos(u):
    st.header("📝 Meus Resumos Estruturados")
    st.info("Anote os pontos chave de cada área. As notas são guardadas na nuvem por conta.")
    
    # Lista de Grandes Áreas
    areas = ["Cirurgia", "Clínica Médica", "Ginecologia e Obstetrícia", "Pediatria", "Preventiva"]
    
    for area in areas:
        with st.expander(f"📚 {area.upper()}", expanded=False):
            # Busca conteúdo
            current_text = get_resumo(u, area)
            
            # Área de digitação
            txt = st.text_area("Digite aqui as suas anotações:", value=current_text, height=300, key=f"txt_{area}")
            
            # Botão de Salvar individual
            if st.button(f"➕ Guardar Notas de {area}", key=f"save_{area}", type="primary", use_container_width=True):
                if salvar_resumo(u, area, txt):
                    st.toast(f"✅ Resumo de {area} atualizado!")
                else: st.error("Erro na ligação ao servidor.")

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
            st.markdown(f"**Meta Personalizada:** {status['meta_diaria']} questões/dia")
            st.markdown(f"**XP Acumulado:** {status['xp_total']} pontos")
            st.progress(status['xp_atual']/1000, text=f"Progresso: {status['xp_atual']}/1000 XP")

# TELA DE LOGIN
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
                    else: st.error("Credenciais inválidas.")
        with t2:
            with st.form("reg"):
                nu, nn, np = st.text_input("ID"), st.text_input("Nome"), st.text_input("Senha", type="password")
                if st.form_submit_button("Cadastrar", use_container_width=True):
                    ok, m = criar_usuario(nu, np, nn)
                    st.success(m) if ok else st.error(m)

if st.session_state.logado: app_principal()
else: tela_login()