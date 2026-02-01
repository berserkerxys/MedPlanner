import streamlit as st
from datetime import datetime
from database import (
    get_status_gamer, get_lista_assuntos_nativa, 
    registrar_estudo, registrar_simulado, update_meta_diaria,
    get_progresso_hoje
)

def render_sidebar():
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    status, _ = get_status_gamer(u, nonce)
    q_hoje = get_progresso_hoje(u, nonce)
    
    with st.sidebar:
        st.markdown(f"### 🩺 Dr. {st.session_state.u_nome}")
        
        if status:
            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown(f"#### Lvl {status['nivel']}")
            with col2:
                st.progress(status['xp_atual']/1000)
                st.caption(f"XP: {status['xp_atual']}/1000")
            
            st.divider()
            
            # --- META DIÁRIA AO VIVO ---
            meta = status['meta_diaria']
            progresso = min(q_hoje / meta, 1.0) if meta > 0 else 0
            st.markdown(f"🎯 **Meta Diária: {q_hoje} / {meta} q**")
            st.progress(progresso)
            
            with st.expander("⚙️ Ajustar Meta"):
                nova_meta = st.number_input("Objetivo Diário:", 1, 500, meta)
                if st.button("Salvar Meta"):
                    if update_meta_diaria(u, nova_meta):
                        st.rerun()

        st.divider()
        st.markdown("📝 **Registar Atividade**")
        tipo = st.selectbox("Tipo:", ["Aula Tema", "Simulado Completo", "Banco Geral"], key="sb_type")
        
        if tipo == "Aula Tema":
            t = st.selectbox("Assunto:", get_lista_assuntos_nativa(), index=None, placeholder="Escolha...")
            c1, c2 = st.columns(2)
            acc = c1.number_input("Hits", 0, 300, 8)
            tot = c2.number_input("Total", 1, 300, 10)
            if st.button("💾 Salvar Aula", use_container_width=True, type="primary"):
                if t: st.toast(registrar_estudo(u, t, acc, tot))
                else: st.error("Escolha o tema!")

        elif tipo == "Simulado Completo":
            with st.expander("📍 Acertos vs Total", expanded=True):
                areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
                res_sim = {}
                for a in areas:
                    st.markdown(f"**{a}**")
                    c1, c2 = st.columns(2)
                    s_tot = c1.number_input("Qtd", 1, 100, 20, key=f"stot_{a}")
                    s_acc = c2.number_input("Ac", 0, s_tot, 15, key=f"sacc_{a}")
                    res_sim[a] = {"total": s_tot, "acertos": s_acc}
                if st.button("💾 Gravar Simulado", use_container_width=True, type="primary"):
                    st.toast(registrar_simulado(u, res_sim))

        elif tipo == "Banco Geral":
            c1, c2 = st.columns(2)
            bg_acc = c1.number_input("Acertos", 0, 1000, 35)
            bg_tot = c2.number_input("Total", 1, 1000, 50)
            if st.button("💾 Salvar Banco", use_container_width=True, type="primary"):
                st.toast(registrar_estudo(u, "Banco Geral - Livre", bg_acc, bg_tot))

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logado = False
            st.rerun()