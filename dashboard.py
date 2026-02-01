import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import get_status_gamer, get_progresso_hoje, get_dados_graficos

def render_dashboard(conn_ignored):
    if 'username' not in st.session_state: return
    u = st.session_state.username

    # --- 1. CABEÇALHO GAMIFICADO ---
    perfil, _ = get_status_gamer(u)
    
    if perfil:
        st.markdown(f"## 🩺 {perfil['titulo']} - Nível {perfil['nivel']}")
        progresso_xp = perfil['xp_atual'] / perfil['xp_proximo'] if perfil['xp_proximo'] > 0 else 0
        st.progress(progresso_xp)
        st.caption(f"XP: {perfil['xp_atual']} / {perfil['xp_proximo']}")

    st.divider()

    # --- 2. META DIÁRIA ---
    questoes_hoje = get_progresso_hoje(u)
    meta_hoje = 50 
    
    fig_meta = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = questoes_hoje,
        title = {'text': "Questões Hoje"},
        gauge = {'axis': {'range': [None, 100]}, 'bar': {'color': "#10b981"}}
    ))
    fig_meta.update_layout(height=200, margin=dict(t=30,b=20,l=20,r=20))
    st.plotly_chart(fig_meta, use_container_width=True)

    st.divider()

    # --- 3. GRÁFICOS (Usando get_dados_graficos) ---
    st.subheader("📊 Performance")
    
    # Busca dados processados do Firebase
    df_perf = get_dados_graficos(u)
    
    if df_perf.empty:
        st.info("Registe o seu primeiro estudo para ver os gráficos!")
    else:
        # Gráfico de Áreas
        # Filtra 'Banco Geral' se quiser focar nas áreas médicas
        df_areas = df_perf[df_perf['grande_area'] != 'Banco Geral']
        if not df_areas.empty:
            df_agrupado = df_areas.groupby('grande_area')[['acertos', 'total']].sum().reset_index()
            df_agrupado['Nota'] = (df_agrupado['acertos'] / df_agrupado['total'] * 100).round(1)
            
            fig_bar = px.bar(df_agrupado, x='grande_area', y='Nota', color='grande_area', title="Aproveitamento por Área (%)")
            st.plotly_chart(fig_bar, use_container_width=True)
        
        # Evolução Temporal
        # Agrupa por data
        df_evo = df_perf.groupby('data_estudo')['percentual'].mean().reset_index()
        fig_line = px.line(df_evo, x='data_estudo', y='percentual', markers=True, title="Evolução Diária")
        st.plotly_chart(fig_line, use_container_width=True)