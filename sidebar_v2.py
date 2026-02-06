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

def render_sidebar():
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
            nv = st.session_state.sb_meta_slider
            update_meta_diaria(u, nv)
            if "pf_meta_slider" in st.session_state: st.session_state.pf_meta_slider = nv
            st.toast(f"Meta: {nv}", icon="🎯")

        st.markdown("### 🎯 Meta Diária")
        st.slider("Alvo:", 10, 200, step=5, key="sb_meta_slider", on_change=on_meta_change, label_visibility="collapsed")
        
        st.divider()
        
        st.markdown("### ⚡ Registro Rápido")
        
        tab_a, tab_s = st.tabs(["Aula", "Simulado"])
        
        with tab_a:
            # Formulário para evitar reload a cada clique no '+' ou '-'
            with st.form("form_registro_aula"):
                lista = get_lista_assuntos_nativa()
                assunto = st.selectbox("Tema:", lista, index=None, label_visibility="collapsed", placeholder="Tema...")
                tipo_estudo = st.radio("Fase:", ["Pre-Aula", "Pos-Aula"], horizontal=True, label_visibility="collapsed")
                
                c1, c2 = st.columns(2)
                ac = c1.number_input("Acertos", 0, 300, 0)
                tot = c2.number_input("Total", 1, 300, 10)
                
                # Botão de submissão do formulário
                submitted = st.form_submit_button("✅ Salvar", use_container_width=True)
                
                if submitted:
                    if assunto:
                        msg = registrar_estudo(u, assunto, ac, tot, tipo_estudo=tipo_estudo, srs=False)
                        st.success(msg)
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.warning("Escolha o tema!")

        with tab_s:
            with st.expander("Lançar Notas"):
                # Formulário para simulado também
                with st.form("form_registro_simulado"):
                    areas_map = {"Preventiva": "Preventiva", "Cirurgia": "Cirurgia", "Clínica Médica": "Clínica", "Ginecologia e Obstetrícia": "G.O/Obst", "Pediatria": "Pediatria"}
                    dados = {}
                    for f, s in areas_map.items():
                        st.markdown(f"**{f}**")
                        c_a, c_t = st.columns(2)
                        a = c_a.number_input(f"Ac {s}", 0, key=f"sa_{f}")
                        t = c_t.number_input(f"Tt {s}", 0, key=f"st_{f}")
                        dados[f] = {'acertos': a, 'total': t}
                        st.markdown("---")
                    
                    if st.form_submit_button("💾 Gravar", use_container_width=True):
                        registrar_simulado(u, dados)
                        st.success("Salvo!")
                        time.sleep(0.5)
                        st.rerun()
        
        st.divider()
        if st.button("🚪 Sair (Logout)", use_container_width=True):
            st.session_state.logado = False
            for k in ["sb_meta_slider", "pf_meta_slider", "video_limit", "chat_history"]:
                if k in st.session_state: del st.session_state[k]
            st.rerun()