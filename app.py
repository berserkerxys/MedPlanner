import streamlit as st
import pandas as pd
from datetime import datetime
from database import (
    verificar_login, criar_usuario, get_connection, 
    registrar_estudo, registrar_simulado, get_progresso_hoje
)

st.set_page_config(page_title="MedPlanner", page_icon="🩺", layout="wide", initial_sidebar_state="collapsed")

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
        st.title("🩺 MedPlanner")
        t1, t2 = st.tabs(["Acessar", "Criar Conta"])
        
        with t1:
            with st.form("l"):
                u = st.text_input("Usuário", key="login_u")
                p = st.text_input("Senha", type="password", key="login_p")
                if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                    ok, nome = verificar_login(u, p)
                    if ok:
                        st.session_state['logado'] = True
                        st.session_state['username'] = u
                        st.session_state['u_nome'] = nome
                        st.rerun()
                    else: 
                        st.error("Erro no login")
        
        with t2:
            with st.form("r"):
                nu = st.text_input("Usuário novo"); nn = st.text_input("Nome"); np = st.text_input("Senha nova", type="password")
                if st.form_submit_button("Registrar"):
                    ok, msg = criar_usuario(nu, np, nn)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

def app_principal():
    u = st.session_state.username
    conn = get_connection()
    
    with st.sidebar:
        st.title(f"Olá, {st.session_state.get('u_nome', 'Doc')} 👋")
        st.metric("Questões Hoje", get_progresso_hoje(u))
        st.divider()
        
        st.subheader("📝 Novo Estudo")
        modo = st.radio("Modo:", ["Por Tema", "Simulado Geral", "Banco Geral"], label_visibility="collapsed")
        dt = st.date_input("Data", datetime.now())
        
        if modo == "Por Tema":
            df_as = pd.read_sql("SELECT nome FROM assuntos ORDER BY nome", conn)
            lista_aulas = df_as['nome'].tolist()
            esc = st.selectbox("Aula:", lista_aulas) if lista_aulas else None
            
            c1, c2 = st.columns(2)
            tot = c1.number_input("Total", 1, 500, 10)
            ac = c2.number_input("Acertos", 0, tot, 8)
            
            if st.button("Salvar Registro", type="primary", use_container_width=True):
                if esc:
                    st.toast(registrar_estudo(u, esc, ac, tot, data_personalizada=dt))
                else:
                    st.error("Nenhuma aula selecionada.")

        elif modo == "Simulado Geral":
            st.info("Insira o desempenho por área:")
            areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
            dados = {}
            for a in areas:
                with st.expander(f"📍 {a}", expanded=False):
                    c1, c2 = st.columns(2)
                    t_a = c1.number_input(f"Total {a}", 0, 100, 20, key=f"t_{a}")
                    a_a = c2.number_input(f"Acertos {a}", 0, t_a, 15, key=f"a_{a}")
                    dados[a] = {'acertos': a_a, 'total': t_a}
            
            if st.button("Salvar Simulado", type="primary", use_container_width=True):
                st.toast(registrar_simulado(u, dados, data_personalizada=dt))

        elif modo == "Banco Geral":
            st.info("Treino livre")
            c1, c2 = st.columns(2)
            tot = c1.number_input("Total Questões", 1, 500, 50)
            ac = c2.number_input("Acertos", 0, tot, 35)
            if st.button("Salvar Banco", type="primary", use_container_width=True):
                st.toast(registrar_estudo(u, "Banco Geral - Livre", ac, tot, data_personalizada=dt))

        st.divider()
        if st.button("Sair"):
            st.session_state.logado = False
            st.rerun()

    # NAVEGAÇÃO
    t_dash, t_agenda, t_video, t_config = st.tabs(["📊 DASHBOARD", "📅 AGENDA", "📚 VIDEOTECA", "⚙️ AJUSTES"])
    
    with t_dash: 
        from dashboard import render_dashboard
        render_dashboard(conn)
    with t_agenda:
        from agenda import render_agenda
        render_agenda(conn)
    with t_video:
        from videoteca import render_videoteca
        render_videoteca(conn)
    with t_config:
        from gerenciar import render_configuracoes
        render_configuracoes(conn)
    
    conn.close()

if st.session_state['logado']:
    app_principal()
else:
    tela_login()