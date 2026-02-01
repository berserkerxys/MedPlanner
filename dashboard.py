import streamlit as st
import plotly.express as px
import pandas as pd
from database import get_status_gamer, get_dados_graficos

def plot_pro(dataframe, col, chart_type='bar'):
    # A coluna 'area' já vem normalizada do database.py
    df_g = dataframe.groupby([col, 'area']).agg({'acertos':'sum', 'total':'sum'}).reset_index()
    df_g['%'] = (df_g['acertos'] / df_g['total'] * 100).round(1)
    
    if chart_type == 'line':
        fig = px.line(df_g, x=col, y='%', color='area', markers=True, template="plotly_white", line_shape="spline")
    else:
        fig = px.bar(df_g, x=col, y='total', color='area', barmode='group', template="plotly_white")
    
    fig.update_layout(height=400, margin=dict(l=0,r=0,t=30,b=0), legend=dict(orientation="h", y=1.1, x=0))
    return fig

def render_dashboard(conn_ignored):
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    df = get_dados_graficos(u, nonce)

    if not df.empty:
        st.subheader("📈 Performance Médica")
        tabs = st.tabs(["📅 Diário", "🗓️ Semanal", "📊 Mensal"])
        
        with tabs[0]:
            # Exibe os últimos 20 dias para clareza
            df['dia'] = df['data'].dt.strftime('%d/%m')
            st.plotly_chart(plot_pro(df.tail(20), 'dia', 'line'), use_container_width=True)
            
        with tabs[1]:
            # Agrupa por início da semana (segunda-feira)
            df['semana'] = df['data'].dt.to_period('W').apply(lambda r: r.start_time.strftime('%d/%m'))
            st.plotly_chart(plot_pro(df, 'semana', 'bar'), use_container_width=True)
            
        with tabs[2]:
            # Agrupa por mês/ano
            df['mes'] = df['data'].dt.strftime('%m/%Y')
            st.plotly_chart(plot_pro(df, 'mes', 'bar'), use_container_width=True)
            
        # Resumo Estatístico
        st.divider()
        c1, c2, c3 = st.columns(3)
        tq, ta = df['total'].sum(), df['acertos'].sum()
        c1.metric("Questões Totais", int(tq))
        c2.metric("Total Acertos", int(ta))
        c3.metric("Média Geral", f"{(ta/tq*100 if tq>0 else 0):.1f}%")
    else:
        st.info("Inicie seus estudos para visualizar sua performance detalhada!")