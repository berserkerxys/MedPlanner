import streamlit as st
import pandas as pd
from datetime import datetime
from database import (
    verificar_login, criar_usuario, registrar_estudo, 
    registrar_simulado, get_progresso_hoje, get_db
)

st.set_page_config(page_title="MedPlanner Cloud", page_icon="☁️", layout="wide", initial_sidebar_state="collapsed")

# CSS e Estado
st.markdown("<style>[data-testid='stSidebarNav'] {display: none;} .stTabs [data-baseweb='tab-list'] {justify-content: center;}</style>", unsafe_allow_html=True)
if 'logado' not in st.session_state: st.session_state.logado = False

# Tela de Login
def tela_login():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title("🩺 MedPlanner Cloud")
        
        # Verifica conexão
        if not get_db():
            st.error("⚠️ Sem conexão com o Banco de Dados. Configure os Secrets.")
            with st.expander("Ajuda"):
                st.write("Adicione o arquivo 'firebase_key.json' na pasta ou configure st.secrets na nuvem.")
            return

        t1, t2 = st.tabs(["Entrar", "Criar Conta"])
        with t1:
            u = st.text_input("Usuário"); p = st.text_input("Senha", type="password")
            if st.button("Acessar", type="primary", use_container_width=True):
                ok, nome = verificar_login(u, p)
                if ok:
                    st.session_state.logado = True; st.session_state.username = u; st.session_state.u_nome = nome
                    st.rerun()
                else: st.error("Erro no login")
        with t2:
            nu = st.text_input("Novo Usuário"); nn = st.text_input("Nome"); np = st.text_input("Senha", type="password")
            if st.button("Registrar"):
                ok, msg = criar_usuario(nu, np, nn)
                st.success(msg) if ok else st.error(msg)

# App Principal
def app_principal():
    u = st.session_state.username
    
    with st.sidebar:
        st.title(f"Olá, {st.session_state.u_nome}")
        st.metric("Hoje", get_progresso_hoje(u))
        st.divider()
        
        st.subheader("📝 Registrar")
        modo = st.radio("Modo", ["Por Tema", "Simulado", "Banco Geral"])
        dt = st.date_input("Data", datetime.now())
        
        if modo == "Por Tema":
            # Busca lista de assuntos (Agora via Firebase)
            db = get_db()
            docs = db.collection('assuntos').stream()
            lista_aulas = sorted([d.to_dict()['nome'] for d in docs])
            
            esc = st.selectbox("Aula:", lista_aulas)
            c1, c2 = st.columns(2)
            tot = c1.number_input("Total", 1, 100, 10)
            ac = c2.number_input("Acertos", 0, tot, 8)
            if st.button("Salvar", type="primary"):
                st.toast(registrar_estudo(u, esc, ac, tot, dt))
        
        # (Outros modos seguem a mesma lógica...)
        
        st.divider()
        if st.button("Sair"): st.session_state.logado = False; st.rerun()

    # Abas
    t1, t2, t3 = st.tabs(["DASHBOARD", "AGENDA", "VIDEOTECA"])
    
    with t1:
        from dashboard import render_dashboard
        render_dashboard(None) # Não precisa mais passar conn
    
    with t2:
        from agenda import render_agenda
        render_agenda(None)

    with t3:
        from videoteca import render_videoteca
        render_videoteca(None)

if st.session_state.logado: app_principal()
else: tela_login()