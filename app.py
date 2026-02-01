# app.py
import streamlit as st
import traceback
import sys
import time

st.set_page_config(page_title="MedPlanner Elite", page_icon="🩺", layout="wide")

# Styling global para esconder o menu padrão e ajustar abas
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .stTabs [data-baseweb="tab-list"] { justify-content: center; gap: 20px; border-bottom: 2px solid #f0f2f6; }
    .stTabs [data-baseweb="tab"] { font-size: 16px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# Imports seguros com tratamento de erro
_import_ok = True
_import_exc = None
try:
    import pandas as pd
    from datetime import datetime
    
    # Imports locais
    from sidebar_v2 import render_sidebar
    from database import get_resumo, salvar_resumo, verificar_login, criar_usuario, get_supabase, get_lista_assuntos_nativa
    from perfil import render_perfil # Novo módulo de perfil
except Exception as e:
    _import_ok = False
    _import_exc = traceback.format_exc()

if not _import_ok:
    st.title("⛔ Erro ao iniciar a aplicação")
    st.error("Falha na importação dos módulos. Verifique o log abaixo.")
    st.code(_import_exc)
    st.stop()

# Inicialização de Sessão Segura
if 'logado' not in st.session_state: st.session_state.logado = False
if 'username' not in st.session_state: st.session_state.username = "guest"
if 'u_nome' not in st.session_state: st.session_state.u_nome = "Doutor(a)"
if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0

# Função Auxiliar de Resumos (mantida no app principal por simplicidade)
def render_resumos_ui(u):
    try:
        st.header("📝 Meus Resumos")
        areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
        
        tab_areas = st.tabs(areas)
        
        for i, area in enumerate(areas):
            with tab_areas[i]:
                txt_val = get_resumo(u, area)
                txt = st.text_area(f"Notas de {area}:", value=txt_val, height=400, key=f"t_{area}")
                
                c1, c2 = st.columns([1, 5])
                with c1:
                    if st.button(f"Salvar {area}", key=f"s_{area}", type="primary"):
                        if salvar_resumo(u, area, txt): 
                            st.toast("Resumo salvo com sucesso!", icon="✅")
    except Exception:
        st.error("Erro na UI de resumos")

# --- APLICAÇÃO PRINCIPAL ---
def app_principal():
    try:
        u = st.session_state.username
        
        # Renderiza a Sidebar simplificada
        render_sidebar()

        st.markdown("<h2 style='text-align:center;'>🩺 MEDPLANNER PRO</h2>", unsafe_allow_html=True)

        # Widget Pomodoro
        with st.expander("⏲️ Foco Pomodoro", expanded=False):
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                mode = st.radio("Modo:", ["Estudo (25m)", "Pausa (5m)"], horizontal=True)
                if st.button("🚀 Iniciar", key="pomodoro_start"):
                    total_seconds = 25*60 if "Estudo" in mode else 5*60
                    st.session_state._pomodoro_remaining = total_seconds
                    st.rerun()

            if st.session_state.get("_pomodoro_remaining", 0) > 0:
                s = st.session_state["_pomodoro_remaining"]
                m, sec = divmod(s, 60)
                st.markdown(f"<h1 style='text-align:center;'>{m:02d}:{sec:02d}</h1>", unsafe_allow_html=True)
                st.session_state["_pomodoro_remaining"] = max(0, s-1)
                time.sleep(1)
                st.rerun()

        # Navegação Principal
        abas = st.tabs(["📊 PERFORMANCE", "📅 AGENDA", "📚 VIDEOTECA", "📝 RESUMOS", "🗂️ CRONOGRAMA", "👤 PERFIL"])
        
        with abas[0]:
            from dashboard import render_dashboard
            render_dashboard(None)
        with abas[1]:
            from agenda import render_agenda
            render_agenda(None)
        with abas[2]:
            from videoteca import render_videoteca
            render_videoteca(None)
        with abas[3]:
            render_resumos_ui(u)
        with abas[4]:
            from cronograma import render_cronograma
            render_cronograma(None)
        with abas[5]:
            # Aba dedicada ao Perfil e Conquistas
            render_perfil(None)

    except Exception:
        st.error("Erro crítico durante a execução do app")
        st.code(traceback.format_exc())

# --- TELA DE LOGIN ---
def tela_login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    
    with c2:
        with st.container(border=True):
            st.markdown("<h2 style='text-align:center;'>🔐 Acesso MedPlanner</h2>", unsafe_allow_html=True)
            u = st.text_input("Usuário", key="login_user")
            p = st.text_input("Senha", type="password", key="login_pass")
            
            if st.button("Entrar", type="primary", use_container_width=True):
                ok, nome = verificar_login(u, p)
                if ok:
                    st.session_state.logado = True
                    st.session_state.username = u
                    st.session_state.u_nome = nome
                    st.toast(f"Bem-vindo, {nome}!", icon="👋")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(nome)

# Entry Point
if st.session_state.logado:
    app_principal()
else:
    tela_login()