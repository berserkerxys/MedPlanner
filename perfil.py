import streamlit as st
import time
from database import (
    get_status_gamer,
    get_conquistas_e_stats,
    update_meta_diaria,
    get_progresso_hoje
)

def render_perfil(conn_ignored):
    st.header("👤 Perfil do Aluno")
    
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    # Carrega dados
    status, _ = get_status_gamer(u, nonce)
    total_q_global, conquistas, proximo_nivel = get_conquistas_e_stats(u)
    
    # --- 1. CABEÇALHO DO AVATAR ---
    with st.container(border=True):
        c1, c2, c3 = st.columns([1, 3, 2])
        
        with c1:
            st.markdown("# 👨‍⚕️") # Avatar grande
        
        with c2:
            st.markdown(f"### Dr(a). {st.session_state.get('u_nome', u)}")
            st.caption(f"**Título Atual:** {status['titulo']}")
            
            # Barra de XP detalhada
            xp_atual = status['xp_atual']
            st.progress(xp_atual / 1000, text=f"XP Nível {status['nivel']}: {xp_atual}/1000")
            
        with c3:
            st.metric("Total de Questões", f"{total_q_global}", delta=f"Rumo a 20k")

    st.divider()

    # --- 2. CONFIGURAÇÕES DE META (GAMIFICAÇÃO) ---
    st.subheader("🎯 Ritmo de Estudos")
    
    def on_meta_change():
        nova_meta = st.session_state.slider_meta_perfil
        update_meta_diaria(u, nova_meta)
        st.toast(f"Nova meta definida: {nova_meta} questões/dia!", icon="🔥")

    meta_val = int(status['meta_diaria'])
    
    c_meta1, c_meta2 = st.columns([3, 1])
    with c_meta1:
        st.slider(
            "Defina sua meta diária de questões:", 
            min_value=10, max_value=200, value=meta_val, step=5,
            key="slider_meta_perfil", on_change=on_meta_change
        )
    with c_meta2:
        prog = get_progresso_hoje(u, nonce)
        st.metric("Hoje", f"{prog}/{meta_val}", delta=f"{int(prog/meta_val*100)}%")

    st.divider()

    # --- 3. SALA DE TROFÉUS (HARDCORE) ---
    st.subheader("🏆 Sala de Troféus")
    st.caption("Conquistas baseadas no volume total de questões resolvidas.")
    
    # Barra de Progresso Global (Rumo à Aprovação)
    perc_aprov = min(total_q_global / 20000, 1.0)
    st.progress(perc_aprov, text=f"Jornada para Aprovação (20.000q): {int(perc_aprov*100)}%")
    
    if proximo_nivel:
        falta = proximo_nivel['meta'] - total_q_global
        st.info(f"🚀 Faltam apenas **{falta}** questões para o título: **{proximo_nivel['nome']}**")

    # Grid de Conquistas
    cols = st.columns(3)
    for idx, c in enumerate(conquistas):
        with cols[idx % 3]:
            # Estilo visual para bloqueado/desbloqueado
            border_style = True if c['desbloqueado'] else False
            
            with st.container(border=True):
                if c['desbloqueado']:
                    st.markdown(f"### {c['icon']} {c['nome']}")
                    st.caption(f"✅ Conquistado! ({c['meta']}q)")
                    st.progress(1.0)
                else:
                    st.markdown(f"### 🔒 {c['nome']}")
                    st.caption(f"Meta: {c['meta']} questões")
                    # Progresso relativo para esta conquista
                    prog_relativo = min(total_q_global / c['meta'], 1.0)
                    st.progress(prog_relativo)

    st.divider()

    # --- 4. DADOS DA CONTA E SEGURANÇA ---
    with st.expander("🔒 Configurações de Conta e Segurança"):
        st.warning("Área Sensível")
        
        col_cred1, col_cred2 = st.columns(2)
        with col_cred1:
            st.text_input("Usuário (Login):", value=u, disabled=True)
            st.text_input("ID Interno:", value=f"MED-{hash(u)%100000:05d}", disabled=True)
        
        with col_cred2:
            st.text_input("Senha:", value="••••••••••••", type="password", disabled=True, help="Criptografada (bcrypt)")
            st.text_input("Status:", value="Ativo - Premium", disabled=True)

        if st.button("Sair da Conta (Logout)", type="primary"):
            st.session_state.logado = False
            st.rerun()