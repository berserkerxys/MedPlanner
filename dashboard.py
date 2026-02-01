import streamlit as st
import plotly.express as px
import pandas as pd
from database import get_status_gamer, get_dados_graficos

def plot_pro(dataframe, col, chart_type='bar'):
    # Proteção de Coluna
    if 'area' not in dataframe.columns: dataframe['area'] = 'Geral'
    dataframe['area'] = dataframe['area'].fillna('Geral')
    
    # Agrupamento
    df_g = dataframe.groupby([col, 'area']).agg({'acertos':'sum', 'total':'sum'}).reset_index()
    df_g['%'] = (df_g['acertos'] / df_g['total'] * 100).round(1)
    
    if chart_type == 'line':
        fig = px.line(df_g, x=col, y='%', color='area', markers=True, template="plotly_white")
    else:
        fig = px.bar(df_g, x=col, y='total', color='area', barmode='group', template="plotly_white")
    
    fig.update_layout(yaxis_range=[0, 105] if chart_type=='line' else None, height=350, margin=dict(l=0,r=0,t=20,b=0))
    return fig

def render_dashboard(conn_ignored):
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    status, df_m = get_status_gamer(u, nonce)
    df = get_dados_graficos(u, nonce)

    # 1. KPIs de Missões
    st.subheader("🚀 Missões de Hoje")
    if not df_m.empty:
        cols = st.columns(3)
        for i, row in df_m.iterrows():
            with cols[i]:
                st.metric(row['Meta'], f"{row['Prog']} / {row['Objetivo']}")
                st.progress(min(row['Prog']/row['Objetivo'], 1.0) if row['Objetivo']>0 else 0)

    st.divider()

    # 2. GRÁFICOS COM FILTROS (ABAS)
    if not df.empty:
        st.subheader("📈 Análise de Desempenho")
        tabs = st.tabs(["📅 Diário", "🗓️ Semanal", "📊 Mensal"])
        
        with tabs[0]:
            df['dia'] = df['data'].dt.strftime('%d/%m')
            st.plotly_chart(plot_pro(df.tail(30), 'dia', 'line'), use_container_width=True)
            
        with tabs[1]:
            # Agrupa por início da semana
            df['semana'] = df['data'].dt.to_period('W').apply(lambda r: r.start_time.strftime('%d/%m'))
            st.plotly_chart(plot_pro(df, 'semana', 'bar'), use_container_width=True)
            
        with tabs[2]:
            df['mes'] = df['data'].dt.strftime('%m/%Y')
            st.plotly_chart(plot_pro(df, 'mes', 'bar'), use_container_width=True)

        # Resumo Geral
        c1, c2, c3 = st.columns(3)
        tq, ta = df['total'].sum(), df['acertos'].sum()
        c1.metric("Total Questões", int(tq))
        c2.metric("Total Acertos", int(ta))
        c3.metric("Média Geral", f"{(ta/tq*100 if tq>0 else 0):.1f}%")
    else:
        st.info("Registre sua primeira aula na barra lateral para ver os gráficos!")