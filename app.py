import streamlit as st
import pandas as pd
from datetime import datetime
from database import (
    verificar_login, criar_usuario, get_connection, 
    registrar_estudo, registrar_simulado, get_progresso_hoje, get_db
)

st.set_page_config(page_title="MedPlanner Cloud", page_icon="☁️", layout="wide", initial_sidebar_state="expanded")

# CSS para esconder menu padrão e ajustar abas
st.markdown("""
    <style>
    [data-testid="stSidebarNav"] {display: none;}
    .stTabs [data-baseweb="tab-list"] {justify-content: center;}
    </style>
""", unsafe_allow_html=True)

if 'logado' not in st.session_state: st.session_state.logado = False

# --- TELA DE LOGIN ---
def tela_login():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title("🩺 MedPlanner Cloud")
        if not get_db(): st.error("⚠️ Erro de conexão Firebase."); return

        t1, t2 = st.tabs(["Entrar", "Criar Conta"])
        with t1:
            with st.form("login_form"):
                u = st.text_input("Usuário", key="u_log")
                p = st.text_input("Senha", type="password", key="p_log")
                if st.form_submit_button("Acessar", type="primary", use_container_width=True):
                    ok, nome = verificar_login(u, p)
                    if ok:
                        st.session_state.logado = True; st.session_state.username = u; st.session_state.u_nome = nome
                        st.rerun()
                    else: st.error("Dados incorretos")
        with t2:
            with st.form("reg_form"):
                nu = st.text_input("Novo Usuário", key="u_reg")
                nn = st.text_input("Seu Nome", key="n_reg")
                np = st.text_input("Senha", type="password", key="p_reg")
                if st.form_submit_button("Registrar", use_container_width=True):
                    ok, msg = criar_usuario(nu, np, nn)
                    st.success(msg) if ok else st.error(msg)

# --- APP PRINCIPAL ---
def app_principal():
    u = st.session_state.username
    db = get_db()
    
    with st.sidebar:
        st.title(f"Olá, {st.session_state.u_nome}")
        st.metric("Hoje", get_progresso_hoje(u))
        st.divider()
        
        st.subheader("📝 Registrar")
        modo = st.radio("Modo", ["Por Tema", "Simulado Geral", "Banco Geral"], key="radio_mode")
        dt = st.date_input("Data", datetime.now(), key="date_picker")
        
        # 1. ESTUDO POR TEMA (Com lista de assuntos)
        if modo == "Por Tema":
            # Busca assuntos do Firebase para o dropdown
            docs = db.collection('assuntos').stream()
            lista_aulas = sorted([d.to_dict()['nome'] for d in docs])
            
            esc = st.selectbox("Aula:", lista_aulas, index=None, placeholder="Selecione o tema...", key="sel_tema")
            
            c1, c2 = st.columns(2)
            tot = c1.number_input("Total", 1, 200, 10, key="tot_tema")
            ac = c2.number_input("Acertos", 0, tot, 8, key="ac_tema")
            
            if st.button("Salvar Aula", type="primary", key="btn_save_tema"):
                if esc: st.toast(registrar_estudo(u, esc, ac, tot, dt))
                else: st.warning("Escolha a aula!")

        # 2. SIMULADO (Por áreas)
        elif modo == "Simulado Geral":
            st.info("Lançamento por Grande Área")
            areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
            dados = {}
            
            with st.form("form_simulado"):
                for a in areas:
                    st.markdown(f"**{a}**")
                    c1, c2 = st.columns(2)
                    t = c1.number_input("Total", 0, 100, 20, key=f"t_{a}")
                    ac = c2.number_input("Acertos", 0, t, 15, key=f"ac_{a}")
                    dados[a] = {'total': t, 'acertos': ac}
                
                st.markdown("---")
                if st.form_submit_button("💾 Salvar Simulado Completo", type="primary"):
                    st.toast(registrar_simulado(u, dados, dt))

        # 3. BANCO GERAL
        elif modo == "Banco Geral":
            c1, c2 = st.columns(2)
            tot = c1.number_input("Total", 1, 500, 50, key="tot_bg")
            ac = c2.number_input("Acertos", 0, tot, 35, key="ac_bg")
            if st.button("Salvar Treino", type="primary", key="btn_bg"):
                st.toast(registrar_estudo(u, "Banco Geral - Livre", ac, tot, dt))

        st.divider()
        if st.button("Sair", key="logout"):
            st.session_state.clear(); st.rerun()

    # Abas
    t1, t2, t3 = st.tabs(["DASHBOARD", "AGENDA", "VIDEOTECA"])
    with t1:
        from dashboard import render_dashboard
        render_dashboard(None)
    with t2:
        from agenda import render_agenda
        render_agenda(None)
    with t3:
        from videoteca import render_videoteca
        render_videoteca(None)

if st.session_state.logado: app_principal()
else: tela_login()