# app.py
import streamlit as st
import traceback
import time
import extra_streamlit_components as stx
from datetime import datetime, timedelta

# 1. Configuração de Página (Deve ser a PRIMEIRA chamada Streamlit do script)
st.set_page_config(page_title="MedPlanner Elite", page_icon="🩺", layout="wide")

# 2. Inicialização de Estado de Sessão (Executado IMEDIATAMENTE)
if 'logado' not in st.session_state: st.session_state.logado = False
if 'username' not in st.session_state: st.session_state.username = "guest"
if 'u_nome' not in st.session_state: st.session_state.u_nome = "Visitante"
if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0
if 'quer_sair' not in st.session_state: st.session_state.quer_sair = False

# 3. CSS para Estilo Profissional
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .stTabs [data-baseweb="tab-list"] { justify-content: center; gap: 20px; border-bottom: 2px solid #f0f2f6; }
    .stTabs [data-baseweb="tab"] { font-size: 16px; font-weight: 600; }
    .login-header { text-align: center; margin-bottom: 2rem; }
    .stButton>button { border-radius: 8px; font-weight: 600; }
    .logout-btn { margin-top: 20px; }
</style>
""", unsafe_allow_html=True)

# 4. Gerenciador de Cookies
@st.cache_resource
def get_cookie_manager():
    # Usamos cache_resource para o componente não ser recriado a cada rerun
    return stx.CookieManager(key="cookie_manager_main_v6")

cookie_manager = get_cookie_manager()

# --- FUNÇÕES DE CONTROLE (Otimizadas) ---

def fazer_logout_definitivo():
    """Limpa cookies e estado de forma segura."""
    cookie_manager.delete("medplanner_auth")
    st.session_state.logado = False
    st.session_state.username = "guest"
    st.session_state.quer_sair = False
    # Limpa chaves de widgets para evitar AttributeError no próximo login
    for key in list(st.session_state.keys()):
        if key.endswith("_slider") or key.startswith("txt_"):
            del st.session_state[key]
    st.rerun()

def verificar_sessao_automatica():
    """Tenta recuperar a sessão via cookie."""
    # O componente de cookie precisa de um pequeno tempo para ser montado no browser
    auth_cookie = cookie_manager.get(cookie="medplanner_auth")
    
    if auth_cookie and not st.session_state.logado:
        st.session_state.logado = True
        st.session_state.username = auth_cookie
        st.session_state.u_nome = "Dr(a). " + auth_cookie.capitalize()
        st.rerun()

def fazer_login(u, nome_real):
    """Efetua login e persiste o cookie."""
    st.session_state.logado = True
    st.session_state.username = u
    st.session_state.u_nome = nome_real
    expires_at = datetime.now() + timedelta(days=30)
    cookie_manager.set("medplanner_auth", u, expires_at=expires_at)
    st.toast(f"Bem-vindo, {nome_real}!", icon="👋")
    time.sleep(0.5)
    st.rerun()

# --- INTERFACES ---

def tela_login():
    """Interface de Login e Cadastro."""
    from database import verificar_login, criar_usuario
    
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
                        else: st.error(f"Erro: {msg}")
                    else: st.warning("Preencha todos os campos.")

def app_principal():
    """Interface principal com Lazy Loading dos módulos."""
    # Logout Gate imediato
    if st.session_state.quer_sair:
        fazer_logout_definitivo()
        return

    try:
        # Lazy Imports: Só carregamos os módulos quando o usuário está logado
        # Isso previne que erros em módulos que o usuário não está vendo travem o login.
        from sidebar_v2 import render_sidebar
        from dashboard import render_dashboard
        from cronograma import render_cronograma
        from agenda import render_agenda
        from mentor import render_mentor
        from simulado import render_simulado_real
        from caderno_erros import render_caderno_erros
        from videoteca import render_videoteca
        from perfil import render_perfil
        from banco_questoes import render_banco_questoes

        render_sidebar(cookie_manager)
        
        # Verificação dupla após sidebar (caso o botão sair tenha sido clicado lá)
        if st.session_state.quer_sair:
            fazer_logout_definitivo()
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
                time.sleep(1)
                st.rerun()

        # Abas
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
        if st.session_state.quer_sair:
            fazer_logout_definitivo()
        else:
            st.error("Erro ao carregar os módulos do sistema.")
            with st.expander("Detalhes técnicos do erro"):
                st.code(traceback.format_exc())

# --- ORQUESTRAÇÃO FINAL ---

if st.session_state.logado:
    app_principal()
else:
    # Mostramos um loader leve enquanto tentamos ler o cookie
    with st.spinner("Verificando sessão..."):
        verificar_sessao_automatica()
    
    # Se após verificar o cookie ele ainda não estiver logado, mostra login
    if not st.session_state.logado:
        tela_login()