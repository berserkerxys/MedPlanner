import streamlit as st
import pandas as pd
from database import get_cronograma_status, salvar_cronograma_status, normalizar_area

def render_cronograma(conn_ignored):
    st.header("🗂️ Cronograma Extensivo")
    st.caption("Marque as aulas concluídas e clique em 'Salvar Progresso'.")

    u = st.session_state.username
    
    # 1. Carregar aulas
    try:
        import aulas_medcof
        dados_brutos = getattr(aulas_medcof, 'DADOS_LIMPOS', [])
    except ImportError:
        st.error("Arquivo aulas_medcof.py não encontrado.")
        return

    if not dados_brutos:
        st.warning("Lista de aulas vazia.")
        return

    # 2. Carregar estado salvo
    estado_salvo = get_cronograma_status(u)
    
    # Botão de Salvar Topo
    if st.button("💾 Salvar Progresso", key="btn_save_top", type="primary"):
        novo_estado = {}
        for item in dados_brutos:
            nome_aula = item[0] if isinstance(item, tuple) else item
            key = f"chk_{nome_aula}"
            if st.session_state.get(key, False):
                novo_estado[nome_aula] = True
        
        if salvar_cronograma_status(u, novo_estado):
            st.toast("Cronograma salvo!", icon="✅")
            st.rerun()

    # 3. Organizar dados
    df = pd.DataFrame(dados_brutos, columns=['Aula', 'Area'])
    df['Area'] = df['Area'].apply(normalizar_area)
    areas = sorted(df['Area'].unique())

    # Barra de Progresso
    total_aulas = len(df)
    concluidas = sum(1 for k in estado_salvo if estado_salvo.get(k))
    progresso = concluidas / total_aulas if total_aulas > 0 else 0
    st.progress(progresso, text=f"Progresso Geral: {concluidas}/{total_aulas} ({progresso:.1%})")

    # 4. Renderizar Checkboxes
    for area in areas:
        aulas_area = df[df['Area'] == area]['Aula'].tolist()
        concluidas_area = sum(1 for a in aulas_area if estado_salvo.get(a))
        
        with st.expander(f"📘 {area} ({concluidas_area}/{len(aulas_area)})"):
            for aula in aulas_area:
                is_checked = estado_salvo.get(aula, False)
                st.checkbox(aula, value=is_checked, key=f"chk_{aula}")

    # Botão de Salvar Final
    if st.button("💾 Salvar Progresso", key="btn_save_bottom"):
        novo_estado = {}
        for item in dados_brutos:
            nome_aula = item[0] if isinstance(item, tuple) else item
            key = f"chk_{nome_aula}"
            if st.session_state.get(key, False):
                novo_estado[nome_aula] = True
        
        if salvar_cronograma_status(u, novo_estado):
            st.toast("Cronograma salvo!", icon="✅")
            st.rerun()