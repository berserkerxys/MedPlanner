import streamlit as st
import pandas as pd
from datetime import datetime
from database import (
    verificar_login, criar_usuario, registrar_estudo, 
    registrar_simulado, get_progresso_hoje, get_db, sincronizar_videoteca_completa
)

st.set_page_config(page_title="MedPlanner", page_icon="🩺", layout="wide")

# CSS para evitar conflitos e melhorar UI
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .stTabs [data-baseweb="tab-list"] {justify-content: center; gap: 20px;}
</style>
""", unsafe_allow_html=True)

if 'logado' not in st.session_state: st.session_state.logado = False

# --- TELA DE LOGIN ---
def tela_login():
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.title("🩺 MedPlanner Cloud")
        if not get_db(): st.error("Erro de conexão com o Firebase."); return
        
        t1, t2 = st.tabs(["Entrar", "Criar Conta"])
        with t1:
            with st.form("form_login"):
                u = st.text_input("Utilizador", key="u_login")
                p = st.text_input("Palavra-passe", type="password", key="p_login")
                if st.form_submit_button("Aceder", type="primary", use_container_width=True):
                    ok, nome = verificar_login(u, p)
                    if ok:
                        st.session_state.logado = True
                        st.session_state.username = u
                        st.session_state.u_nome = nome
                        st.rerun()
                    else: st.error("Dados incorretos.")
        with t2:
            with st.form("form_registro"):
                nu = st.text_input("Novo Utilizador", key="u_reg")
                nn = st.text_input("Nome Completo", key="n_reg")
                np = st.text_input("Nova Palavra-passe", type="password", key="p_reg")
                if st.form_submit_button("Registar", use_container_width=True):
                    ok, msg = criar_usuario(nu, np, nn)
                    st.success(msg) if ok else st.error(msg)

# --- APP PRINCIPAL ---
def app_principal():
    u = st.session_state.username
    db = get_db()
    
    with st.sidebar:
        st.title(f"Olá, {st.session_state.u_nome}!")
        st.metric("Questões Hoje", get_progresso_hoje(u))
        st.divider()
        
        st.subheader("📝 Registar Estudo")
        modo = st.radio("Modo:", ["Por Tema", "Simulado Geral", "Banco Geral"], key="radio_modo")
        dt = st.date_input("Data:", datetime.now(), key="main_date")
        
        if modo == "Por Tema":
            docs = db.collection('assuntos').stream()
            lista_temas = sorted([d.to_dict()['nome'] for d in docs])
            esc = st.selectbox("Selecione o Tema:", lista_temas, index=None, placeholder="Escolha...")
            c1, c2 = st.columns(2)
            tot = c1.number_input("Total", 1, 200, 10, key="t_est")
            acc = c2.number_input("Acertos", 0, tot, 8, key="a_est")
            if st.button("Guardar Aula", type="primary", use_container_width=True):
                if esc: st.toast(registrar_estudo(u, esc, acc, tot, dt))
                else: st.warning("Selecione um tema!")

        elif modo == "Simulado Geral":
            areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
            dados_sim = {}
            with st.form("sim_form"):
                for a in areas:
                    st.markdown(f"**{a}**")
                    c1, c2 = st.columns(2)
                    t = c1.number_input("Qtd", 0, 100, 20, key=f"t_{a}")
                    ac = c2.number_input("Ac", 0, t, 15, key=f"ac_{a}")
                    dados_sim[a] = {'total': t, 'acertos': ac}
                if st.form_submit_button("💾 Salvar Simulado Completo", type="primary"):
                    st.toast(registrar_simulado(u, dados_sim, dt))

        elif modo == "Banco Geral":
            c1, c2 = st.columns(2)
            tot = c1.number_input("Total", 1, 500, 50, key="t_bg")
            acc = c2.number_input("Acertos", 0, tot, 35, key="a_bg")
            if st.button("Guardar Banco", type="primary", use_container_width=True):
                st.toast(registrar_estudo(u, "Banco Geral - Livre", acc, tot, dt))

        st.divider()
        if st.button("🔄 Sincronizar Videoteca"):
            with st.spinner("A enviar biblioteca para a nuvem..."):
                st.toast(sincronizar_videoteca_completa())
        
        if st.button("Sair", key="logout_btn"):
            st.session_state.clear(); st.rerun()

    # ABAS
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