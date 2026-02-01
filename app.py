import streamlit as st
import pandas as pd
import time
from datetime import datetime
from database import (
    verificar_login, criar_usuario, registrar_estudo, 
    registrar_simulado, get_progresso_hoje, get_lista_assuntos_nativa,
    update_perfil_nome
)

st.set_page_config(page_title="MedPlanner Pro", page_icon="🩺", layout="wide")

# Custom CSS para navegação e UI moderna
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .stButton button { border-radius: 8px; }
    .nav-card { background: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 10px; }
    .pomodoro-container { text-align: center; background: #fee2e2; padding: 20px; border-radius: 15px; border: 2px solid #ef4444; }
</style>
""", unsafe_allow_html=True)

# Estados Globais
if 'logado' not in st.session_state: st.session_state.logado = False
if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0
if 'pomodoro_active' not in st.session_state: st.session_state.pomodoro_active = False

def tela_login():
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<h1 style='text-align: center;'>🩺 MedPlanner Pro</h1>", unsafe_allow_html=True)
        tab_log, tab_reg = st.tabs(["Acesso", "Novo Cadastro"])
        with tab_log:
            with st.form("login"):
                u = st.text_input("Usuário", key="u_login")
                p = st.text_input("Senha", type="password", key="p_login")
                if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                    ok, res = verificar_login(u, p)
                    if ok:
                        st.session_state.logado = True
                        st.session_state.username = u
                        st.session_state.u_nome = res
                        st.rerun()
                    else: st.error(res)
        with tab_reg:
            with st.form("registro"):
                nu = st.text_input("ID Usuário"); nn = st.text_input("Seu Nome"); np = st.text_input("Senha", type="password")
                if st.form_submit_button("Criar Conta Gratuitamente", use_container_width=True):
                    ok, m = criar_usuario(nu, np, nn)
                    st.success(m) if ok else st.error(m)

def app_principal():
    u = st.session_state.username
    nonce = st.session_state.data_nonce

    # --- BARRA LATERAL (SIDEBAR) MELHORADA ---
    with st.sidebar:
        st.markdown(f"### 🩺 {st.session_state.u_nome}")
        st.caption(f"ID: {u}")
        q_hoje = get_progresso_hoje(u, nonce)
        st.metric("Questões Hoje", q_hoje, delta=f"{q_hoje-20 if q_hoje > 20 else 0} meta")
        
        st.divider()
        menu = st.radio("Navegação", 
            ["📊 Dashboard", "📅 Agenda SRS", "📚 Videoteca", "⏲️ Pomodoro", "👤 Meu Perfil"],
            label_visibility="collapsed")
        
        st.divider()
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.logado = False
            st.rerun()

    # --- ROTEAMENTO DE PÁGINAS ---
    if menu == "📊 Dashboard":
        from dashboard import render_dashboard
        render_dashboard(None)
    
    elif menu == "📅 Agenda SRS":
        from agenda import render_agenda
        render_agenda(None)
        
    elif menu == "📚 Videoteca":
        from videoteca import render_videoteca
        render_videoteca(None)

    elif menu == "⏲️ Pomodoro":
        render_pomodoro()

    elif menu == "👤 Meu Perfil":
        render_perfil()

def render_pomodoro():
    st.header("⏲️ Contador Pomodoro")
    st.info("O método Pomodoro ajuda a manter o foco total por 25 minutos com pausas curtas.")
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        container = st.container(border=True)
        placeholder = container.empty()
        
        type_p = st.radio("Ciclo:", ["Estudo (25min)", "Pausa Curta (5min)"], horizontal=True)
        duration = 25 * 60 if "Estudo" in type_p else 5 * 60
        
        if st.button("🚀 Iniciar Cronômetro", use_container_width=True):
            for t in range(duration, -1, -1):
                mins, secs = divmod(t, 60)
                placeholder.markdown(f"<h1 style='text-align: center; font-size: 80px;'>{mins:02d}:{secs:02d}</h1>", unsafe_allow_html=True)
                time.sleep(1)
            st.balloons()
            st.success("Ciclo concluído! Hora de uma pausa ou voltar aos estudos.")

def render_perfil():
    st.header("👤 Perfil do Aluno")
    u = st.session_state.username
    
    with st.container(border=True):
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("<div style='font-size: 100px;'>👨‍⚕️</div>", unsafe_allow_html=True)
        with col2:
            st.subheader(st.session_state.u_nome)
            st.write(f"**Nome de Usuário:** {u}")
            
            with st.expander("Editar Dados"):
                novo_n = st.text_input("Mudar Nome Exibido", value=st.session_state.u_nome)
                if st.button("Atualizar Perfil"):
                    if update_perfil_nome(u, novo_n):
                        st.session_state.u_nome = novo_n
                        st.success("Nome atualizado!")
                        st.rerun()

if st.session_state.logado: app_principal()
else: tela_login()