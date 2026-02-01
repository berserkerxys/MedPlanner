import streamlit as st
import plotly.express as px
import pandas as pd
import time
from database import get_status_gamer, get_dados_graficos, listar_conteudo_videoteca

def render_dashboard(conn_ignored):
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    loading = st.empty()
    with loading.container():
        st.markdown("<h3 style='text-align: center;'>🩺 Sincronizando Performance Médica...</h3>", unsafe_allow_html=True)
        pb = st.progress(0)
        status, df_m = get_status_gamer(u, nonce); pb.progress(40)
        df = get_dados_graficos(u, nonce); pb.progress(80)
        listar_conteudo_videoteca(); pb.progress(100)
        time.sleep(0.3)
    loading.empty()

    # 1. MISSÕES DIÁRIAS
    st.subheader("🚀 Missões de Hoje")
    if not df_m.empty:
        cols = st.columns(3)
        for i, row in df_m.iterrows():
            with cols[i]:
                with st.container(border=True):
                    st.markdown(f"**{row['Icon']} {row['Meta']}**")
                    p = min(row['Prog'] / row['Objetivo'], 1.0) if row['Objetivo'] > 0 else 0
                    st.progress(p)
                    st.caption(f"{row['Prog']} / {row['Objetivo']} {row['Unid']}")

    st.divider()

    # 2. GRÁFICOS (DESIGN FIXED & CATEGORY BASED)
    if not df.empty:
        st.subheader("📈 Performance Médica")
        chart_config = {'staticPlot': True}

        def plot_pro(dataframe, col, chart_type='bar'):
            df_g = dataframe.groupby([col, 'area']).agg({'acertos':'sum', 'total':'sum'}).reset_index()
            df_g['%'] = (df_g['acertos'] / df_g['total'] * 100).round(1)
            
            if chart_type == 'line':
                # PONTOS FORMANDO LINHAS (DIÁRIO)
                fig = px.line(df_g, x=col, y='%', color='area', markers=True, line_shape="spline", color_discrete_sequence=px.colors.qualitative.Bold)
            else:
                fig = px.bar(df_g, x=col, y='%', color='area', barmode='group', text_auto='.1f', color_discrete_sequence=px.colors.qualitative.Bold)
            
            fig.update_layout(
                yaxis_range=[0, 105], template="plotly_white", height=400, 
                margin=dict(l=0,r=0,t=20,b=0), legend=dict(orientation="h", y=1.1, x=0),
                xaxis=dict(type='category') # REMOVE MILISSEGUNDOS
            )
            return fig

        tabs = st.tabs(["📅 Diário", "🗓️ Semanal", "📊 Mensal"])
        with tabs[0]:
            df['dia'] = pd.to_datetime(df['data']).dt.strftime('%d/%m')
            st.plotly_chart(plot_pro(df.tail(30), 'dia', 'line'), use_container_width=True, config=chart_config)
        with tabs[1]:
            df['semana'] = pd.to_datetime(df['data']).dt.to_period('W').apply(lambda r: r.start_time.strftime('%d/%m'))
            st.plotly_chart(plot_pro(df, 'semana'), use_container_width=True, config=chart_config)
        with tabs[2]:
            df['mes'] = pd.to_datetime(df['data']).dt.strftime('%m/%Y')
            st.plotly_chart(plot_pro(df, 'mes'), use_container_width=True, config=chart_config)

        # KPIs
        st.divider()
        m1, m2, m3 = st.columns(3)
        tq, ta = df['total'].sum(), df['acertos'].sum()
        m1.metric("Questões", int(tq))
        m2.metric("Acertos", int(ta))
        m3.metric("Média Geral", f"{(ta/tq*100 if tq>0 else 0):.1f}%")