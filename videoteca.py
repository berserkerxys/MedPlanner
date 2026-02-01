import streamlit as st
from database import listar_conteudo_videoteca, registrar_estudo, pesquisar_global

def render_videoteca(conn_ignored):
    st.header("📚 Videoteca")
    termo = st.text_input("🔍 Pesquisar...", placeholder="Tema...")
    
    if termo:
        df = pesquisar_global(termo)
    else:
        df = listar_conteudo_videoteca()

    if df.empty:
        st.info("Videoteca vazia.")
        return

    areas = ["Todas"] + sorted(df['grande_area'].unique().tolist())
    escolha = st.pills("Filtro:", areas, default="Todas")
    if escolha != "Todas": df = df[df['grande_area'] == escolha]

    for assunto in df['assunto'].unique():
        with st.expander(f"🔹 {assunto}"):
            items = df[df['assunto'] == assunto]
            for _, row in items.iterrows():
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{row['titulo']}**\n<small>{row['subtipo']}</small>", unsafe_allow_html=True)
                with c2:
                    st.link_button("Abrir", row['link'], use_container_width=True)