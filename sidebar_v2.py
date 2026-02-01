import streamlit as st
from datetime import datetime
from database import (
    get_progresso_hoje, get_lista_assuntos_nativa, 
    registrar_estudo, registrar_simulado
)

def render_sidebar():
    """Função de barra lateral fixa e segura."""
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    with st.sidebar:
        st.markdown(f"### 🩺 Dr. {st.session_state.u_nome}")
        
        # Métrica Real-time
        q_hoje = get_progresso_hoje(u, nonce)
        st.metric("Hoje", f"{q_hoje} questões", delta=f"{q_hoje - 50} meta")
        
        st.divider()
        
        # Menu Limpo
        nav = st.radio("Menu:", ["📊 Performance", "📅 Agenda SRS", "📚 Videoteca", "👤 Meu Perfil"], label_visibility="collapsed")
        
        st.divider()
        st.markdown("📝 **Registrar Atividade**")
        tipo = st.selectbox("O que fez?", ["Aula Tema", "Simulado Geral"], key="sb_type")
        
        if tipo == "Aula Tema":
            t = st.selectbox("Assunto:", get_lista_assuntos_nativa(), index=None, placeholder="Selecione...")
            c1, c2 = st.columns(2)
            acc = c1.number_input("Hits", 0, 200, 8, key="sb_acc")
            tot = c2.number_input("Total", 1, 200, 10, key="sb_tot")
            if st.button("💾 Salvar Estudo", use_container_width=True, type="primary"):
                if t: st.toast(registrar_estudo(u, t, acc, tot))
                else: st.error("Escolha o tema!")

        elif tipo == "Simulado Geral":
            with st.expander("Dados do Simulado", expanded=False):
                areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
                res_sim = {}
                for a in areas:
                    # BLINDAGEM: Força o total de 20 questões por área
                    val = st.number_input(f"{a} (Ac)", 0, 20, 15, key=f"sb_sim_{a}")
                    res_sim[a] = {"total": 20, "acertos": val}
                
                if st.button("💾 Gravar Simulado", use_container_width=True, type="primary"):
                    st.toast(registrar_simulado(u, res_sim))

        st.divider()
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.logado = False
            st.rerun()
            
    return nav