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
    
    # --- NOTIFICAÇÃO DE TROFÉU ---
    # Verifica se houve desbloqueio recente (simulação simples baseada no estado anterior)
    if 'last_total_q' not in st.session_state:
        st.session_state.last_total_q = total_q_global
    
    if total_q_global > st.session_state.last_total_q:
        # Se aumentou o número de questões, verifica se desbloqueou algo novo
        for c in conquistas:
            if c['desbloqueado'] and c['meta'] > st.session_state.last_total_q and c['meta'] <= total_q_global:
                st.toast(f"🏆 CONQUISTA DESBLOQUEADA: {c['nome']}!", icon="🎉")
        st.session_state.last_total_q = total_q_global

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
        tab_conta, tab_conq, tab_meta = st.tabs(["👤 Perfil", "🏆 Troféus", "🎯 Meta"])

        # 1. ABA DADOS DA CONTA (PERFIL)
        with tab_conta:
            st.markdown("### 🆔 Credenciais")
            st.text_input("Usuário:", value=u, disabled=True)
            st.text_input("ID:", value=f"MED-{hash(u)%100000:05d}", disabled=True)
            st.text_input("Senha:", value="••••••••", type="password", disabled=True)
            
            st.caption("🔒 Seus dados estão seguros.")
            
            if st.button("Sair da Conta", type="primary", use_container_width=True):
                st.session_state.logado = False
                st.rerun()

        # 2. ABA CONQUISTAS (HARDCORE - GALERIA DE TROFÉUS)
        with tab_conq:
            st.markdown(f"### 🏅 Sala de Troféus")
            st.caption(f"Total Global: **{total_q_global}** questões resolvidas")
            
            # Barra "Rumo à Aprovação" (20k)
            perc_aprov = min(total_q_global / 20000, 1.0)
            st.progress(perc_aprov, text=f"Rumo à Aprovação ({int(perc_aprov*100)}%)")
            
            if proximo_nivel:
                falta = proximo_nivel['meta'] - total_q_global
                st.info(f"Faltam **{falta}q** para o próximo nível!")
            
            st.markdown("---")
            
            # Galeria Visual de Conquistas
            for c in conquistas:
                with st.container(border=True):
                    col_icon, col_info = st.columns([1, 3])
                    with col_icon:
                        if c['desbloqueado']:
                            st.markdown(f"## {c['icon']}")
                        else:
                            st.markdown("## 🔒")
                    with col_info:
                        if c['desbloqueado']:
                            st.markdown(f"**{c['nome']}**")
                            st.caption(f"✅ Conquistado ({c['meta']}q)")
                        else:
                            st.markdown(f"**Bloqueado**")
                            st.caption(f"Meta: {c['meta']} questões")

        # 3. ABA META DIÁRIA
        with tab_meta:
            st.caption("Defina seu ritmo diário:")
            
            def on_meta_change():
                nova_meta = st.session_state.slider_meta
                update_meta_diaria(u, nova_meta)
                st.toast(f"Meta: {nova_meta} questões!", icon="🔥")

            meta_val = int(status['meta_diaria'])
            st.slider(
                "Questões/Dia:", 10, 200, meta_val, 5, 
                key="slider_meta", on_change=on_meta_change
            )
            
            prog = get_progresso_hoje(u, nonce)
            perc = min(prog / meta_val, 1.0) if meta_val > 0 else 0
            st.progress(perc, text=f"Hoje: {prog}/{meta_val}")
            
            if perc >= 1.0: 
                st.success("🔥 Meta diária batida!")
            else:
                st.info(f"Faltam {meta_val - prog} para a meta.")

        st.divider()

        # --- REGISTRO DE ATIVIDADE ---
        st.markdown("### 📝 Registrar Estudo")
        t_reg, t_sim = st.tabs(["Aula", "Simulado"])
        
        with t_reg:
            lista = get_lista_assuntos_nativa()
            assunto = st.selectbox("Tema:", lista, placeholder="Tema...", index=None, label_visibility="collapsed")
            c1, c2 = st.columns(2)
            ac = c1.number_input("Acertos", 0, 300, 0)
            tot = c2.number_input("Total", 1, 300, 10)
            
            if st.button("✅ Salvar Aula", use_container_width=True):
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