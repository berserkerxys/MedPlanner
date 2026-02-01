import streamlit as st
import pandas as pd
from biblioteca_conteudo import VIDEOTECA_GLOBAL

def render_videoteca(conn_ignored):
    st.header("📚 Videoteca Global")
    
    # 1. Carregar dados do arquivo estático (biblioteca_conteudo.py)
    # Estrutura da lista: [Grande Area, Assunto, Tipo, Subtipo, Titulo, Link, ID]
    colunas = ['grande_area', 'assunto', 'tipo', 'subtipo', 'titulo', 'link', 'id_conteudo']
    try:
        df = pd.DataFrame(VIDEOTECA_GLOBAL, columns=colunas)
    except Exception as e:
        st.error(f"Erro ao carregar biblioteca_conteudo.py: {e}")
        return

    # 2. Barra de Pesquisa
    termo = st.text_input("🔍 Pesquisar na videoteca...", placeholder="Ex: Diabetes, Trauma, Cirurgia...")
    
    if termo:
        # Filtra em qualquer coluna de texto
        mask = df.apply(lambda x: x.astype(str).str.contains(termo, case=False, na=False)).any(axis=1)
        df = df[mask]

    if df.empty:
        st.warning("Nenhum conteúdo encontrado com esses termos.")
        return

    # 3. Filtro de Áreas (Pills)
    lista_areas = ["Todas"] + sorted(df['grande_area'].unique().tolist())
    escolha_area = st.pills("Filtrar por Área:", lista_areas, default="Todas")
    
    if escolha_area != "Todas":
        df = df[df['grande_area'] == escolha_area]

    # 4. Renderização agrupada por Assunto
    # Pegamos os assuntos únicos presentes no DataFrame filtrado
    assuntos_disponiveis = sorted(df['assunto'].unique().tolist())

    for assunto in assuntos_disponiveis:
        # Cria um expander para cada assunto
        itens_do_assunto = df[df['assunto'] == assunto]
        
        # O título do expander mostra a área e a quantidade de itens
        qtd = len(itens_do_assunto)
        area_label = itens_do_assunto.iloc[0]['grande_area']
        
        with st.expander(f"🔹 {assunto} ({qtd} itens) - {area_label}", expanded=False):
            for _, row in itens_do_assunto.iterrows():
                # Layout de cada item
                c1, c2 = st.columns([0.85, 0.15])
                
                with c1:
                    # Ícone baseado no tipo
                    icone = "🎥" if row['tipo'] == 'Video' else "📄"
                    # Renderiza o título (que já vem com markdown do arquivo original)
                    st.markdown(f"{icone} {row['titulo']}")
                
                with c2:
                    st.link_button("Acessar", row['link'], use_container_width=True)