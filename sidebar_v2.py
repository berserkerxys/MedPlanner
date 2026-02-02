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
    # A função get_status_gamer já deve retornar a meta salva no banco (tabela perfil_gamer)
    status, _ = get_status_gamer(u, nonce)
    prog = get_progresso_hoje(u, nonce)
    
    # 2. Define o valor inicial da meta
    # Prioridade: 1. Banco de dados -> 2. Padrão 50
    # Importante: Convertemos para int para evitar erros no slider
    meta_banco = int(status.get('meta_diaria', 50))
    
    # Lógica de Estado do Slider:
    # Se o slider ainda não existe na sessão (primeiro carregamento ou após login), 
    # inicializamos com o valor do banco.
    # Se já existe, verificamos se é diferente do banco (pode ter sido atualizado em outra aba)
    # e sincronizamos se necessário, mas com cuidado para não "travar" a interface.
    if "sb_meta_slider" not in st.session_state:
        st.session_state.sb_meta_slider = meta_banco
    
    # Se o valor no banco mudou (ex: alterado na aba Perfil), atualizamos o slider
    # (Opcional, mas bom para consistência se você tem o slider em dois lugares)
    if meta_banco != st.session_state.sb_meta_slider:
         # Apenas atualiza se a diferença for externa, não enquanto o usuário arrasta
         # Como st.rerun() recarrega tudo, assumimos que o banco é a fonte da verdade ao carregar
         pass 

    with st.sidebar:
        # --- Resumo Compacto ---
        st.markdown(f"**Dr(a). {st.session_state.get('u_nome', u)}**")
        st.caption(f"{status['titulo']} (Nv. {status['nivel']})")
        
        # --- LÓGICA VISUAL ---
        # Usamos o valor que está NO BANCO como referência principal para a barra,
        # ou o valor local se o usuário estiver arrastando agora (feedback instantâneo)
        meta_visual = st.session_state.sb_meta_slider if st.session_state.sb_meta_slider > 0 else 1
        perc = min(prog / meta_visual, 1.0)
        
        st.progress(perc, text=f"Hoje: {prog}/{meta_visual}")
        
        st.divider()
        
        # --- Meta Diária (Slider) ---
        def on_meta_change():
            # Esta função roda quando o usuário SOLTA o slider
            novo_valor = st.session_state.sb_meta_slider
            # Salva no banco para este usuário específico
            update_meta_diaria(u, novo_valor)
            st.toast(f"Meta salva: {novo_valor}", icon="💾")

        st.markdown("### 🎯 Meta Diária")
        
        # O segredo aqui é usar 'value=meta_banco' para que, ao recarregar a página (F5/Login),
        # ele pegue o valor que foi salvo no banco, e não um valor fixo ou antigo da sessão.
        # Mas precisamos garantir que a chave 'sb_meta_slider' seja atualizada.
        
        st.slider(
            "Ajuste seu alvo:",
            min_value=10,
            max_value=200,
            # Se a sessão já tem um valor (interação recente), usa ele. 
            # Senão, usa o do banco. Isso previne "pulos" estranhos.
            value=st.session_state.get("sb_meta_slider", meta_banco),
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
            # Limpa chaves de sessão específicas para evitar "sujeira" no próximo login
            keys_to_clear = ["sb_meta_slider", "video_limit", "chat_history"]
            for k in keys_to_clear:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()