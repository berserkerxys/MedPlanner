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
    
    # Dados em tempo real
    status, _ = get_status_gamer(u, nonce)
    q_hoje = get_progresso_hoje(u, nonce)
    
    with st.sidebar:
        st.markdown(f"### 🩺 Dr. {st.session_state.u_nome}")
        
        if status:
            c1, c2 = st.columns([1, 2])
            c1.markdown(f"**Lvl {status['nivel']}**")
            c2.progress(status['xp_atual']/1000)
            
            st.divider()
            
            # Meta Diária Visual
            meta = status['meta_diaria']
            prog = min(q_hoje / meta, 1.0) if meta > 0 else 0
            st.markdown(f"🎯 **Meta: {q_hoje} / {meta}**")
            st.progress(prog)
            if q_hoje >= meta: st.success("🔥 Objetivo Batido!")

            with st.expander("⚙️ Ajustar Meta"):
                nm = st.number_input("Novo Alvo:", 1, 500, meta)
                if st.button("Atualizar"):
                    update_meta_diaria(u, nm)
                    st.rerun()

        st.divider()
        st.markdown("📝 **Registar**")
        tipo = st.selectbox("Atividade:", ["Aula Tema", "Simulado Completo", "Banco Geral"], key="sb_type")
        
        if tipo == "Aula Tema":
            t = st.selectbox("Assunto:", get_lista_assuntos_nativa(), index=None)
            c1, c2 = st.columns(2)
            ac = c1.number_input("Hits", 0, 999, 8)
            tt = c2.number_input("Total", 1, 999, 10)
            if st.button("💾 Salvar", use_container_width=True, type="primary"):
                if t: st.toast(registrar_estudo(u, t, ac, tt))
                else: st.error("Escolha o tema!")

        elif tipo == "Simulado Completo":
            with st.expander("📍 Detalhes por Área", expanded=True):
                areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
                res = {}
                for a in areas:
                    st.markdown(f"**{a}**")
                    c1, c2 = st.columns(2)
                    tot = c1.number_input(f"Tot {a}", 0, 100, 20, key=f"t_{a}")
                    acc = c2.number_input(f"Ac {a}", 0, tot, 15, key=f"a_{a}")
                    res[a] = {"total": tot, "acertos": acc}
                if st.button("💾 Gravar Simulado", use_container_width=True, type="primary"):
                    st.toast(registrar_simulado(u, res))

        elif tipo == "Banco Geral":
            c1, c2 = st.columns(2)
            tot = c1.number_input("Total", 1, 1000, 50)
            acc = c2.number_input("Acertos", 0, tot, 35)
            if st.button("💾 Salvar Banco", use_container_width=True, type="primary"):
                st.toast(registrar_estudo(u, "Banco Geral - Livre", acc, tot))

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logado = False
            st.rerun()