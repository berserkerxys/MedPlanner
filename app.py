import streamlit as st
import pandas as pd
from datetime import datetime
from database import (
    verificar_login, criar_usuario, registrar_estudo, 
    registrar_simulado, get_progresso_hoje, get_lista_assuntos_nativa,
    get_db
)

# 1. Configuração de Página deve ser a primeira chamada Streamlit
st.set_page_config(page_title="MedPlanner", page_icon="🩺", layout="wide")

# CSS e Estado
st.markdown("<style>[data-testid='stSidebarNav'] {display: none;} .stTabs [data-baseweb='tab-list'] {justify-content: center;}</style>", unsafe_allow_html=True)

if 'logado' not in st.session_state:
    st.session_state.logado = False

def tela_login():
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.title("🩺 MedPlanner Cloud")
        t1, t2 = st.tabs(["Entrar", "Criar Conta"])
        
        with t1:
            with st.form("form_login"):
                u = st.text_input("Usuário", key="u_login")
                p = st.text_input("Senha", type="password", key="p_login")
                if st.form_submit_button("Aceder", type="primary", use_container_width=True):
                    ok, res = verificar_login(u, p)
                    if ok:
                        st.session_state.logado = True
                        st.session_state.username = u
                        st.session_state.u_nome = res
                        st.rerun()
                    else:
                        st.error(res)
        
        with t2:
            with st.form("form_registro"):
                nu = st.text_input("Novo Usuário", key="u_reg")
                nn = st.text_input("Seu Nome", key="n_reg")
                np = st.text_input("Senha", type="password", key="p_reg")
                if st.form_submit_button("Registrar Conta", use_container_width=True):
                    if nu and np and nn:
                        ok, msg = criar_usuario(nu, np, nn)
                        if ok: st.success(msg)
                        else: st.error(msg)
                    else:
                        st.warning("Preencha todos os campos.")

def app_principal():
    u = st.session_state.username
    with st.sidebar:
        st.title(f"Olá, {st.session_state.u_nome}!")
        st.metric("Questões Hoje", get_progresso_hoje(u))
        st.divider()
        
        st.subheader("📝 Registrar")
        modo = st.radio("Tipo:", ["Por Tema", "Simulado Geral", "Banco Geral"], key="radio_sidebar")
        dt = st.date_input("Data:", datetime.now(), key="date_sidebar")
        
        if modo == "Por Tema":
            lista = get_lista_assuntos_nativa()
            tema = st.selectbox("Escolha o Tema:", lista, index=None, placeholder="Selecione...", key="sel_tema")
            c1, c2 = st.columns(2)
            tot = c1.number_input("Total", 1, 200, 10, key="t_est")
            acc = c2.number_input("Acertos", 0, tot, 8, key="a_est")
            if st.button("Salvar Aula", type="primary", use_container_width=True, key="btn_save_aula"):
                if tema: st.toast(registrar_estudo(u, tema, acc, tot, dt))
                else: st.warning("Escolha o tema!")

        elif modo == "Simulado Geral":
            areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
            dados_sim = {}
            with st.form("form_sim_sidebar"):
                for a in areas:
                    c1, c2 = st.columns([2, 1])
                    c1.write(f"**{a}**")
                    ac = c2.number_input("Ac", 0, 100, 15, key=f"sim_ac_{a}", label_visibility="collapsed")
                    dados_sim[a] = {'total': 20, 'acertos': ac}
                if st.form_submit_button("💾 Salvar Simulado", type="primary", use_container_width=True):
                    st.toast(registrar_simulado(u, dados_sim, dt))

        elif modo == "Banco Geral":
            c1, c2 = st.columns(2)
            tot = c1.number_input("Total", 1, 500, 50, key="bg_t")
            acc = c2.number_input("Acertos", 0, tot, 35, key="bg_a")
            if st.button("Salvar Banco", type="primary", key="btn_save_bg"):
                st.toast(registrar_estudo(u, "Banco Geral - Livre", acc, tot, dt))

        st.divider()
        if st.button("Sair", key="btn_logout"):
            st.session_state.clear()
            st.rerun()

    t1, t2, t3 = st.tabs(["📊 DASHBOARD", "📅 AGENDA", "📚 VIDEOTECA"])
    
    with t1:
        from dashboard import render_dashboard
        render_dashboard(None)
    with t2:
        from agenda import render_agenda
        render_agenda(None)
    with t3:
        from videoteca import render_videoteca
        render_videoteca(None)

# Lógica de Execução Principal
if st.session_state.logado:
    app_principal()
else:
    tela_login()