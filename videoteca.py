import streamlit as st
import pandas as pd
from database import listar_conteudo_videoteca, excluir_conteudo, registrar_estudo, pesquisar_global

def render_videoteca(conn_ignored):
    st.subheader("📚 Videoteca & Materiais")
    
    # 🔍 BARRA DE PESQUISA
    c_busca, c_stats = st.columns([3, 1])
    termo_busca = c_busca.text_input("🔍 Pesquisar aula ou material...", placeholder="Ex: Apendicite, Asma...")
    
    if termo_busca:
        # MODO PESQUISA (Global)
        st.caption(f"Resultados para: **'{termo_busca}'**")
        df = pesquisar_global(termo_busca)
        if df.empty:
            st.warning("😕 Nada encontrado.")
            return
        renderizar_lista_de_cards(df)
        
    else:
        # MODO NAVEGAÇÃO (Pastas)
        df_full = listar_conteudo_videoteca()
        
        if df_full.empty:
            st.info("Videoteca vazia.")
            return

        areas = df_full['grande_area'].unique()
        area_filtro = st.pills("Filtrar Área:", areas)
        
        if not area_filtro:
            st.info("👆 Selecione uma área ou pesquise acima.")
            return

        df_area = df_full[df_full['grande_area'] == area_filtro]
        assuntos = df_area['assunto'].unique()

        for assunto in assuntos:
            with st.expander(f"🔹 {assunto}", expanded=False):
                df_items = df_area[df_area['assunto'] == assunto]
                renderizar_lista_de_cards(df_items)

def renderizar_lista_de_cards(df):
    u = st.session_state.username # Necessário para registrar estudo
    
    # MATERIAIS
    materiais = df[df['tipo'] == 'Material']
    if not materiais.empty:
        st.markdown("###### 📄 Materiais")
        for _, row in materiais.iterrows():
            icon = "⭐" if row['subtipo'] == "Ficha" else "📎"
            with st.container(border=True):
                c1, c2, c3 = st.columns([0.1, 0.8, 0.1])
                c1.write(icon)
                c2.markdown(f"[{row['titulo']}]({row['link']})")
                if c3.button("🗑️", key=f"del_m_{row['id']}"):
                    excluir_conteudo(row['id']); st.rerun()

    # VÍDEOS
    videos = df[df['tipo'] == 'Video']
    if not videos.empty:
        st.markdown("###### 🎥 Aulas")
        for _, row in videos.iterrows():
            label = "⏱️ Rápido" if row['subtipo'] == "Curto" else "📽️ Aula"
            cor_btn = "primary" if row['subtipo'] == "Longo" else "secondary"
            
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1.2, 0.5])
                with c1:
                    st.write(f"**{row['titulo']}**")
                    if 'grande_area' in row: st.caption(f"📌 {row['grande_area']}")
                with c2:
                    st.link_button(label, row['link'], use_container_width=True, type=cor_btn)
                with c3:
                    with st.popover("⋮"):
                        if st.button("✅ Concluir", key=f"ok_{row['id']}", use_container_width=True):
                            registrar_estudo(u, row['assunto'], 1, 1) # Registra presença simbólica
                            st.toast("Estudo Registrado!")
                        st.divider()
                        if st.button("🗑️ Excluir", key=f"del_v_{row['id']}", use_container_width=True):
                            excluir_conteudo(row['id']); st.rerun()