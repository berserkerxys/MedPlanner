import streamlit as st
from datetime import datetime
from database import (
    get_status_gamer, get_lista_assuntos_nativa, 
    registrar_estudo, registrar_simulado, update_meta_diaria
)

def render_sidebar():
    """Barra lateral modular com gamificação, metas e registros detalhados."""
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    # Busca status para UI
    status, df_m = get_status_gamer(u, nonce)
    
    with st.sidebar:
        st.markdown(f"### 🩺 Dr. {st.session_state.u_nome}")
        
        # 1. PERFIL GAMER
        if status:
            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown(f"<h2 style='margin:0;'>Lvl {status['nivel']}</h2>", unsafe_allow_html=True)
                st.caption(status['titulo'])
            with col2:
                st.caption(f"XP: {status['xp_atual']}/1000")
                st.progress(status['xp_atual']/1000)
            
            # Configuração de Meta
            with st.expander("⚙️ Ajustar Meta Diária"):
                nova_meta = st.number_input("Objetivo (questões):", 1, 500, status['meta_diaria'])
                if st.button("Salvar Meta"):
                    if update_meta_diaria(u, nova_meta):
                        st.success("Meta atualizada!")
                        st.rerun()

        st.divider()
        
        # 2. MENU NAVEGAÇÃO
        nav = st.radio("Navegação:", ["📊 Performance", "📅 Agenda SRS", "📚 Videoteca", "👤 Perfil"], label_visibility="collapsed")
        
        st.divider()
        
        # 3. REGISTROS (DETALHADOS)
        st.markdown("📝 **Registar Atividade**")
        tipo = st.selectbox("O que fez?", ["Aula por Tema", "Simulado Completo", "Banco Geral (Aleatório)"], key="sb_reg_type")
        
        if tipo == "Aula por Tema":
            t = st.selectbox("Assunto:", get_lista_assuntos_nativa(), index=None, placeholder="Escolha...")
            c1, c2 = st.columns(2)
            acc = c1.number_input("Hits", 0, 300, 8, key="sb_hits")
            tot = c2.number_input("Total", 1, 300, 10, key="sb_tot")
            if st.button("💾 Salvar Aula", use_container_width=True, type="primary"):
                if t: st.toast(registrar_estudo(u, t, acc, tot))
                else: st.error("Escolha o tema!")

        elif tipo == "Simulado Completo":
            with st.expander("📍 Áreas do Simulado", expanded=True):
                areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva"]
                res_sim = {}
                for a in areas:
                    st.markdown(f"**{a}**")
                    c1, c2 = st.columns(2)
                    a_tot = c1.number_input(f"Qtd {a}", 1, 100, 20, key=f"tot_{a}")
                    a_acc = c2.number_input(f"Ac {a}", 0, a_tot, 15, key=f"acc_{a}")
                    res_sim[a] = {"total": a_tot, "acertos": a_acc}
                
                if st.button("💾 Gravar Simulado", use_container_width=True, type="primary"):
                    st.toast(registrar_simulado(u, res_sim))

        elif tipo == "Banco Geral (Aleatório)":
            st.caption("Questões de bancos variados sem tema único.")
            c1, c2 = st.columns(2)
            bg_acc = c1.number_input("Acertos", 0, 1000, 35)
            bg_tot = c2.number_input("Total", 1, 1000, 50)
            if st.button("💾 Salvar Banco", use_container_width=True, type="primary"):
                st.toast(registrar_estudo(u, "Banco Geral - Livre", bg_acc, bg_tot))

        st.divider()
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.logado = False
            st.rerun()
            
    return nav