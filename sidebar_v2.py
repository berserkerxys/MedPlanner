import streamlit as st
import time
from database import (
    get_lista_assuntos_nativa,
    registrar_estudo,
    registrar_simulado,
    get_progresso_hoje,
    get_status_gamer,
    update_meta_diaria
)

def render_sidebar(cookie_manager):
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    status, _ = get_status_gamer(u, nonce)
    prog = get_progresso_hoje(u, nonce)
    meta_banco = int(status.get('meta_diaria', 50))
    
    if "sb_meta_slider" not in st.session_state:
        st.session_state.sb_meta_slider = meta_banco

    with st.sidebar:
        st.markdown(f"**Dr(a). {st.session_state.get('u_nome', u)}**")
        st.caption(f"{status['titulo']} (Nv. {status['nivel']})")
        
        meta_atual = st.session_state.sb_meta_slider if st.session_state.sb_meta_slider > 0 else 1
        perc = min(prog / meta_atual, 1.0)
        st.progress(perc, text=f"Hoje: {prog}/{meta_atual}")
        
        st.divider()
        
        def on_meta_change():
            novo_valor = st.session_state.sb_meta_slider
            update_meta_diaria(u, novo_valor)
            if "pf_meta_slider" in st.session_state:
                st.session_state.pf_meta_slider = novo_valor
            st.toast(f"Meta definida: {novo_valor}", icon="🎯")

        st.markdown("### 🎯 Meta Diária")
        st.slider("Alvo:", 10, 200, step=5, key="sb_meta_slider", on_change=on_meta_change, label_visibility="collapsed")
        
        st.divider()
        
        # Registro Rápido
        st.markdown("### ⚡ Registro Rápido")
        tab_a, tab_s = st.tabs(["Aula", "Simulado"])
        
        with tab_a:
            lista = get_lista_assuntos_nativa()
            assunto = st.selectbox("Tema:", lista, index=None, placeholder="Tema...")
            tipo_estudo = st.radio("Fase:", ["Pre-Aula", "Pos-Aula"], horizontal=True)
            c1, c2 = st.columns(2)
            ac = c1.number_input("Acertos", 0, 300, 0, key="sb_ac")
            tot = c2.number_input("Total", 1, 300, 10, key="sb_tot")
            
            if st.button("✅ Salvar", use_container_width=True, key="btn_sb"):
                if assunto:
                    msg = registrar_estudo(u, assunto, ac, tot, tipo_estudo=tipo_estudo, srs=False)
                    st.success(msg)
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.warning("Escolha o tema!")

        with tab_s:
            with st.expander("Lançar Notas por Área"):
                areas_map = {"Preventiva": "Preventiva", "Cirurgia": "Cirurgia", "Clínica Médica": "Clínica", "Ginecologia e Obstetrícia": "G.O", "Pediatria": "Pediatria"}
                dados = {}
                for area_full, label in areas_map.items():
                    st.markdown(f"**{area_full}**")
                    c_a, c_t = st.columns(2)
                    a = c_a.number_input(f"Acertos {label}", 0, 100, 0, key=f"sba_{area_full}")
                    t = c_t.number_input(f"Total {label}", 0, 100, 0, key=f"sbt_{area_full}")
                    dados[area_full] = {'acertos': a, 'total': t}
                if st.button("💾 Gravar Simulado", use_container_width=True):
                    msg = registrar_simulado(u, dados)
                    st.success(msg); time.sleep(0.5); st.rerun()
        
        st.divider()
        
        # --- CORREÇÃO DO LOGOUT ---
        if st.button("🚪 Sair (Logout)", use_container_width=True):
            # 1. Deleta o cookie do navegador para impedir o auto-login
            cookie_manager.delete("medplanner_auth")
            # 2. Altera o estado da sessão
            st.session_state.logado = False
            # 3. Limpa chaves para evitar conflitos no próximo login
            keys_to_clear = ["sb_meta_slider", "pf_meta_slider"]
            for k in keys_to_clear:
                if k in st.session_state: del st.session_state[k]
            # 4. Força o recarregamento
            st.rerun()