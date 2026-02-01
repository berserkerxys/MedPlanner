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
    
    # Dados de Gamificação
    status, _ = get_status_gamer(u, nonce)
    total_q_global, conquistas, proximo_nivel = get_conquistas_e_stats(u)
    
    # Dados Pessoais
    dados_pessoais = get_dados_pessoais(u)
    
    # --- 1. CABEÇALHO DO PERFIL ---
    with st.container(border=True):
        c1, c2, c3 = st.columns([1, 3, 2])
        
        with c1:
            st.markdown("# 👨‍⚕️")
        
        with c2:
            st.markdown(f"### Dr(a). {st.session_state.get('u_nome', u)}")
            st.markdown(f"**Rank:** {status['titulo']}")
            st.caption(f"Nível {status['nivel']}")
            
            # Checagem de Aniversário
            nasc_str = dados_pessoais.get('nascimento')
            if nasc_str:
                try:
                    nasc_dt = datetime.strptime(nasc_str, "%Y-%m-%d")
                    hoje = datetime.now()
                    if today_is_birthday(nasc_dt, hoje):
                        st.success("🎂 Feliz Aniversário, Doutor(a)! Hoje o dia é seu! 🎉")
                except: pass
            
        with c3:
            st.metric("Total Questões", f"{total_q_global}", delta="Acumulado")

    st.divider()

    # --- 2. CONFIGURAÇÕES (Meta e Dados) ---
    st.subheader("⚙️ Configurações e Dados")
    
    tab_meta, tab_dados = st.tabs(["🎯 Meta Diária", "📝 Dados Pessoais"])
    
    with tab_meta:
        st.caption("Defina seu ritmo de estudos diário:")
        def on_meta_change():
            nova_meta = st.session_state.slider_meta_perfil
            update_meta_diaria(u, nova_meta)
            st.toast(f"Meta: {nova_meta} questões!", icon="🔥")

        meta_val = int(status['meta_diaria'])
        c_m1, c_m2 = st.columns([3, 1])
        with c_m1:
            st.slider("Questões/dia:", 10, 200, meta_val, 5, key="slider_meta_perfil", on_change=on_meta_change)
        with c_m2:
            prog = get_progresso_hoje(u, nonce)
            st.metric("Hoje", f"{prog}/{meta_val}")

    with tab_dados:
        with st.form("form_dados_pessoais"):
            c_d1, c_d2 = st.columns(2)
            
            email_atual = dados_pessoais.get("email", "")
            nasc_atual_str = dados_pessoais.get("nascimento")
            nasc_val = None
            if nasc_atual_str:
                try: nasc_val = datetime.strptime(nasc_atual_str, "%Y-%m-%d")
                except: pass

            email_input = c_d1.text_input("E-mail", value=email_atual, placeholder="seuemail@exemplo.com")
            nasc_input = c_d2.date_input("Data de Nascimento", value=nasc_val, format="DD/MM/YYYY")
            
            if st.form_submit_button("💾 Salvar Dados"):
                nasc_fmt = nasc_input.strftime("%Y-%m-%d") if nasc_input else None
                if update_dados_pessoais(u, email_input, nasc_fmt):
                    st.success("Dados atualizados com sucesso!")
                    st.rerun()
                else:
                    st.error("Erro ao salvar.")

    st.divider()

    # --- 3. SALA DE TROFÉUS ---
    st.subheader("🏆 Sala de Troféus")
    
    perc_aprov = min(total_q_global / 20000, 1.0)
    st.progress(perc_aprov, text=f"Rumo à Aprovação (20k): {int(perc_aprov*100)}%")
    
    if proximo_nivel:
        st.info(f"Faltam **{proximo_nivel['meta'] - total_q_global}** questões para: **{proximo_nivel['nome']}**")

    cols = st.columns(3)
    for idx, c in enumerate(conquistas):
        with cols[idx % 3]:
            with st.container(border=True):
                if c['desbloqueado']:
                    st.markdown(f"## {c['icon']} {c['nome']}")
                    st.caption(f"✅ Conquistado ({c['meta']}q)")
                else:
                    st.markdown(f"## 🔒 {c['nome']}")
                    st.caption(f"Meta: {c['meta']} questões")
                    st.progress(min(total_q_global / c['meta'], 1.0))

def today_is_birthday(nasc, hoje):
    return nasc.month == hoje.month and nasc.day == hoje.day