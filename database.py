# app.py
import streamlit as st
import traceback
import sys
import time
import extra_streamlit_components as stx  # Biblioteca essencial para cookies
from datetime import datetime, timedelta

st.set_page_config(page_title="MedPlanner Elite", page_icon="🩺", layout="wide")

# CSS para estilo profissional
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .stTabs [data-baseweb="tab-list"] { justify-content: center; gap: 20px; border-bottom: 2px solid #f0f2f6; }
    .stTabs [data-baseweb="tab"] { font-size: 16px; font-weight: 600; }
    .login-header { text-align: center; margin-bottom: 2rem; }
    .stButton>button { border-radius: 8px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# Gerenciador de Cookies
# REMOVIDO: @st.cache_resource para evitar CachedWidgetWarning e StreamlitDuplicateElementKey
# O CookieManager deve ser instanciado diretamente no script principal
def get_cookie_manager():
    return stx.CookieManager(key="cookie_manager_main")

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
    
except Exception as e:
    _import_ok = False
    _import_exc = traceback.format_exc()

if not _import_ok:
    st.error("Erro crítico na inicialização.")
    st.code(_import_exc)
    st.stop()

# --- LÓGICA DE SESSÃO PERSISTENTE ---
def verificar_sessao_automatica():
    # Tenta ler o cookie de autenticação
    # Nota: cookie_manager.get_all() ou .get() pode precisar de um tempo para carregar no front
    time.sleep(0.1) # Pequeno delay para garantir carga
    auth_cookie = cookie_manager.get(cookie="medplanner_auth")
    
    if auth_cookie and not st.session_state.get('logado', False):
        try:
            user_salvo = auth_cookie
            st.session_state.logado = True
            st.session_state.username = user_salvo
            st.session_state.u_nome = "Dr(a). " + user_salvo.capitalize()
            # Força rerun para atualizar a interface com o estado logado
            st.rerun()
            return True
        except:
            return False
    return False

# Inicialização de Estado
if 'logado' not in st.session_state: 
    st.session_state.logado = False
    
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
    
    # Salva cookie por 30 dias
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

def render_resumos_ui(u):
    pass

def app_principal():
    try:
        render_sidebar()
        
        # Check de Logout vindo da Sidebar
        if not st.session_state.logado:
            fazer_logout()
            return

        st.markdown("<h2 style='text-align:center;'>🩺 MEDPLANNER PRO</h2>", unsafe_allow_html=True)

        # Pomodoro
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
                time.sleep(1); st.rerun()

        # Abas Principais
        abas = st.tabs([
            "📊 DASHBOARD", "🤖 MENTOR IA", "🧠 CADERNO ERROS", "⏱️ SIMULADO", 
            "📅 AGENDA", "📚 VIDEOTECA", "🗂️ CRONOGRAMA", "👤 PERFIL"
        ])
        
        with abas[0]: 
            from dashboard import render_dashboard; render_dashboard(None)
        with abas[1]: render_mentor(None)
        with abas[2]: render_caderno_erros(None)
        with abas[3]: render_simulado_real(None)
        with abas[4]: 
            from agenda import render_agenda; render_agenda(None)
        with abas[5]: 
            from videoteca import render_videoteca; render_videoteca(None)
        with abas[6]: 
            from cronograma import render_cronograma; render_cronograma(None)
        with abas[7]: render_perfil(None)

    except Exception:
        st.error("Erro no app principal"); st.code(traceback.format_exc())

def tela_login():
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
                        if ok:
                            fazer_login(u, nome)
                        else: st.error(nome)
                    else: st.warning("Preencha tudo.")
            
            with tab_cad:
                nu = st.text_input("Novo Usuário", key="n_user")
                nn = st.text_input("Nome", key="n_name")
                np = st.text_input("Senha", type="password", key="n_pass")
                if st.button("Cadastrar", use_container_width=True):
                    if nu and nn and np:
                        ok, msg = criar_usuario(nu, np, nn)
                        if ok: st.success("Criado! Faça login."); st.balloons()
                        elif "UNIQUE" in str(msg) or "IntegrityError" in str(msg): st.error("Usuário já existe.")
                        else: st.error(f"Erro: {msg}")
                    else: st.warning("Preencha tudo.")

# Lógica de Controle de Fluxo
if st.session_state.logado:
    app_principal()
else:
    tela_login()