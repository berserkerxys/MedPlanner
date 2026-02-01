import streamlit as st
from datetime import datetime
from database import (
    get_progresso_hoje, get_lista_assuntos_nativa, 
    registrar_estudo, registrar_simulado
)

def render_sidebar():
    """Gerencia a barra lateral com inputs detalhados de Simulado."""
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    with st.sidebar:
        st.markdown(f"### 🩺 Dr. {st.session_state.u_nome}")
        q_hoje = get_progresso_hoje(u, nonce)
        st.metric("Hoje", f"{q_hoje} q", delta=f"{q_hoje - 50} meta")
        
        st.divider()
        nav = st.radio("Menu Principal:", ["📊 Performance", "📅 Agenda SRS", "📚 Videoteca", "👤 Meu Perfil"], label_visibility="collapsed")
        
        st.divider()
        st.markdown("📝 **Registar Atividade**")
        tipo = st.selectbox("O que você fez?", ["Aula por Tema", "Simulado Completo"], key="sb_type")
        
        if tipo == "Aula por Tema":
            t = st.selectbox("Assunto:", get_lista_assuntos_nativa(), index=None, placeholder="Selecione o tema...")
            c1, c2 = st.columns(2)
            acc = c1.number_input("Hits", 0, 300, 8, key="sb_hits")
            tot = c2.number_input("Total", 1, 300, 10, key="sb_tot")
            if st.button("💾 Salvar Estudo", use_container_width=True, type="primary"):
                if t: st.toast(registrar_estudo(u, t, acc, tot))
                else: st.error("Selecione o tema!")

        elif tipo == "Simulado Completo":
            with st.expander("📝 Dados do Simulado", expanded=True):
                areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
                res_sim = {}
                for a in areas:
                    st.markdown(f"**{a}**")
                    c1, c2 = st.columns(2)
                    # Agora permite definir total e acertos por área
                    a_tot = c1.number_input("Qtd", 1, 100, 20, key=f"tot_{a}")
                    a_acc = c2.number_input("Ac", 0, a_tot, 15, key=f"acc_{a}")
                    res_sim[a] = {"total": a_tot, "acertos": a_acc}
                
                if st.button("💾 Gravar Simulado", use_container_width=True, type="primary"):
                    st.toast(registrar_simulado(u, res_sim))

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logado = False
            st.rerun()
            
    return nav