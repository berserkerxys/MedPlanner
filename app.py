# app.py
import streamlit as st
import time
from datetime import datetime, timedelta

# Configuração de página no topo
st.set_page_config(page_title="MedPlanner Elite", page_icon="🩺", layout="wide")

# CSS Responsivo e de Performance
st.markdown("""
<style>
    .block-container { padding: 1rem; max-width: 100%; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; overflow-x: auto; }
    /* Esconde elementos enquanto carrega */
    .loading-overlay {
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: white; z-index: 9999; display: flex;
        flex-direction: column; align-items: center; justify-content: center;
    }
</style>
""", unsafe_allow_html=True)

# Gerenciador de Estado Inicial
if 'logado' not in st.session_state: st.session_state.logado = False
if 'ready' not in st.session_state: st.session_state.ready = False

# --- FUNÇÃO DE CARREGAMENTO INICIAL (BOOTSTRAP) ---
def inicializar_aplicacao():
    """Tela de loading que pré-carrega dados pesados na cache."""
    placeholder = st.empty()
    with placeholder.container():
        st.markdown("""
            <div style='text-align:center; margin-top: 20%;'>
                <h1 style='font-size: 50px;'>🩺</h1>
                <h2>Sincronizando MedPlanner...</h2>
                <p>Otimizando seu cronograma e banco de dados.</p>
            </div>
        """, unsafe_allow_html=True)
        
        progress_bar = st.progress(0)
        
        # Passo 1: Conexão DB e Cache de Aulas
        import database
        database._ensure_local_db()
        progress_bar.progress(40)
        time.sleep(0.3)
        
        # Passo 2: Carregamento de dados MedCof (Cache)
        database._carregar_dados_medcof()
        progress_bar.progress(80)
        time.sleep(0.2)
        
        # Passo 3: Finalização
        st.session_state.ready = True
        progress_bar.progress(100)
        time.sleep(0.3)
    
    placeholder.empty()

# --- LÓGICA DE LOGIN ---
def tela_login():
    import database
    st.markdown("<div style='text-align:center;'><h1>🩺 MedPlanner</h1><p>Acesse sua conta para continuar</p></div>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        with st.container(border=True):
            u = st.text_input("Usuário")
            p = st.text_input("Senha", type="password")
            if st.button("Entrar", type="primary", use_container_width=True):
                ok, nome = database.verificar_login(u, p)
                if ok:
                    st.session_state.logado = True
                    st.session_state.username = u
                    st.session_state.u_nome = nome
                    st.rerun()
                else:
                    st.error("Credenciais inválidas")

# --- APP PRINCIPAL (MODULAR) ---
def app_principal():
    # Só renderiza a sidebar UMA VEZ
    from sidebar_v2 import render_sidebar
    render_sidebar()

    st.markdown("<h3 style='text-align:center;'>MedPlanner Elite</h3>", unsafe_allow_html=True)

    # Abas - O conteúdo dentro das abas só será importado ao clicar
    abas = st.tabs([
        "📊 DASHBOARD", "🗂️ CRONOGRAMA", "🏦 BANCO", "🧠 ERROS", "👤 PERFIL"
    ])

    with abas[0]:
        # Lazy Import: Dashboard
        from dashboard import render_dashboard
        render_dashboard(None)
    
    with abas[1]:
        # Lazy Import: Cronograma
        from cronograma import render_cronograma
        render_cronograma(None)
        
    with abas[2]:
        # Lazy Import: Banco
        from banco_questoes import render_banco_questoes
        render_banco_questoes(None)

    with abas[3]:
        from caderno_erros import render_caderno_erros
        render_caderno_erros(None)

    with abas[4]:
        from perfil import render_perfil
        render_perfil(None)

# --- CONTROLE DE FLUXO ---
if not st.session_state.logado:
    tela_login()
elif not st.session_state.ready:
    inicializar_aplicacao()
    st.rerun()
else:
    app_principal()