# Arquivo app.py (modificado para adicionar a aba "🗂️ CRONOGRAMA")
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
    u = st.session_state.username if 'username' in st.session_state else None
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

    # ABAS PRINCIPAIS (adicionada a aba Cronograma)
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 PERFORMANCE", "📅 AGENDA", "📚 VIDEOTECA", "📝 RESUMOS", "👤 PERFIL", "🗂️ CRONOGRAMA"])
    
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
    with tab6:
        from cronograma import render_cronograma
        render_cronograma(None)

def render_resumos_ui(u):
    st.header("📝 Meus Resumos")
    areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
    for area in areas:
        with st.expander(f"📘 {area}", expanded=False):
            txt = st.text_area(f"Notas de {area}:", value=get_resumo(u, area), height=300, key=f"t_{area}")
            if st.button(f"Salvar {area}", key=f"s_{area}"):
                if salvar_resumo(u, area, txt): st.toast("Salvo!")

def render_perfil_aluno():
    # Placeholder (mantém compatibilidade com o restante do app)
    st.header("👤 Perfil")
    st.write("Informações do perfil e gamificação aparecem aqui.")