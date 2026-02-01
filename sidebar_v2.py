import streamlit as st
import time
from database import (
    get_progresso_hoje, 
    get_status_gamer, 
    update_meta_diaria,
    get_lista_assuntos_nativa,
    registrar_estudo,
    registrar_simulado,
    get_conquistas_e_stats
)

def render_sidebar():
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    # Carrega dados do gamer e conquistas
    status, _ = get_status_gamer(u, nonce)
    total_q_global, conquistas, proximo_nivel = get_conquistas_e_stats(u)
    
    with st.sidebar:
        # --- CABEÇALHO ---
        st.markdown(f"### 🩺 Dr(a). {st.session_state.get('u_nome', 'Usuário')}")
        
        with st.container(border=True):
            c1, c2 = st.columns([1, 2.5])
            with c1:
                st.markdown("# 👨‍⚕️") 
            with c2:
                st.write(f"**Nível {status['nivel']}**")
                st.caption(f"Rank: {status['titulo']}")
            
            xp_atual = status['xp_atual']
            st.progress(xp_atual / 1000, text=f"XP: {xp_atual}/1000")

        st.divider()

        # --- ABAS PRINCIPAIS ---
        tab_meta, tab_conq, tab_conta = st.tabs(["🎯 Meta", "🏆 Conquistas", "👤 Conta"])

        # 1. ABA META DIÁRIA
        with tab_meta:
            st.caption("Ajuste sua meta diária de questões:")
            
            def on_meta_change():
                nova_meta = st.session_state.slider_meta
                update_meta_diaria(u, nova_meta)
                st.toast(f"Meta: {nova_meta} questões!", icon="🔥")

            meta_val = int(status['meta_diaria'])
            st.slider(
                "Objetivo:", 10, 200, meta_val, 5, 
                key="slider_meta", on_change=on_meta_change
            )
            
            prog = get_progresso_hoje(u, nonce)
            perc = min(prog / meta_val, 1.0) if meta_val > 0 else 0
            st.progress(perc, text=f"Hoje: {prog}/{meta_val}")
            if perc >= 1.0: st.success("Meta batida!")

        # 2. ABA CONQUISTAS (HARDCORE)
        with tab_conq:
            st.caption(f"**Total Global: {total_q_global} questões**")
            
            # Barra "Rumo à Aprovação" (20k)
            perc_aprov = min(total_q_global / 20000, 1.0)
            st.progress(perc_aprov, text=f"Rumo à Aprovação ({int(perc_aprov*100)}%)")
            
            if proximo_nivel:
                falta = proximo_nivel['meta'] - total_q_global
                st.info(f"Faltam {falta}q para: **{proximo_nivel['nome']}**")
            
            st.markdown("---")
            st.markdown("**Sala de Troféus:**")
            
            for c in conquistas:
                if c['desbloqueado']:
                    st.success(f"{c['icon']} **{c['nome']}** ({c['meta']}q)")
                else:
                    st.markdown(f"🔒 {c['nome']} _({c['meta']}q)_")

        # 3. ABA DADOS DA CONTA
        with tab_conta:
            st.info("ℹ️ Dados de Acesso")
            st.text_input("Usuário (Login):", value=u, disabled=True)
            st.text_input("ID do Sistema:", value=f"USR-{hash(u)%10000:04d}", disabled=True)
            st.text_input("Senha:", value="••••••••", type="password", disabled=True, help="A senha é criptografada e não pode ser exibida.")
            
            st.caption("🔒 Suas credenciais são protegidas por criptografia bcrypt.")
            
            if st.button("Sair / Logout", type="primary"):
                st.session_state.logado = False
                st.rerun()

        st.divider()

        # --- REGISTRO DE ATIVIDADE ---
        st.markdown("### 📝 Registrar")
        t_reg, t_sim = st.tabs(["Aula", "Simulado"])
        
        with t_reg:
            lista = get_lista_assuntos_nativa()
            assunto = st.selectbox("Tema:", lista, placeholder="Tema...", index=None, label_visibility="collapsed")
            c1, c2 = st.columns(2)
            ac = c1.number_input("Acertos", 0, 300, 0)
            tot = c2.number_input("Total", 1, 300, 10)
            
            if st.button("✅ Salvar", use_container_width=True):
                if assunto:
                    msg = registrar_estudo(u, assunto, ac, tot)
                    st.success(msg)
                    time.sleep(0.5)
                    st.rerun()
                else: st.warning("Selecione um tema!")

        with t_sim:
            areas = ["Preventiva", "Cirurgia", "Clínica Médica", "Ginecologia e Obstetrícia", "Pediatria"]
            dados = {}
            for ar in areas:
                with st.expander(ar):
                    a = st.number_input(f"Acertos {ar}", 0, 100, 0, key=f"a_{ar}")
                    t = st.number_input(f"Total {ar}", 0, 100, 0, key=f"t_{ar}")
                    dados[ar] = {'acertos': a, 'total': t}
            if st.button("💾 Salvar Simulado", use_container_width=True):
                msg = registrar_simulado(u, dados)
                st.success(msg)
                time.sleep(0.5)
                st.rerun()