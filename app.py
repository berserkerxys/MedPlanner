import streamlit as st
import pandas as pd
import time
from datetime import datetime
from database import (
    verificar_login, criar_usuario, registrar_estudo, 
    registrar_simulado, get_progresso_hoje, get_lista_assuntos_nativa
)

st.set_page_config(page_title="MedPlanner Pro", page_icon="🩺", layout="wide")

# CSS Elite
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .main-header { font-size: 2.2rem; font-weight: 800; color: #1e293b; margin-bottom: 0.5rem; }
    .pomodoro-box { background: #fdf2f2; border: 1px solid #fee2e2; border-radius: 12px; padding: 1rem; text-align: center; }
</style>
""", unsafe_allow_html=True)

if 'logado' not in st.session_state: st.session_state.logado = False
if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0

def tela_login():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h1 style='text-align:center;'>🩺 MedPlanner</h1>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["Entrar", "Criar Conta"])
        with t1:
            with st.form("login_form"):
                u = st.text_input("Usuário")
                p = st.text_input("Senha", type="password")
                if st.form_submit_button("Aceder", type="primary", use_container_width=True):
                    ok, res = verificar_login(u, p)
                    if ok:
                        st.session_state.logado, st.session_state.username, st.session_state.u_nome = True, u, res
                        st.rerun()
                    else: st.error(res)
        with t2:
            with st.form("reg_form"):
                nu, nn, np = st.text_input("ID"), st.text_input("Nome"), st.text_input("Senha", type="password")
                if st.form_submit_button("Registar", use_container_width=True):
                    ok, m = criar_usuario(nu, np, nn)
                    st.success(m) if ok else st.error(m)

def app_principal():
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    # --- TOPO: CABEÇALHO E POMODORO ---
    st.markdown(f"<div class='main-header'>Bem-vindo, Dr. {st.session_state.u_nome}</div>", unsafe_allow_html=True)
    
    with st.expander("⏲️ Ferramenta Pomodoro (Foco)", expanded=False):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.markdown("<div class='pomodoro-box'>", unsafe_allow_html=True)
            mode = st.radio("Sessão:", ["Estudo (25m)", "Pausa (5m)"], horizontal=True, label_visibility="collapsed")
            placeholder = st.empty()
            if st.button("🚀 Iniciar Ciclo", use_container_width=True):
                secs = 25*60 if "Estudo" in mode else 5*60
                while secs > 0:
                    mm, ss = divmod(secs, 60)
                    placeholder.markdown(f"## ⏳ {mm:02d}:{ss:02d}")
                    time.sleep(1)
                    secs -= 1
                st.balloons()
            else: placeholder.markdown(f"## ⏳ {'25:00' if 'Estudo' in mode else '05:00'}")
            st.markdown("</div>", unsafe_allow_html=True)

    # --- SIDEBAR: NAVEGAÇÃO E REGISTOS ---
    with st.sidebar:
        st.markdown("### 🧭 Menu Principal")
        menu = st.radio("Selecione:", ["📊 Performance", "📅 Agenda SRS", "📚 Videoteca", "👤 Meu Perfil"], label_visibility="collapsed")
        
        st.divider()
        st.subheader("📝 Registar Estudo")
        tipo = st.selectbox("Tipo:", ["Por Tema", "Simulado Completo"])
        
        if tipo == "Por Tema":
            t = st.selectbox("Assunto:", get_lista_assuntos_nativa())
            acc = st.number_input("Acertos", 0, 100, 8)
            tot = st.number_input("Total", 1, 100, 10)
            if st.button("💾 Salvar", use_container_width=True, type="primary"):
                st.toast(registrar_estudo(u, t, acc, tot))
        else:
            areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
            res_sim = {}
            for a in areas: res_sim[a] = {"total": 20, "acertos": st.number_input(f"{a} (Ac)", 0, 20, 15)}
            if st.button("💾 Salvar Simulado", use_container_width=True, type="primary"):
                st.toast(registrar_simulado(u, res_sim))

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logado = False
            st.rerun()

    # --- CONTEÚDO DINÂMICO ---
    if menu == "📊 Performance":
        from dashboard import render_dashboard
        render_dashboard(None)
    elif menu == "📅 Agenda SRS":
        from agenda import render_agenda
        render_agenda(None)
    elif menu == "📚 Videoteca":
        from videoteca import render_videoteca
        render_videoteca(None)
    elif menu == "👤 Meu Perfil":
        render_perfil()

def render_perfil():
    from database import get_status_gamer
    status, _ = get_status_gamer(st.session_state.username, st.session_state.data_nonce)
    st.header("👤 Perfil do Aluno")
    if status:
        c1, c2 = st.columns([1, 2])
        c1.markdown("<h1 style='font-size: 100px; text-align: center;'>👨‍⚕️</h1>", unsafe_allow_html=True)
        with c2:
            st.subheader(st.session_state.u_nome)
            st.markdown(f"**Título:** {status['titulo']}")
            st.markdown(f"**Nível:** {status['nivel']}")
            st.markdown(f"**XP Acumulado:** {status['xp_total']} pts")
            st.progress(status['xp_atual']/1000, text="Próximo Nível")

if st.session_state.logado: app_principal()
else: tela_login()