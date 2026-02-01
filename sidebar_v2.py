import streamlit as st
import time
from database import (
    get_lista_assuntos_nativa,
    registrar_estudo,
    registrar_simulado,
    get_progresso_hoje,
    get_status_gamer
)

def render_sidebar():
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    # Dados rápidos apenas para feedback visual
    status, _ = get_status_gamer(u, nonce)
    prog = get_progresso_hoje(u, nonce)
    meta = status['meta_diaria']
    
    with st.sidebar:
        # Mini-Resumo do Perfil
        st.markdown(f"### Dr(a). {st.session_state.get('u_nome', u)}")
        st.caption(f"Nível {status['nivel']} • {status['titulo']}")
        
        # Barra de progresso diária compacta
        perc = min(prog/meta, 1.0) if meta > 0 else 0
        st.progress(perc, text=f"Hoje: {prog}/{meta}")
        
        st.divider()
        
        # ÁREA DE REGISTRO RÁPIDO (Prioridade na Sidebar)
        st.markdown("### ⚡ Registro Rápido")
        
        tab_aula, tab_sim = st.tabs(["Aula", "Simulado"])
        
        # Aba Aula (Registro Individual)
        with tab_aula:
            lista = get_lista_assuntos_nativa()
            assunto = st.selectbox("Tema:", lista, placeholder="Selecione...", index=None, label_visibility="collapsed")
            
            c1, c2 = st.columns(2)
            ac = c1.number_input("Acertos", 0, 300, 0, key="sb_ac")
            tot = c2.number_input("Total", 1, 300, 10, key="sb_tot")
            
            if st.button("✅ Salvar", use_container_width=True, key="btn_save_sb"):
                if assunto:
                    msg = registrar_estudo(u, assunto, ac, tot)
                    st.success(msg)
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.warning("Selecione um tema!")

        # Aba Simulado (Registro em Lote)
        with tab_sim:
            with st.expander("Lançar Notas por Área"):
                areas = ["Preventiva", "Cirurgia", "Clínica Médica", "Ginecologia e Obstetrícia", "Pediatria"]
                dados = {}
                for ar in areas:
                    st.caption(ar)
                    c_a, c_t = st.columns(2)
                    a = c_a.number_input("Ac", 0, 100, 0, key=f"sba_{ar}")
                    t = c_t.number_input("Tot", 0, 100, 0, key=f"sbt_{ar}")
                    dados[ar] = {'acertos': a, 'total': t}
                
                if st.button("💾 Gravar Simulado", use_container_width=True):
                    msg = registrar_simulado(u, dados)
                    st.success(msg)
                    time.sleep(0.5)
                    st.rerun()
        
        st.divider()
        st.info("💡 **Dica:** Acesse a aba **PERFIL** no menu principal para ver suas conquistas e ajustar metas.")