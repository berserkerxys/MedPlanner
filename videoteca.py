import streamlit as st
import pandas as pd
from biblioteca_conteudo import VIDEOTECA_GLOBAL

def render_videoteca(conn_ignored):
    st.header("📚 Videoteca Global")
    
    # --- 1. CONFIGURAÇÃO DE ESTADO (PAGINAÇÃO) ---
    # Define quantos assuntos são carregados por vez (Lote)
    BATCH_SIZE = 5 
    
    if 'video_limit' not in st.session_state: 
        st.session_state.video_limit = BATCH_SIZE
    if 'video_last_area' not in st.session_state: 
        st.session_state.video_last_area = "Todas"
    if 'video_last_search' not in st.session_state: 
        st.session_state.video_last_search = ""

    # --- 2. CARGA DE DADOS ---
    colunas = ['grande_area', 'assunto', 'tipo', 'subtipo', 'titulo', 'link', 'id_conteudo']
    try:
        df = pd.DataFrame(VIDEOTECA_GLOBAL, columns=colunas)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return

    # --- 3. FILTROS (PESQUISA E ÁREA) ---
    termo = st.text_input("🔍 Pesquisar aula...", placeholder="Ex: Diabetes, Trauma...", value=st.session_state.video_last_search)
    
    lista_areas = ["Todas"] + sorted(df['grande_area'].unique().tolist())
    # O st.pills é ótimo para mobile, mas se não estiver disponível na versão, use selectbox
    # escolha_area = st.pills("Filtrar por Área:", lista_areas, default=st.session_state.video_last_area) # Streamlit mais novo
    escolha_area = st.selectbox("Filtrar por Área:", lista_areas, index=lista_areas.index(st.session_state.video_last_area) if st.session_state.video_last_area in lista_areas else 0)

    # --- 4. LÓGICA DE RESET DE PAGINAÇÃO ---
    # Se mudou o filtro, reseta a paginação para o início
    if escolha_area != st.session_state.video_last_area or termo != st.session_state.video_last_search:
        st.session_state.video_limit = BATCH_SIZE
        st.session_state.video_last_area = escolha_area
        st.session_state.video_last_search = termo
        st.rerun()

    # --- 5. APLICAÇÃO DOS FILTROS ---
    df_filtered = df.copy()
    
    if escolha_area != "Todas":
        df_filtered = df_filtered[df_filtered['grande_area'] == escolha_area]
        
    if termo:
        mask = df_filtered.apply(lambda x: x.astype(str).str.contains(termo, case=False, na=False)).any(axis=1)
        df_filtered = df_filtered[mask]

    if df_filtered.empty:
        st.warning("Nenhum conteúdo encontrado.")
        return

    # --- 6. RENDERIZAÇÃO OTIMIZADA (POR ASSUNTO) ---
    # Agrupa por assunto para manter a organização
    assuntos_unicos = sorted(df_filtered['assunto'].unique().tolist())
    total_assuntos = len(assuntos_unicos)
    
    # Fatiamento: Pega apenas até o limite atual
    assuntos_visiveis = assuntos_unicos[:st.session_state.video_limit]
    
    st.markdown(f"**Exibindo {len(assuntos_visiveis)} de {total_assuntos} tópicos**")
    
    for assunto in assuntos_visiveis:
        itens = df_filtered[df_filtered['assunto'] == assunto]
        qtd = len(itens)
        area_label = itens.iloc[0]['grande_area']
        
        with st.expander(f"🔹 {assunto} ({qtd})", expanded=False):
            for _, row in itens.iterrows():
                c1, c2 = st.columns([0.8, 0.2])
                with c1:
                    icone = "🎥" if row['tipo'] == 'Video' else "📄"
                    st.write(f"{icone} {row['titulo']}")
                    st.caption(f"{row['subtipo']}")
                with c2:
                    st.link_button("Abrir", row['link'], use_container_width=True)

    # --- 7. BOTÃO "CARREGAR MAIS" ---
    if len(assuntos_visiveis) < total_assuntos:
        st.markdown("---")
        col_load_1, col_load_2, col_load_3 = st.columns([1, 2, 1])
        with col_load_2:
            remaining = total_assuntos - len(assuntos_visiveis)
            # Botão grande e chamativo
            if st.button(f"⬇️ Carregar mais ({remaining} restantes)", use_container_width=True, type="primary"):
                st.session_state.video_limit += BATCH_SIZE
                st.rerun()