import streamlit as st
from database import listar_conteudo_videoteca, registrar_estudo

def render_videoteca(conn_ignored):
    st.header("📚 Sua Videoteca")
    df = listar_conteudo_videoteca()
    if df.empty:
        st.warning("Biblioteca vazia. Use o script sync.py.")
        return

    # Busca
    busca = st.text_input("🔍 Procurar aula...", placeholder="Digite o tema...")
    if busca:
        df = df[df['titulo'].str.contains(busca, case=False) | df['assunto'].str.contains(busca, case=False)]

    areas = ["Todas"] + sorted(df['grande_area'].unique().tolist())
    area_sel = st.pills("Filtro por Área:", areas, default="Todas")
    if area_sel != "Todas": df = df[df['grande_area'] == area_sel]

    for assunto in df['assunto'].unique():
        with st.expander(f"🔹 {assunto}"):
            items = df[df['assunto'] == assunto]
            for _, row in items.iterrows():
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{row['titulo']}**")
                c1.caption(f"{row['tipo']} - {row['subtipo']}")
                with c2:
                    st.link_button("Abrir", row['link'], use_container_width=True)
                    if st.button("OK", key=f"ok_{row['id']}", use_container_width=True):
                        st.toast(registrar_estudo(st.session_state.username, assunto, 1, 1))