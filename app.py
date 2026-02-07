# app.py
import streamlit as st
import traceback
import sys
import time
import extra_streamlit_components as stx
from datetime import datetime, timedelta

# 1. Configuração de Página (Deve ser a primeira chamada Streamlit)
st.set_page_config(page_title="MedPlanner Elite", page_icon="🩺", layout="wide")

# 2. CSS para Estilo Profissional e Responsividade
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .stTabs [data-baseweb="tab-list"] { justify-content: center; gap: 20px; border-bottom: 2px solid #f0f2f6; }
    .stTabs [data-baseweb="tab"] { font-size: 16px; font-weight: 600; }
    .login-header { text-align: center; margin-bottom: 2rem; }
    .stButton>button { border-radius: 8px; font-weight: 600; }
    /* Estilo para o botão de sair isolado */
    .logout-btn { margin-top: 20px; }
</style>
""", unsafe_allow_html=True)

# 3. Gerenciador de Cookies (Inicializado uma única vez)
def get_cookie_manager():
    return stx.CookieManager(key="cookie_manager_main_v5")

cookie_manager = get_cookie_manager()

# 4. Inicialização de Estado de Sessão (Padrão de Segurança)
if 'logado' not in st.session_state: st.session_state.logado = False
if 'username' not in st.session_state: st.session_state.username = "guest"
if 'u_nome' not in st.session_state: st.session_state.u_nome = "Visitante"
if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0
if 'quer_sair' not in st.session_state: st.session_state.quer_sair = False

# 5. Importações Seguras
_import_ok = True
_import_exc = None
try:
    import pandas as pd
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
    st.error("Erro crítico na inicialização dos módulos.")
    st.code(_import_exc)
    st.stop()

# --- FUNÇÕES DE CONTROLE DE ACESSO ---

def fazer_logout_definitivo():
    """Executa a limpeza real de cookies e estado e redireciona."""
    cookie_manager.delete("medplanner_auth")
    st.session_state.logado = False
    st.session_state.username = "guest"
    st.session_state.quer_sair = False
    # Limpa chaves específicas que causam erros de widget se necessário
    for key in list(st.session_state.keys()):
        if key.endswith("_slider") or key.startswith("txt_"):
            del st.session_state[key]
    st.rerun()

def verificar_sessao_automatica():
    """Verifica se existe um cookie para logar o usuário automaticamente."""
    # Pequeno delay para o componente de cookie responder no browser
    time.sleep(0.1)
    auth_cookie = cookie_manager.get(cookie="medplanner_auth")
    
    if auth_cookie and not st.session_state.logado:
        try:
            st.session_state.logado = True
            st.session_state.username = auth_cookie
            st.session_state.u_nome = "Dr(a). " + auth_cookie.capitalize()
            st.rerun()
        except:
            pass

def fazer_login(u, nome_real):
    """Realiza o login e salva o cookie."""
    st.session_state.logado = True
    st.session_state.username = u
    st.session_state.u_nome = nome_real
    expires_at = datetime.now() + timedelta(days=30)
    cookie_manager.set("medplanner_auth", u, expires_at=expires_at)
    st.toast(f"Bem-vindo, {nome_real}!", icon="👋")
    time.sleep(0.5)
    st.rerun()

# --- INTERFACES PRINCIPAIS ---

def app_principal():
    """Interface principal após autenticação."""
    try:
        # A Sidebar é renderizada. Se o botão "Sair" nela for clicado, 
        # ela deve apenas setar st.session_state.quer_sair = True
        render_sidebar(cookie_manager)
        
        # LOGOUT GATE: Verifica se o sinal de saída foi ativado
        if st.session_state.quer_sair:
            fazer_logout_definitivo()
            return # Interrompe a renderização para evitar erros de widget órfãos

        st.markdown("<h2 style='text-align:center;'>🩺 MEDPLANNER PRO</h2>", unsafe_allow_html=True)

        # Pomodoro e utilitários rápidos
        with st.expander("⏲️ Foco Pomodoro", expanded=False):
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                mode = st.radio("Modo:", ["Estudo (25m)", "Pausa (5m)"], horizontal=True)
                if st.button("🚀 Iniciar", key="pom_start"):
                    st.session_state._pom_rem = 25*60 if "Estudo" in mode else 5*60
                    st.rerun()
            if st.session_state.get("_pom_rem", 0) > 0:
                m, s = divmod(st.session_state["_pom_rem"], 60)
                st.markdown(f"<h1 style='text-align:center;'>{m:02d}:{s:02d}</h1>", unsafe_allow_html=True)
                st.session_state["_pom_rem"] = max(0, st.session_state["_pom_rem"]-1)
                time.sleep(1)
                st.rerun()

        # Renderização de Abas (Só ocorre se logado for True e quer_sair for False)
        abas = st.tabs([
            "📊 DASHBOARD", "🤖 MENTOR IA", "🏦 QUESTÕES", "🧠 ERROS", "⏱️ SIMULADO", 
            "📅 AGENDA", "📚 VIDEOTECA", "🗂️ CRONOGRAMA", "👤 PERFIL"
        ])
        
        with abas[0]: render_dashboard(None)
        with abas[1]: render_mentor(None)
        with abas[2]: render_banco_questoes(None)
        with abas[3]: render_caderno_erros(None)
        with abas[4]: render_simulado_real(None)
        with abas[5]: render_agenda(None)
        with abas[6]: render_videoteca(None)
        with abas[7]: render_cronograma(None)
        with abas[8]: render_perfil(None)

    except Exception as e:
        # Tratamento de erro silencioso durante logout para evitar alertas feios
        if st.session_state.quer_sair:
            fazer_logout_definitivo()
        else:
            st.error("Ocorreu um erro inesperado na interface principal.")
            st.code(traceback.format_exc())

def tela_login():
    """Interface de acesso inicial."""
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<div class='login-header'><h1>🩺 MedPlanner Elite</h1><p>Sua aprovação começa aqui.</p></div>", unsafe_allow_html=True)
        with st.container(border=True):
            tab_login, tab_cad = st.tabs(["🔐 Entrar", "✨ Criar Conta"])
            
            with tab_login:
                u = st.text_input("Usuário", key="l_user")
                p = st.text_input("Senha", type="password", key="l_pass")
                if st.button("Acessar", type="primary", use_container_width=True):
                    if u and p:
                        ok, nome = verificar_login(u, p)
                        if ok: fazer_login(u, nome)
                        else: st.error("Usuário ou senha incorretos.")
                    else: st.warning("Preencha todos os campos.")
            
            with tab_cad:
                nu = st.text_input("Novo Usuário", key="n_user")
                nn = st.text_input("Nome", key="n_name")
                np = st.text_input("Senha", type="password", key="n_pass")
                if st.button("Cadastrar", use_container_width=True):
                    if nu and nn and np:
                        ok, msg = criar_usuario(nu, np, nn)
                        if ok: 
                            st.success("Conta criada! Já pode entrar.")
                            st.balloons()
                        else: st.error(f"Erro ao criar conta: {msg}")
                    else: st.warning("Preencha todos os campos.")

# --- ORQUESTRAÇÃO FINAL ---

if st.session_state.logado:
    app_principal()
else:
    # Tenta login automático via cookie antes de mostrar a tela de login
    verificar_sessao_automatica()
    # Se ainda não logou (cookie não existe ou falhou), mostra login
    if not st.session_state.logado:
        tela_login()