import streamlit as st
import pandas as pd
from datetime import datetime
from database import (
    verificar_login, criar_usuario, registrar_estudo, 
    registrar_simulado, get_progresso_hoje, get_lista_assuntos_nativa
)

st.set_page_config(page_title="MedPlanner", page_icon="🩺", layout="wide")

# CSS e Estado
st.markdown("<style>[data-testid='stSidebarNav'] {display: none;} .stTabs [data-baseweb='tab-list'] {justify-content: center;}</style>", unsafe_allow_html=True)
if 'logado' not in st.session_state: st.session_state.logado = False
if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0

def tela_login():
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.title("🩺 MedPlanner")
        t1, t2 = st.tabs(["Entrar", "Criar Conta"])
        with t1:
            with st.form("f_login"):
                u = st.text_input("Usuário", key="u_log")
                p = st.text_input("Senha", type="password", key="p_log")
                if st.form_submit_button("Aceder", type="primary", use_container_width=True):
                    ok, res = verificar_login(u, p)
                    if ok:
                        st.session_state.logado = True
                        st.session_state.username = u
                        st.session_state.u_nome = res
                        st.rerun()
                    else: st.error(res)
        with t2:
            with st.form("f_reg"):
                nu = st.text_input("ID Usuário"); nn = st.text_input("Nome"); np = st.text_input("Senha", type="password")
                if st.form_submit_button("Registrar Conta"):
                    ok, m = criar_usuario(nu, np, nn)
                    st.success(m) if ok else st.error(m)

def app_principal():
    u = st.session_state.username
    with st.sidebar:
        st.title(f"Olá, {st.session_state.u_nome}!")
        st.metric("Questões Hoje", get_progresso_hoje(u, st.session_state.data_nonce))
        st.divider()
        st.subheader("📝 Registrar Atividade")
        modo = st.radio("Modo:", ["Tema", "Simulado", "Banco"], key="mode")
        dt = st.date_input("Data:", datetime.now(), key="d_reg")
        
        if modo == "Tema":
            lista = get_lista_assuntos_nativa()
            tema = st.selectbox("Assunto:", lista, index=None, placeholder="Selecione...")
            c1, c2 = st.columns(2)
            tot = c1.number_input("Total", 1, 500, 10, key="t_q")
            acc = c2.number_input("Acertos", 0, tot, 8, key="a_q")
            if st.button("Salvar Aula", type="primary", use_container_width=True):
                if tema: st.toast(registrar_estudo(u, tema, acc, tot, dt))
                else: st.warning("Escolha o tema")

        elif modo == "Simulado":
            areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
            dados_sim = {}
            for a in areas:
                with st.expander(f"📍 {a}"):
                    ac = st.number_input("Acertos", 0, 20, 15, key=f"ac_{a}")
                    dados_sim[a] = {'total': 20, 'acertos': ac}
            if st.button("💾 Salvar Simulado", type="primary", use_container_width=True):
                st.toast(registrar_simulado(u, dados_sim, dt))

        elif modo == "Banco":
            c1, c2 = st.columns(2)
            tot = c1.number_input("Total", 1, 1000, 50, key="b_t")
            acc = c2.number_input("Acertos", 0, tot, 35, key="b_a")
            if st.button("Salvar Banco", type="primary"):
                st.toast(registrar_estudo(u, "Banco Geral - Livre", acc, tot, dt))

        st.divider()
        if st.button("Sair (Logout)", use_container_width=True):
            st.session_state.logado = False
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

if st.session_state.logado: app_principal()
else: tela_login()