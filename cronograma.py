import streamlit as st
import pandas as pd
from database import get_cronograma_status, salvar_cronograma_status, normalizar_area

def auto_save_callback(u, dados_brutos):
    """
    Função chamada automaticamente toda vez que um checkbox é alterado.
    Lê o estado atual da sessão e salva no banco imediatamente.
    """
    novo_estado = {}
    for item in dados_brutos:
        nome_aula = item[0] if isinstance(item, tuple) else item
        key = f"chk_{nome_aula}"
        # O session_state já contém o valor novo (True/False) do checkbox que acabou de ser clicado
        if st.session_state.get(key, False):
            novo_estado[nome_aula] = True
            
    # Salva silenciosamente no banco
    salvar_cronograma_status(u, novo_estado)
    # Feedback visual discreto
    st.toast("Salvo automaticamente!", icon="✅")

def render_cronograma(conn_ignored):
    st.header("🗂️ Cronograma Extensivo")
    st.caption("Seu progresso é salvo automaticamente ao marcar os itens.")

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
    # Como o callback roda antes do rerun, o get aqui já trará o dado atualizado do banco
    estado_salvo = get_cronograma_status(u)
    
    # 3. Organizar dados
    df = pd.DataFrame(dados_brutos, columns=['Aula', 'Area'])
    df['Area'] = df['Area'].apply(normalizar_area)
    areas = sorted(df['Area'].unique())

    # Barra de Progresso Geral
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
                
                # Checkbox com Auto-Save
                st.checkbox(
                    aula, 
                    value=is_checked, 
                    key=f"chk_{aula}",
                    on_change=auto_save_callback, # Aciona o salvamento ao mudar
                    args=(u, dados_brutos)        # Passa os argumentos necessários
                )