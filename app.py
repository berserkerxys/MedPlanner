# app.py
import streamlit as st
import traceback
import sys
import time
import extra_streamlit_components as stx
from datetime import datetime, timedelta

# Configuração da página com layout wide para aproveitar espaço, 
# mas controlaremos a largura via CSS para responsividade.
st.set_page_config(page_title="MedPlanner Elite", page_icon="🩺", layout="wide")

# --- CSS PARA DESIGN RESPONSIVO E MODERNO ---
st.markdown("""
<style>
    /* Reset e Variáveis de Layout */
    [data-testid="stSidebarNav"] {display: none;}
    
    /* Container Principal: Garante que em telas ultra-wide o conteúdo não se perca */
    .block-container {
        max-width: 1300px;
        padding-top: 2rem;
        padding-bottom: 2rem;
        margin: auto;
    }

    /* Estilização de Abas Responsivas: Scroll horizontal automático em telas pequenas */
    .stTabs [data-baseweb="tab-list"] {
        display: flex;
        justify-content: center;
        gap: 5px;
        border-bottom: 2px solid #f0f2f6;
        overflow-x: auto; /* Permite rolar abas no mobile */
        overflow-y: hidden;
        white-space: nowrap;
        padding: 5px 0;
    }
    
    /* Melhoria no toque e leitura das abas */
    .stTabs [data-baseweb="tab"] {
        font-size: 14px !important;
        font-weight: 600 !important;
        padding: 10px 15px !important;
        border-radius: 8px 8px 0 0 !important;
    }

    /* Estilização Global de Botões */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        transition: transform 0.1s;
    }
    .stButton>button:active {
        transform: scale(0.98);
    }

    /* Estilo da Tela de Login */
    .login-header {
        text-align: center;
        margin-bottom: 1.5rem;
    }
    
    /* Ajustes para mobile (Telas menores que 768px) */
    @media (max-width: 768px) {
        .stTabs [data-baseweb="tab-list"] {
            justify-content: flex-start; /* Alinha à esquerda para facilitar o scroll */
        }
        .stTabs [data-baseweb="tab"] {
            font-size: 12px !important;
            padding: 8px 10px !important;
        }
        h1 { font-size: 1.8rem !important; }
        h2 { font-size: 1.4rem !important; }
    }
</style>
""", unsafe_allow_html=True)

# Gerenciador de Cookies - Adicionada Key fixa para evitar DuplicateElementKey
def get_cookie_manager():
    return stx.CookieManager(key="med_cookie_manager_v1")

cookie_manager = get_cookie_manager()

_import_ok = True
_import_exc = None
try:
    import pandas as pd
    
    # Imports Locais
    from sidebar_v2 import render_sidebar
    from database import verificar_login, criar_usuario, get_resumo, salvar_resumo
    from perfil import render_perfil
    from mentor import render_mentor
    from simulado import render_simulado_real
    from caderno_erros import render_caderno_erros
    from videoteca import render_videoteca
    from agenda import render_agenda
    from cronograma import render_cronograma
    from dashboard import render_dashboard
    from banco_questoes import render_banco_questoes
    
except Exception as e:
    _import_ok = False
    _import_exc = traceback.format_exc()

if not _import_ok:
    st.error("Erro crítico na inicialização das seções.")
    st.code(_import_exc)
    st.stop()

# --- LÓGICA DE SESSÃO PERSISTENTE ---
def verificar_sessao_automatica():
    # Pequeno delay técnico para o componente JS responder
    time.sleep(0.1)
    auth_cookie = cookie_manager.get(cookie="medplanner_auth")
    
    if auth_cookie and not st.session_state.get('logado', False):
        try:
            user_salvo = auth_cookie
            st.session_state.logado = True
            st.session_state.username = user_salvo
            st.session_state.u_nome = "Dr(a). " + user_salvo.capitalize()
            st.rerun()
            return True
        except:
            return False
    return False

if 'logado' not in st.session_state: st.session_state.logado = False
if 'username' not in st.session_state: st.session_state.username = "guest"
if 'u_nome' not in st.session_state: st.session_state.u_nome = "Visitante"
if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0

# Tenta login automático se não estiver logado
if not st.session_state.logado:
    verificar_sessao_automatica()

def fazer_login(u, nome_real):
    st.session_state.logado = True
    st.session_state.username = u
    st.session_state.u_nome = nome_real
    # Expira em 30 dias
    expires_at = datetime.now() + timedelta(days=30)
    cookie_manager.set("medplanner_auth", u, expires_at=expires_at)
    st.toast(f"Bem-vindo de volta, {nome_real}!", icon="👋")
    time.sleep(0.5)
    st.rerun()

