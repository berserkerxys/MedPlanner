import streamlit as st
import pandas as pd
from database import (
    get_cronograma_status, 
    salvar_cronograma_status,
    calcular_meta_questoes
)

# Fragmento: Garante que interações pequenas não recarreguem a página toda
@st.fragment
def render_aula_item(u, aula, prio, dados_aula, estado_completo):
    """Renderiza uma única linha do cronograma de forma independente."""
    c1, c2, c3, c4 = st.columns([0.1, 0.4, 0.3, 0.2])
    
    feito = c1.checkbox("", value=dados_aula.get('feito', False), key=f"chk_{aula}")
    c2.markdown(f"**{aula}**")
    
    # Se mudar o status, salva silenciosamente
    if feito != dados_aula.get('feito'):
        dados_aula['feito'] = feito
        estado_completo[aula] = dados_aula
        salvar_cronograma_status(u, estado_completo)

def render_cronograma(conn_ignored):
    st.subheader("🗂️ Seu Cronograma")
    u = st.session_state.username
    
    # Cache do estado na sessão para evitar IO repetitivo
    if 'cache_cronograma' not in st.session_state:
        st.session_state.cache_cronograma = get_cronograma_status(u)
    
    estado = st.session_state.cache_cronograma

    # Carregar dados pesados via cache do database
    from database import get_lista_assuntos_nativa
    aulas = get_lista_assuntos_nativa()

    for aula in aulas[:20]: # Exemplo limitado para performance
        render_aula_item(u, aula, "Normal", estado.get(aula, {}), estado)

    if st.button("💾 Salvar Alterações Globais", use_container_width=True):
        salvar_cronograma_status(u, estado)
        st.success("Tudo salvo!")