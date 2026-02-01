import streamlit as st
import plotly.express as px
from database import get_status_gamer, get_dados_graficos

def render_dashboard(conn_ignored):
    u = st.session_state.username
    perfil, _ = get_status_gamer(u)
    
    # Cabeçalho
    if perfil:
        st.markdown(f"## Nível {perfil['nivel']} - {perfil['titulo']}")
        st.progress(perfil['xp'] / 1000) # Exemplo simplificado
    
    st.divider()
    
    # Gráficos (Usando Pandas e não SQL)
    df_hist = get_dados_graficos(u)
    
    if df_hist.empty:
        st.info("Sem dados ainda.")
        return
        
    c1, c2 = st.columns(2)
    
    # Gráfico de Barras
    df_area = df_hist.groupby('area')[['acertos', 'total']].sum().reset_index()
    df_area['Nota'] = (df_area['acertos'] / df_area['total'] * 100).round(1)
    
    fig1 = px.bar(df_area, x='area', y='Nota', title="Desempenho por Área", color='area')
    c1.plotly_chart(fig1, use_container_width=True)
    
    # Gráfico de Evolução
    df_evo = df_hist.groupby('data_estudo')['percentual'].mean().reset_index()
    fig2 = px.line(df_evo, x='data_estudo', y='percentual', title="Evolução Diária")
    c2.plotly_chart(fig2, use_container_width=True)