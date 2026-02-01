import streamlit as st
import pandas as pd
from database import listar_conteudo_videoteca, registrar_estudo, pesquisar_global

def render_videoteca(conn_ignored):
    st.subheader("📚 Videoteca Master")
    
    # Barra de Pesquisa
    termo = st.text_input("🔍 Pesquisar material...", placeholder="Ex: Pneumonia, Diabetes...", key="search_vid")
    
    if termo:
        df = pesquisar_global(termo)
    else:
        df = listar_conteudo_videoteca()

    if df.empty:
        st.info("Nenhum material encontrado no arquivo biblioteca_conteudo.py")
        return

    # Filtros por Área
    areas = ["Todas"] + sorted(df['grande_area'].unique().tolist())
    escolha_area = st.pills("Grande Área:", areas, selection_mode="single", default="Todas", key="pills_area")

    if escolha_area != "Todas":
        df = df[df['grande_area'] == escolha_area]

    # Agrupar por Assunto
    assuntos = df['assunto'].unique()
    for ass in assuntos:
        with st.expander(f"🔹 {ass}", expanded=False):
            items = df[df['assunto'] == ass]
            for _, row in items.iterrows():
                col_info, col_btn = st.columns([3, 1])
                with col_info:
                    icon = "📽️" if row['tipo'] == 'Video' else "📄"
                    st.markdown(f"{icon} **{row['titulo']}**")
                    st.caption(f"{row['subtipo']}")
                with col_btn:
                    st.link_button("Abrir", row['link'], use_container_width=True)
                    if st.button("✅ Concluir", key=f"ok_{row['id']}", use_container_width=True):
                        st.toast(registrar_estudo(st.session_state.username, ass, 1, 1))