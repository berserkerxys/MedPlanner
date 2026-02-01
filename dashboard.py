import streamlit as st
import plotly.express as px
import pandas as pd
from database import get_status_gamer, get_dados_graficos

def plot_pro(dataframe, col, chart_type='bar'):
    if 'area' not in dataframe.columns: dataframe['area'] = 'Geral'
    df_g = dataframe.groupby([col, 'area']).agg({'acertos':'sum', 'total':'sum'}).reset_index()
    df_g['%'] = (df_g['acertos'] / df_g['total'] * 100).round(1)
    
    if chart_type == 'line':
        fig = px.line(df_g, x=col, y='%', color='area', markers=True, template="plotly_white")
    else:
        fig = px.bar(df_g, x=col, y='total', color='area', barmode='group', template="plotly_white")
    
    fig.update_layout(height=350, margin=dict(l=0,r=0,t=20,b=0))
    return fig

def render_dashboard(conn_ignored):
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    df = get_dados_graficos(u, nonce) # cite: 12

    if not df.empty:
        st.subheader("📈 Performance Médica")
        tabs = st.tabs(["📅 Diário", "🗓️ Semanal", "📊 Mensal"])
        
        with tabs[0]:
            df['dia'] = df['data'].dt.strftime('%d/%m')
            st.plotly_chart(plot_pro(df.tail(30), 'dia', 'line'), use_container_width=True)
            
        with tabs[1]:
            df['semana'] = df['data'].dt.to_period('W').apply(lambda r: r.start_time.strftime('%d/%m'))
            st.plotly_chart(plot_pro(df, 'semana', 'bar'), use_container_width=True)
            
        with tabs[2]:
            df['mes'] = df['data'].dt.strftime('%m/%Y')
            st.plotly_chart(plot_pro(df, 'mes', 'bar'), use_container_width=True)
    else:
        st.info("Registre seus primeiros estudos para visualizar sua evolução!")