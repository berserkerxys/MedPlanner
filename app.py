import streamlit as st
import pandas as pd
import time
from datetime import datetime
from database import (
    verificar_login, criar_usuario, registrar_estudo, 
    registrar_simulado, get_lista_assuntos_nativa
)

st.set_page_config(page_title="MedPlanner Pro", page_icon="🩺", layout="wide")

# CSS Profissional
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .stProgress > div > div > div > div { background-color: #3b82f6; }
    .pomodoro-box { 
        background-color: #fef2f2; 
        border: 1px solid #fee2e2; 
        padding: 15px; 
        border-radius: 12px; 
        text-align: center;
        margin-bottom: 20px;
    }
    .main-title { font-weight: 800; color: #1e293b; }
</style>
""", unsafe_allow_html=True)

if 'logado' not in st.session_state: st.session_state.logado = False
if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0

def tela_login():
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown("<h1 style='text-align:center;'>🩺 MedPlanner</h1>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["Acesso", "Cadastro"])
        with t1:
            with st.form("login"):
                u = st.text_input("Usuário")
                p = st.text_input("Senha", type="password")
                if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                    ok, res = verificar_login(u, p)
                    if ok:
                        st.session_state.logado, st.session_state.username, st.session_state.u_nome = True, u, res
                        st.rerun()
                    else: st.error(res)
        with t2:
            with st.form("reg"):
                nu, nn, np = st.text_input("ID"), st.text_input("Nome"), st.text_input("Senha", type="password")
                if st.form_submit_button("Criar Conta", use_container_width=True):
                    ok, m = criar_usuario(nu, np, nn)
                    st.success(m) if ok else st.error(m)

def app_principal():
    u = st.session_state.username
    
    # 1. HEADER & POMODORO (TOPO)
    st.markdown(f"<h2 class='main-title'>Bem-vindo, Dr. {st.session_state.u_nome}</h2>", unsafe_allow_html=True)
    
    with st.expander("⏲️ Ferramenta Pomodoro (Foco)", expanded=False):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.markdown("<div class='pomodoro-box'>", unsafe_allow_html=True)
            mode = st.radio("Modo:", ["Estudo (25m)", "Pausa (5m)"], horizontal=True, label_visibility="collapsed")
            placeholder = st.empty()
            btn_col = st.columns([1, 1])
            start = btn_col[0].button("Iniciar")
            stop = btn_col[1].button("Resetar")
            
            if start:
                secs = 25*60 if "Estudo" in mode else 5*60
                while secs > 0:
                    mm, ss = divmod(secs, 60)
                    placeholder.markdown(f"### ⏳ {mm:02d}:{ss:02d}")
                    time.sleep(1)
                    secs -= 1
                st.balloons()
            else:
                placeholder.markdown(f"### ⏳ {'25:00' if 'Estudo' in mode else '05:00'}")
            st.markdown("</div>", unsafe_allow_html=True)

    # 2. SIDEBAR NAVIGATION
    with st.sidebar:
        st.markdown("### 🧭 Navegação")
        menu = st.radio("Ir para:", ["📊 Performance", "📅 Minha Agenda", "📚 Videoteca", "👤 Perfil"], label_visibility="collapsed")
        st.divider()
        st.markdown("### 📝 Registrar")
        tipo = st.selectbox("O que estudou?", ["Aula por Tema", "Simulado Completo", "Banco de Questões"])
        
        if tipo == "Aula por Tema":
            t = st.selectbox("Assunto:", get_lista_assuntos_nativa())
            acc = st.number_input("Acertos", 0, 100, 8)
            tot = st.number_input("Total", 1, 100, 10)
            if st.button("Salvar Estudo", use_container_width=True, type="primary"):
                st.toast(registrar_estudo(u, t, acc, tot))
        
        elif tipo == "Simulado Completo":
            st.caption("20q por área padrão")
            areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
            res_sim = {}
            for a in areas:
                res_sim[a] = {"total": 20, "acertos": st.number_input(f"Acertos {a}", 0, 20, 15)}
            if st.button("Salvar Simulado", use_container_width=True, type="primary"):
                st.toast(registrar_simulado(u, res_sim))

        st.divider()
        if st.button("Sair"):
            st.session_state.logado = False
            st.rerun()

    # 3. CONTEÚDO
    if menu == "📊 Performance":
        from dashboard import render_dashboard
        render_dashboard(None)
    elif menu == "📅 Minha Agenda":
        from agenda import render_agenda
        render_agenda(None)
    elif menu == "📚 Videoteca":
        from videoteca import render_videoteca
        render_videoteca(None)
    elif menu == "👤 Perfil":
        render_perfil()

def render_perfil():
    st.header("👤 Perfil do Usuário")
    from database import get_status_gamer
    status, _ = get_status_gamer(st.session_state.username, st.session_state.data_nonce)
    if status:
        c1, c2 = st.columns([1, 3])
        with c1: st.image("https://cdn-icons-png.flaticon.com/512/3774/3774299.png", width=150)
        with c2:
            st.subheader(st.session_state.u_nome)
            st.write(f"**Título:** {status['titulo']}")
            st.write(f"**Nível:** {status['nivel']}")
            st.write(f"**XP Total:** {status['xp_total']} pontos")
            st.progress(status['xp_atual']/1000, text="Progresso do Nível")

if st.session_state.logado: app_principal()
else: tela_login()