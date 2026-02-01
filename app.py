import streamlit as st
import pandas as pd
from datetime import datetime
from database import (
    verificar_login, criar_usuario, registrar_estudo, 
    registrar_simulado, get_progresso_hoje, get_lista_assuntos_nativa
)

# 1. Configuração de Página (Deve ser sempre a primeira chamada)
st.set_page_config(page_title="MedPlanner", page_icon="🩺", layout="wide", initial_sidebar_state="collapsed")

# Estilos Visuais para uma experiência Premium
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .stTabs [data-baseweb="tab-list"] {
        justify-content: center;
        gap: 20px;
    }
    .stMetric {
        background-color: #f8fafc;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
    }
    div[data-testid="stForm"] {
        border: none;
        padding: 0;
    }
</style>
""", unsafe_allow_html=True)

# Inicialização do Estado de Login
if 'logado' not in st.session_state:
    st.session_state.logado = False

def tela_login():
    """Renderiza a interface de acesso e criação de conta."""
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        st.markdown("<h1 style='text-align: center;'>🩺 MedPlanner</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b;'>Sua residência começa aqui</p>", unsafe_allow_html=True)
        
        aba_login, aba_reg = st.tabs(["Entrar", "Criar Conta"])
        
        with aba_login:
            with st.form("form_login_principal"):
                u = st.text_input("Usuário", key="login_user_input", placeholder="ex: vitor.dinizio")
                p = st.text_input("Senha", type="password", key="login_pass_input")
                
                if st.form_submit_button("Aceder", type="primary", use_container_width=True):
                    if u and p:
                        ok, res = verificar_login(u, p)
                        if ok:
                            st.session_state.logado = True
                            st.session_state.username = u
                            st.session_state.u_nome = res
                            st.rerun()
                        else:
                            st.error(res)
                    else:
                        st.warning("Introduza o usuário e a senha.")
        
        with aba_reg:
            with st.form("form_registro_novo"):
                nu = st.text_input("Novo Usuário", key="reg_user", placeholder="Crie um ID único")
                nn = st.text_input("Nome Completo", key="reg_name", placeholder="Como deseja ser chamado")
                np = st.text_input("Definir Senha", type="password", key="reg_pass")
                
                if st.form_submit_button("Registrar Conta", use_container_width=True):
                    if nu and np and nn:
                        ok, msg = criar_usuario(nu, np, nn)
                        if ok:
                            st.success("Conta criada! Pode fazer login.")
                        else:
                            st.error(msg)
                    else:
                        st.warning("Preencha todos os campos obrigatórios.")

def app_principal():
    """Interface principal após o login."""
    u = st.session_state.username
    
    with st.sidebar:
        st.title(f"Olá, {st.session_state.u_nome}!")
        st.metric("Questões Hoje", get_progresso_hoje(u))
        st.divider()
        
        st.subheader("📝 Registrar Atividade")
        modo = st.radio("Modo de Estudo:", ["Por Tema", "Simulado", "Banco Geral"], key="sidebar_mode")
        dt = st.date_input("Data:", datetime.now(), key="sidebar_date")
        
        if modo == "Por Tema":
            # Busca temas do arquivo biblioteca_conteudo.py
            lista_temas = get_lista_assuntos_nativa()
            tema = st.selectbox("Escolha o Tema:", lista_temas, index=None, placeholder="Selecione o assunto...", key="sel_tema_reg")
            
            c1, c2 = st.columns(2)
            tot = c1.number_input("Total", 1, 500, 10, key="tema_tot")
            acc = c2.number_input("Acertos", 0, tot, 8, key="tema_acc")
            
            if st.button("Salvar Estudo", type="primary", use_container_width=True, key="btn_save_tema"):
                if tema:
                    msg = registrar_estudo(u, tema, acc, tot, dt)
                    st.toast(msg)
                else:
                    st.error("Por favor, selecione um tema.")

        elif modo == "Simulado":
            st.info("Simulado Geral (20q por área)")
            areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
            dados_sim = {}
            
            for a in areas:
                with st.expander(f"📍 {a}", expanded=False):
                    c1, c2 = st.columns(2)
                    t = c1.number_input(f"Total {a}", 0, 100, 20, key=f"sim_t_{a}")
                    ac = c2.number_input(f"Acertos {a}", 0, t, 15, key=f"sim_ac_{a}")
                    dados_sim[a] = {'total': t, 'acertos': ac}
            
            if st.button("💾 Salvar Simulado", type="primary", use_container_width=True, key="btn_save_sim"):
                msg = registrar_simulado(u, dados_sim, dt)
                st.toast(msg)

        elif modo == "Banco Geral":
            c1, c2 = st.columns(2)
            tot = c1.number_input("Total Questões", 1, 1000, 50, key="bg_tot_input")
            acc = c2.number_input("Acertos", 0, tot, 35, key="bg_acc_input")
            
            if st.button("Salvar Banco", type="primary", use_container_width=True, key="btn_save_bg"):
                msg = registrar_estudo(u, "Banco Geral - Livre", acc, tot, dt)
                st.toast(msg)

        st.divider()
        if st.button("Sair", key="btn_logout_final", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    # Organização por Abas
    t1, t2, t3 = st.tabs(["📊 DASHBOARD", "📅 AGENDA", "📚 VIDEOTECA"])
    
    # Carregamento tardio (Lazy Load) para evitar erros circulares
    with t1:
        from dashboard import render_dashboard
        render_dashboard(None)
    with t2:
        from agenda import render_agenda
        render_agenda(None)
    with t3:
        from videoteca import render_videoteca
        render_videoteca(None)

# --- Execução Principal ---
if st.session_state.logado:
    app_principal()
else:
    tela_login()