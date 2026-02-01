import streamlit as st
import pandas as pd
from datetime import datetime
from database import (
    verificar_login, criar_usuario, registrar_estudo, 
    registrar_simulado, get_progresso_hoje, get_db
)

st.set_page_config(page_title="MedPlanner", page_icon="🩺", layout="wide")

# CSS Customizado
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .stTabs [data-baseweb="tab-list"] {justify-content: center; gap: 20px;}
    .stMetric {background-color: #f8fafc; padding: 10px; border-radius: 10px; border: 1px solid #e2e8f0;}
</style>
""", unsafe_allow_html=True)

if 'logado' not in st.session_state: st.session_state.logado = False

# --- LOGIN ---
def tela_login():
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.title("🩺 MedPlanner Cloud")
        if not get_db(): st.error("Erro de conexão Firebase. Verifique os Secrets."); return
        
        t1, t2 = st.tabs(["Entrar", "Criar Conta"])
        with t1:
            with st.form("login"):
                u = st.text_input("Usuário", key="login_u")
                p = st.text_input("Senha", type="password", key="login_p")
                if st.form_submit_button("Acessar", type="primary", use_container_width=True):
                    ok, nome = verificar_login(u, p)
                    if ok:
                        st.session_state.logado = True; st.session_state.username = u; st.session_state.u_nome = nome
                        st.rerun()
                    else: st.error("Credenciais inválidas.")
        with t2:
            with st.form("registro"):
                nu = st.text_input("Novo Usuário"); nn = st.text_input("Nome Completo"); np = st.text_input("Senha", type="password")
                if st.form_submit_button("Registrar Conta", use_container_width=True):
                    ok, msg = criar_usuario(nu, np, nn)
                    st.success(msg) if ok else st.error(msg)

# --- APP ---
def app_principal():
    u = st.session_state.username
    db = get_db()
    
    with st.sidebar:
        st.title(f"Olá, {st.session_state.u_nome}!")
        st.metric("Questões Hoje", get_progresso_hoje(u))
        st.divider()
        
        st.subheader("📝 Registrar Atividade")
        modo = st.radio("Tipo de Estudo:", ["Por Tema", "Simulado Geral", "Banco Geral"], key="reg_modo")
        dt = st.date_input("Data:", datetime.now())
        
        if modo == "Por Tema":
            # Busca temas do Firebase
            assuntos_docs = db.collection('assuntos').stream()
            lista_temas = sorted([d.to_dict()['nome'] for d in assuntos_docs])
            
            tema_esc = st.selectbox("Escolha o Tema:", lista_temas, index=None, placeholder="Selecione...")
            c1, c2 = st.columns(2)
            tot = c1.number_input("Total", 1, 200, 10)
            acc = c2.number_input("Acertos", 0, tot, 8)
            if st.button("Salvar Estudo", type="primary", use_container_width=True):
                if tema_esc: st.toast(registrar_estudo(u, tema_esc, acc, tot, dt))
                else: st.warning("Selecione um tema!")

        elif modo == "Simulado Geral":
            st.info("Insira os acertos de cada área (20 questões cada):")
            areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
            dados_sim = {}
            for a in areas:
                with st.expander(f"📍 {a}", expanded=False):
                    c1, c2 = st.columns(2)
                    t_a = c1.number_input(f"Total {a}", 0, 100, 20, key=f"t_{a}")
                    a_a = c2.number_input(f"Acertos {a}", 0, t_a, 15, key=f"a_{a}")
                    dados_sim[a] = {'acertos': a_a, 'total': t_a}
            
            if st.button("💾 Salvar Simulado", type="primary", use_container_width=True):
                st.toast(registrar_simulado(u, dados_sim, dt))

        elif modo == "Banco Geral":
            c1, c2 = st.columns(2)
            tot = c1.number_input("Total Questões", 1, 500, 50)
            acc = c2.number_input("Acertos", 0, tot, 35)
            if st.button("Salvar Banco", type="primary", use_container_width=True):
                st.toast(registrar_estudo(u, "Banco Geral - Livre", acc, tot, dt))

        st.divider()
        if st.button("Sair"): st.session_state.clear(); st.rerun()

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