def fazer_logout():
    st.session_state.logado = False
    st.session_state.username = "guest"
    cookie_manager.delete("medplanner_auth")
    st.rerun()

def app_principal():
    try:
        render_sidebar()
        
        if not st.session_state.logado:
            fazer_logout()
            return

        # Cabeçalho Adaptável
        st.markdown("<div class='login-header'><h2>🩺 MEDPLANNER PRO</h2></div>", unsafe_allow_html=True)

        # Pomodoro Compacto e Responsivo
        with st.expander("⏲️ Foco Pomodoro", expanded=False):
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                mode = st.radio("Modo:", ["Estudo (25m)", "Pausa (5m)"], horizontal=True)
                if st.button("🚀 Iniciar Temporizador", key="pom_start"):
                    st.session_state._pom_rem = 25*60 if "Estudo" in mode else 5*60
                    st.rerun()
            
            if st.session_state.get("_pom_rem", 0) > 0:
                m, s = divmod(st.session_state["_pom_rem"], 60)
                st.markdown(f"<h1 style='text-align:center; color:#FF4B4B;'>{m:02d}:{s:02d}</h1>", unsafe_allow_html=True)
                st.session_state["_pom_rem"] = max(0, st.session_state["_pom_rem"]-1)
                time.sleep(1); st.rerun()

        # --- NAVEGAÇÃO PRINCIPAL (Abas Adaptáveis) ---
        # No mobile, o CSS acima fará estas abas serem roláveis lateralmente.
        abas = st.tabs([
            "📊 DASHBOARD", "🤖 MENTOR", "🏦 QUESTÕES", "🧠 ERROS", 
            "⏱️ SIMULADO", "📅 AGENDA", "📚 VIDEOS", "🗂️ CRONOGRAMA", "👤 PERFIL"
        ])
        
        # Injeção de conteúdo em containers para controle de margem
        with abas[0]: render_dashboard(None)
        with abas[1]: render_mentor(None)
        with abas[2]: render_banco_questoes(None)
        with abas[3]: render_caderno_erros(None)
        with abas[4]: render_simulado_real(None)
        with abas[5]: render_agenda(None)
        with abas[6]: render_videoteca(None)
        with abas[7]: render_cronograma(None)
        with abas[8]: render_perfil(None)

    except Exception:
        st.error("Ocorreu um erro ao carregar as seções do aplicativo."); 
        st.code(traceback.format_exc())

def tela_login():
    st.markdown("<br>", unsafe_allow_html=True)
    # Colunas responsivas: No desktop centraliza, no mobile ocupam a largura total
    _, central_col, _ = st.columns([1, 4, 1])
    
    with central_col:
        st.markdown("""
            <div class='login-header'>
                <h1>🩺 MedPlanner Elite</h1>
                <p style='color: #666;'>Gestão de Estudos de Alta Performance</p>
            </div>
        """, unsafe_allow_html=True)
        
        with st.container(border=True):
            tab_login, tab_cad = st.tabs(["🔐 Acessar", "✨ Nova Conta"])
            
            with tab_login:
                u = st.text_input("Usuário", key="l_user", placeholder="Seu nome de usuário")
                p = st.text_input("Senha", type="password", key="l_pass", placeholder="******")
                if st.button("Entrar no Sistema", type="primary", use_container_width=True):
                    if u and p:
                        ok, nome = verificar_login(u, p)
                        if ok: fazer_login(u, nome)
                        else: st.error("Usuário ou senha incorretos.")
                    else: st.warning("Por favor, preencha todos os campos.")
            
            with tab_cad:
                nu = st.text_input("Criar Usuário", key="n_user")
                nn = st.text_input("Nome Completo", key="n_name")
                np = st.text_input("Definir Senha", type="password", key="n_pass")
                if st.button("Finalizar Cadastro", use_container_width=True):
                    if nu and nn and np:
                        ok, msg = criar_usuario(nu, np, nn)
                        if ok: 
                            st.success("Conta criada com sucesso! Mude para a aba 'Acessar'.")
                            st.balloons()
                        else: st.error(f"Erro ao cadastrar: {msg}")
                    else: st.warning("Preencha todos os campos para continuar.")

# --- FLUXO DE EXECUÇÃO ---
if st.session_state.logado:
    app_principal()
else:
    tela_login()