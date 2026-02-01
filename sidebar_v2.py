import streamlit as st
import time
from database import (
    get_progresso_hoje, 
    get_status_gamer, 
    update_meta_diaria,
    get_lista_assuntos_nativa,
    registrar_estudo,
    registrar_simulado
)

def render_sidebar():
    # --- 1. CABEÇALHO DO PERFIL ---
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    # Obtém dados atualizados do banco
    status, _ = get_status_gamer(u, nonce)
    
    with st.sidebar:
        # Saudação Personalizada
        st.markdown(f"### 🩺 Dr(a). {st.session_state.get('u_nome', 'Usuário')}")
        
        # Cartão de Gamer (Nível e XP)
        with st.container(border=True):
            c1, c2 = st.columns([1, 2.5])
            with c1:
                # Avatar Simples
                st.markdown("## 👨‍⚕️") 
            with c2:
                st.write(f"**Nível {status['nivel']}**")
                st.caption(f"Rank: {status['titulo']}")
            
            # Barra de XP
            xp_atual = status['xp_atual']
            st.progress(xp_atual / 1000, text=f"XP: {xp_atual}/1000")

        st.divider()

        # --- 2. META DIÁRIA (CONTROLE DESLIZANTE) ---
        st.markdown("### 🎯 Meta Diária")
        
        # Função de Callback para salvar automático
        def on_meta_change():
            nova_meta = st.session_state.slider_meta
            update_meta_diaria(u, nova_meta)
            st.toast(f"Meta atualizada para {nova_meta} questões!", icon="🔥")

        # SLIDER INTERATIVO ("ARCO")
        # Permite arrastar para definir a meta entre 10 e 200 questões
        meta_selecionada = st.slider(
            label="Deslize para ajustar seu objetivo:",
            min_value=10,
            max_value=200,
            value=int(status['meta_diaria']),
            step=5,
            key="slider_meta",
            on_change=on_meta_change,
            help="Arraste o marcador para aumentar ou diminuir sua meta diária de questões."
        )
        
        # Feedback Visual de Progresso
        progresso = get_progresso_hoje(u, nonce)
        percentual = min(progresso / meta_selecionada, 1.0) if meta_selecionada > 0 else 0
        
        st.progress(percentual, text=f"Hoje: {progresso} de {meta_selecionada} questões")
        
        if percentual >= 1.0:
            st.success("🎉 Meta batida! Parabéns!")

        st.divider()

        # --- 3. REGISTRO DE ESTUDO ---
        st.markdown("### 📝 Registrar Atividade")
        
        tab_aula, tab_sim = st.tabs(["Questões/Aula", "Simulado"])
        
        # ABA 1: Registro Rápido
        with tab_aula:
            lista = get_lista_assuntos_nativa()
            assunto = st.selectbox("Tema:", lista, placeholder="Busque o tema...", index=None, label_visibility="collapsed")
            
            c_ac, c_tot = st.columns(2)
            acertos = c_ac.number_input("Acertos", 0, 300, 0)
            total = c_tot.number_input("Total", 1, 300, 10)
            
            if st.button("✅ Registrar", use_container_width=True):
                if assunto:
                    msg = registrar_estudo(u, assunto, acertos, total)
                    st.success(msg)
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.warning("Escolha um tema acima!")

        # ABA 2: Registro de Simulado
        with tab_sim:
            st.caption("Informe acertos/total por área:")
            areas_sim = ["Preventiva", "Cirurgia", "Clínica Médica", "Ginecologia e Obstetrícia", "Pediatria"]
            dados_sim = {}
            
            for area in areas_sim:
                with st.expander(area, expanded=False):
                    a = st.number_input(f"Acertos {area}", 0, 100, 0, key=f"sac_{area}")
                    t = st.number_input(f"Total {area}", 0, 100, 0, key=f"stt_{area}")
                    dados_sim[area] = {'acertos': a, 'total': t}
            
            if st.button("💾 Salvar Simulado", type="primary", use_container_width=True):
                msg = registrar_simulado(u, dados_sim)
                st.success(msg)
                time.sleep(0.5)
                st.rerun()