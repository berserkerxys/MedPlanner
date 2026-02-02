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
    
    # 1. Carrega dados frescos do banco para este usuário
    status, _ = get_status_gamer(u, nonce)
    prog = get_progresso_hoje(u, nonce)
    
    # 2. Define o valor inicial da meta vindo do banco
    # Se não houver nada no banco, usa 50 como padrão seguro
    meta_banco = int(status.get('meta_diaria', 50))
    
    # 3. Inicialização de Estado Robusta
    # Só inicializamos a chave da sessão SE ela não existir.
    # Isso impede que o slider seja resetado para 50 num rerun acidental.
    if "sb_meta_slider" not in st.session_state:
        st.session_state.sb_meta_slider = meta_banco
    
    # Se o valor do banco for diferente da sessão (ex: mudou no perfil), sincronizamos.
    # Mas só fazemos isso se a diferença for externa, para não atrapalhar a interação.
    # Como o slider atualiza o banco no on_change, podemos confiar no banco como fonte da verdade ao carregar.
    if meta_banco != st.session_state.sb_meta_slider:
         st.session_state.sb_meta_slider = meta_banco

    with st.sidebar:
        # --- Resumo Compacto ---
        st.markdown(f"**Dr(a). {st.session_state.get('u_nome', u)}**")
        st.caption(f"{status['titulo']} (Nv. {status['nivel']})")
        
        # --- LÓGICA VISUAL ---
        # Usa o valor da sessão para feedback imediato
        meta_visual = st.session_state.sb_meta_slider if st.session_state.sb_meta_slider > 0 else 1
        perc = min(prog / meta_visual, 1.0)
        
        st.progress(perc, text=f"Hoje: {prog}/{meta_visual}")
        
        st.divider()
        
        # --- Meta Diária (Slider) ---
        def on_meta_change():
            # Esta função roda quando o usuário SOLTA o slider
            novo_valor = st.session_state.sb_meta_slider
            
            # 1. Salva no banco
            update_meta_diaria(u, novo_valor)
            
            # 2. Sincroniza com slider do perfil (se existir na sessão)
            if "pf_meta_slider" in st.session_state:
                st.session_state.pf_meta_slider = novo_valor
                
            st.toast(f"Meta salva: {novo_valor}", icon="💾")

        st.markdown("### 🎯 Meta Diária")
        
        st.slider(
            "Ajuste seu alvo:",
            min_value=10,
            max_value=200,
            # O valor inicial do slider DEVE ser a chave da sessão
            value=st.session_state.sb_meta_slider,
            step=5,
            key="sb_meta_slider",
            on_change=on_meta_change,
            label_visibility="collapsed"
        )
        
        st.divider()
        
        # --- Registro Rápido ---
        st.markdown("### ⚡ Registro Rápido")
        
        tab_a, tab_s = st.tabs(["Aula", "Simulado"])
        
        with tab_a:
            lista = get_lista_assuntos_nativa()
            assunto = st.selectbox("Tema:", lista, index=None, label_visibility="collapsed", placeholder="Tema...")
            c1, c2 = st.columns(2)
            ac = c1.number_input("Acertos", 0, 300, 0, key="sb_ac")
            tot = c2.number_input("Total", 1, 300, 10, key="sb_tot")
            
            if st.button("✅ Salvar", use_container_width=True, key="btn_sb"):
                if assunto:
                    msg = registrar_estudo(u, assunto, ac, tot)
                    st.success(msg)
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.warning("Escolha o tema!")

        with tab_s:
            with st.expander("Lançar Notas por Área"):
                # Mapeamento para labels mais bonitos
                areas_map = {
                    "Preventiva": "Preventiva",
                    "Cirurgia": "Cirurgia",
                    "Clínica Médica": "Clínica",
                    "Ginecologia e Obstetrícia": "G.O/Obstetrícia",
                    "Pediatria": "Pediatria"
                }
                
                dados = {}
                for area_full, label_short in areas_map.items():
                    st.markdown(f"**{area_full}**")
                    c_a, c_t = st.columns(2)
                    a = c_a.number_input(f"Acertos ({label_short})", 0, 100, 0, key=f"sba_{area_full}")
                    t = c_t.number_input(f"Total ({label_short})", 0, 100, 0, key=f"sbt_{area_full}")
                    dados[area_full] = {'acertos': a, 'total': t}
                    st.markdown("---")
                
                if st.button("💾 Gravar Simulado", use_container_width=True):
                    msg = registrar_simulado(u, dados)
                    st.success(msg)
                    time.sleep(0.5)
                    st.rerun()
        
        st.divider()
        
        # --- Botão de Logout ---
        if st.button("🚪 Sair (Logout)", use_container_width=True):
            st.session_state.logado = False
            # Limpa chaves de sessão específicas
            for k in ["sb_meta_slider", "pf_meta_slider", "video_limit", "chat_history"]:
                if k in st.session_state: del st.session_state[k]
            st.rerun()