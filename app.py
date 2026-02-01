import streamlit as st
import pandas as pd
from datetime import datetime
from database import (
    verificar_login, criar_usuario, get_connection, 
    registrar_estudo, registrar_simulado, get_progresso_hoje, get_db
)

st.set_page_config(page_title="MedPlanner Cloud", page_icon="☁️", layout="wide", initial_sidebar_state="collapsed")

# Estilos CSS
st.markdown("""
    <style>
    [data-testid="stSidebarNav"] {display: none;}
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        justify-content: center;
    }
    </style>
""", unsafe_allow_html=True)

if 'logado' not in st.session_state:
    st.session_state['logado'] = False

def tela_login():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title("🩺 MedPlanner Cloud")
        
        # Verifica conexão com o banco antes de mostrar login
        if not get_db():
            st.error("⚠️ Erro de conexão com o Firebase. Verifique os Secrets.")
            return

        t1, t2 = st.tabs(["Entrar", "Criar Conta"])
        
        # --- LOGIN ---
        with t1:
            with st.form("login_form"):
                # Adicionei keys únicas para evitar DuplicateElementId
                u = st.text_input("Usuário", key="login_username_input")
                p = st.text_input("Senha", type="password", key="login_password_input")
                
                if st.form_submit_button("Acessar", type="primary", use_container_width=True):
                    ok, nome = verificar_login(u, p)
                    if ok:
                        st.session_state.logado = True
                        st.session_state.username = u
                        st.session_state.u_nome = nome
                        st.rerun()
                    else:
                        st.error("Usuário ou senha incorretos")
        
        # --- REGISTRO ---
        with t2:
            with st.form("register_form"):
                # Keys únicas aqui também
                nu = st.text_input("Novo Usuário", key="reg_username_input")
                nn = st.text_input("Seu Nome", key="reg_name_input")
                np = st.text_input("Nova Senha", type="password", key="reg_password_input")
                
                if st.form_submit_button("Registrar Conta", use_container_width=True):
                    if nu and nn and np:
                        ok, msg = criar_usuario(nu, np, nn)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.warning("Preencha todos os campos.")

def app_principal():
    u = st.session_state.username
    
    with st.sidebar:
        st.title(f"Olá, {st.session_state.u_nome}")
        st.metric("Hoje", get_progresso_hoje(u))
        st.divider()
        
        st.subheader("📝 Registrar")
        modo = st.radio("Modo", ["Por Tema", "Simulado", "Banco Geral"], key="sidebar_mode_radio")
        dt = st.date_input("Data", datetime.now(), key="sidebar_date_input")
        
        # Lógica de Registro (adaptada para Firebase)
        # Nota: As listas de assuntos agora vêm do Firestore via funções do database.py
        # Para simplificar aqui, vamos assumir que o usuário digita ou que carregamos dinamicamente
        
        if modo == "Por Tema":
            # No Firebase, é melhor ter uma lista fixa ou caixa de texto se a lista for gigante
            # Aqui vamos usar um input de texto ou carregar se possível. 
            # Para evitar complexidade de query no app.py, vamos simplificar:
            assunto_input = st.text_input("Nome da Aula/Assunto", key="input_tema_study")
            
            c1, c2 = st.columns(2)
            tot = c1.number_input("Total", 1, 500, 10, key="input_tot_study")
            ac = c2.number_input("Acertos", 0, tot, 8, key="input_ac_study")
            
            if st.button("Salvar", type="primary", key="btn_save_study"):
                if assunto_input:
                    st.toast(registrar_estudo(u, assunto_input, ac, tot, dt))
                else:
                    st.warning("Digite o nome da aula.")
        
        elif modo == "Simulado":
            st.info("Simulado Geral (5 Áreas)")
            areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
            dados = {}
            for a in areas:
                ac = st.number_input(f"{a} (Acertos)", 0, 20, 15, key=f"sim_ac_{a}")
                dados[a] = {'acertos': ac, 'total': 20}
            
            if st.button("Salvar Simulado", type="primary", key="btn_save_sim"):
                st.toast(registrar_simulado(u, dados, dt))
        
        elif modo == "Banco Geral":
            c1, c2 = st.columns(2)
            tot = c1.number_input("Total", 1, 500, 50, key="bg_tot")
            ac = c2.number_input("Acertos", 0, tot, 35, key="bg_ac")
            
            if st.button("Salvar Banco", type="primary", key="btn_save_bg"):
                st.toast(registrar_estudo(u, "Banco Geral - Livre", ac, tot, dt))

        st.divider()
        if st.button("Sair", key="btn_logout"):
            st.session_state.clear()
            st.rerun()

    # Abas
    t1, t2, t3 = st.tabs(["DASHBOARD", "AGENDA", "VIDEOTECA"])
    
    # Importação Lazy para evitar erros circulares
    with t1:
        from dashboard import render_dashboard
        render_dashboard(None)
    
    with t2:
        from agenda import render_agenda
        render_agenda(None)

    with t3:
        from videoteca import render_videoteca
        render_videoteca(None)

if st.session_state.logado:
    app_principal()
else:
    tela_login()