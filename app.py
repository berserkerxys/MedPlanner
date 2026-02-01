# app.py (versão com diagnóstico e captura de erros)
# Substitua o app.py atual por este para coletar erros e diagnosticar a tela em branco.
import streamlit as st
import traceback
import sys

st.set_page_config(page_title="MedPlanner Elite", page_icon="🩺", layout="wide")

# Styling (mantive seu CSS)
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .stTabs [data-baseweb="tab-list"] { justify-content: center; gap: 20px; border-bottom: 2px solid #f0f2f6; }
    .stTabs [data-baseweb="tab"] { font-size: 16px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# TRY IMPORTS: captura falhas de import e mostra o traceback na página (evita tela branca)
_import_ok = True
_import_exc = None
try:
    import pandas as pd
    import time
    from datetime import datetime
    # imports do seu projeto (podem levantar exceções)
    from sidebar_v2 import render_sidebar
    from database import get_resumo, salvar_resumo, verificar_login, criar_usuario, get_supabase, get_lista_assuntos_nativa
    # imports tardios usados nas abas
    # (não importamos dashboard/agenda/videoteca aqui para evitar ciclos na importação;
    #  importaremos dentro dos blocos que executam)
except Exception as e:
    _import_ok = False
    _import_exc = traceback.format_exc()

# Mostrar erro de import se houver
if not _import_ok:
    st.title("⛔ Erro ao iniciar a aplicação")
    st.error("Houve uma exceção durante a importação dos módulos. O trace completo está abaixo.")
    st.code(_import_exc)
    # Exibir informações úteis para debug rápido
    st.markdown("Verifique as funções exportadas em database.py e se todos os arquivos existem.")
    st.stop()

# Garante chaves em session_state para evitar KeyError laterais
if 'logado' not in st.session_state: st.session_state.logado = False
if 'username' not in st.session_state: st.session_state.username = "guest"
if 'data_nonce' not in st.session_state: st.session_state.data_nonce = 0

# Pequeno painel de diagnóstico no topo (útil para entender por que a tela pode ficar vazia)
with st.expander("🔧 Diagnóstico (apenas dev)", expanded=False):
    try:
        st.write("Hora do servidor:", datetime.now().isoformat())
        sup = get_supabase()
        st.write("Supabase disponível?", bool(sup))
    except Exception as e:
        st.write("Erro ao checar Supabase:")
        st.code(traceback.format_exc())
    try:
        la = get_lista_assuntos_nativa()
        st.write("Assuntos carregados (sample):", la[:10] if isinstance(la, list) else str(type(la)))
    except Exception:
        st.write("Erro ao chamar get_lista_assuntos_nativa():")
        st.code(traceback.format_exc())

# Funções auxiliares locais (mantive a sua lógica do app principal, mas com captura de exceções)
def render_resumos_ui(u):
    try:
        st.header("📝 Meus Resumos")
        areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
        for area in areas:
            with st.expander(f"📘 {area}", expanded=False):
                txt = st.text_area(f"Notas de {area}:", value=get_resumo(u, area), height=300, key=f"t_{area}")
                if st.button(f"Salvar {area}", key=f"s_{area}"):
                    if salvar_resumo(u, area, txt): st.toast("Salvo!")
    except Exception:
        st.error("Erro na UI de resumos")
        st.code(traceback.format_exc())

def render_perfil_aluno():
    try:
        st.header("👤 Perfil do Aluno")
        st.write("Informações do perfil e gamificação aparecem aqui.")
    except Exception:
        st.error("Erro ao renderizar perfil")
        st.code(traceback.format_exc())

def app_principal():
    try:
        u = st.session_state.username
        render_sidebar()

        st.markdown("<h2 style='text-align:center;'>🩺 MEDPLANNER PRO</h2>", unsafe_allow_html=True)

        # Pomodoro Topo (mantive, mas pode bloquear se usado de modo síncrono; botão inicia loop)
        with st.expander("⏲️ Foco Pomodoro", expanded=False):
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                mode = st.radio("Modo:", ["Estudo (25m)", "Pausa (5m)"], horizontal=True)
                if st.button("🚀 Iniciar", key="pomodoro_start"):
                    # Uso mínimo: roda o contador em background via rerun para evitar bloqueio prolongado
                    total_seconds = 25*60 if "Estudo" in mode else 5*60
                    # armazenar no session_state para evitar loop bloqueante
                    st.session_state._pomodoro_remaining = total_seconds
                    st.experimental_rerun()

            # Se houver um contador em session_state, mostramos sem bloquear
            if st.session_state.get("_pomodoro_remaining", 0) > 0:
                s = st.session_state["_pomodoro_remaining"]
                m, sec = divmod(s, 60)
                st.markdown(f"<h1 style='text-align:center;'>{m:02d}:{sec:02d}</h1>", unsafe_allow_html=True)
                # diminui sem bloquear: subtrai 1 segundo a cada rerun curto (user verá atualização por rerun manual)
                st.session_state["_pomodoro_remaining"] = max(0, s-1)

        # Abas principais
        tabs = st.tabs(["📊 PERFORMANCE", "📅 AGENDA", "📚 VIDEOTECA", "📝 RESUMOS", "👤 PERFIL", "🗂️ CRONOGRAMA"])
        # Cada aba importa o módulo apenas quando acessada (reduz chance de import error inicial)
        with tabs[0]:
            try:
                from dashboard import render_dashboard
                render_dashboard(None)
            except Exception:
                st.error("Erro ao renderizar Dashboard")
                st.code(traceback.format_exc())
        with tabs[1]:
            try:
                from agenda import render_agenda
                render_agenda(None)
            except Exception:
                st.error("Erro ao renderizar Agenda")
                st.code(traceback.format_exc())
        with tabs[2]:
            try:
                from videoteca import render_videoteca
                render_videoteca(None)
            except Exception:
                st.error("Erro ao renderizar Videoteca")
                st.code(traceback.format_exc())
        with tabs[3]:
            render_resumos_ui(u)
        with tabs[4]:
            render_perfil_aluno()
        with tabs[5]:
            try:
                from cronograma import render_cronograma
                render_cronograma(None)
            except Exception:
                st.error("Erro ao renderizar Cronograma")
                st.code(traceback.format_exc())

    except Exception:
        st.error("Erro durante a execução do app principal")
        st.code(traceback.format_exc())

# Se o usuário está logado, mostra o app; caso contrário, mostra tela de login mínima
def tela_login():
    try:
        st.header("🔐 Login")
        u = st.text_input("Usuário:", value="", key="login_user")
        p = st.text_input("Senha:", value="", type="password", key="login_pass")
        if st.button("Entrar"):
            ok, nome = verificar_login(u, p)
            if ok:
                st.session_state.logado = True
                st.session_state.username = u
                st.toast(f"Bem-vindo {nome}!")
                st.experimental_rerun()
            else:
                st.error(nome)
    except Exception:
        st.error("Erro na tela de login")
        st.code(traceback.format_exc())

# Entry point (protegido)
try:
    if st.session_state.logado:
        app_principal()
    else:
        tela_login()
except Exception:
    st.error("Erro inesperado no fluxo principal")
    st.code(traceback.format_exc())