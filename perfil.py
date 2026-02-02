import streamlit as st
import time
from datetime import datetime
from database import (
    get_status_gamer,
    get_conquistas_e_stats,
    update_meta_diaria,
    get_progresso_hoje,
    get_dados_pessoais,
    update_dados_pessoais
)

def render_perfil(conn_ignored):
    st.header("👤 Perfil & Conquistas")
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    # Dados
    status, _ = get_status_gamer(u, nonce)
    total_q_global, conquistas, proximo_nivel = get_conquistas_e_stats(u)
    dados_pessoais = get_dados_pessoais(u)
    prog = get_progresso_hoje(u, nonce)
    
    # Inicializa estado do slider do perfil se necessário
    meta_banco = int(status['meta_diaria'])
    if "pf_meta_slider" not in st.session_state:
        st.session_state.pf_meta_slider = meta_banco

    # --- 1. CABEÇALHO ---
    with st.container(border=True):
        c1, c2, c3 = st.columns([1, 3, 2])
        with c1: st.markdown("# 👨‍⚕️")
        with c2:
            st.markdown(f"### Dr(a). {st.session_state.get('u_nome', u)}")
            st.markdown(f"**Rank:** {status['titulo']}")
            
            # Aniversário
            nasc_str = dados_pessoais.get('nascimento')
            if nasc_str:
                try:
                    dt = datetime.strptime(nasc_str, "%Y-%m-%d")
                    if dt.day == datetime.now().day and dt.month == datetime.now().month:
                        st.success("🎂 Feliz Aniversário! 🎉")
                except: pass
        with c3: st.metric("Total Questões", f"{total_q_global}", delta="Carreira")

    st.divider()
    
    # --- 2. CONFIGURAÇÕES ---
    st.subheader("⚙️ Configurações e Dados")
    tab_meta, tab_dados = st.tabs(["🎯 Meta Diária", "📝 Dados Pessoais"])
    
    with tab_meta:
        st.caption("Defina seu ritmo de estudos diário:")
        
        def on_pf_meta_change():
            novo = st.session_state.pf_meta_slider
            update_meta_diaria(u, novo)
            st.toast(f"Meta atualizada: {novo} questões!", icon="🔥")
            # Sincroniza slider da sidebar se existir
            if "sb_meta_slider" in st.session_state:
                st.session_state.sb_meta_slider = novo

        c_m1, c_m2 = st.columns([3, 1])
        with c_m1:
            st.slider(
                "Questões/dia:", 10, 200, 
                value=meta_banco, 
                step=5, 
                key="pf_meta_slider", 
                on_change=on_pf_meta_change
            )
        with c_m2:
            # Feedback visual instantâneo usando o estado do slider
            meta_vis = st.session_state.pf_meta_slider if st.session_state.pf_meta_slider > 0 else 1
            st.metric("Hoje", f"{prog}/{meta_vis}", delta=f"{int(prog/meta_vis*100)}%")

    with tab_dados:
        with st.form("f_dados"):
            c1, c2 = st.columns(2)
            em = c1.text_input("Email", value=dados_pessoais.get("email", ""))
            
            dt_val = None
            if dados_pessoais.get("nascimento"):
                try: dt_val = datetime.strptime(dados_pessoais['nascimento'], "%Y-%m-%d")
                except: pass
            
            nasc = c2.date_input("Nascimento", value=dt_val, format="DD/MM/YYYY")
            
            if st.form_submit_button("💾 Salvar Dados"):
                nasc_fmt = nasc.strftime("%Y-%m-%d") if nasc else None
                if update_dados_pessoais(u, em, nasc_fmt):
                    st.success("Dados atualizados!")
                    time.sleep(0.5)
                    st.rerun()
                else: st.error("Erro ao salvar.")

    st.divider()
    
    # --- 3. TROFÉUS ---
    st.subheader("🏆 Sala de Troféus")
    perc_aprov = min(total_q_global / 20000, 1.0)
    st.progress(perc_aprov, text=f"Rumo à Aprovação (20k): {int(perc_aprov*100)}%")
    
    cols = st.columns(3)
    for i, c in enumerate(conquistas):
        with cols[i%3]:
            with st.container(border=True):
                if c['desbloqueado']:
                    st.markdown(f"### {c['icon']} {c['nome']}")
                    st.caption("✅ Conquistado")
                else:
                    st.markdown(f"### 🔒 {c['nome']}")
                    st.caption(f"Meta: {c['meta']}q")
                    st.progress(min(total_q_global/c['meta'], 1.0))
    
    st.divider()
    
    with st.expander("🚨 Zona de Perigo"):
        st.warning("Ações Críticas")
        st.text_input("Usuário", value=u, disabled=True)
        if st.button("Sair da Conta", type="primary"):
            st.session_state.logado = False
            st.rerun()