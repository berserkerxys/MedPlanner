import streamlit as st
import plotly.express as px
import time
import pandas as pd
from database import get_status_gamer, get_dados_graficos, listar_conteudo_videoteca

def render_dashboard(conn_ignored):
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    # --- PRÉ-CARREGAMENTO PROFISSIONAL ---
    loading = st.empty()
    with loading.container():
        st.markdown("<h3 style='text-align: center; color: #1e293b;'>🩺 Sincronizando Performance Médica...</h3>", unsafe_allow_html=True)
        pb = st.progress(0)
        status, df_m = get_status_gamer(u, nonce); pb.progress(35)
        df = get_dados_graficos(u, nonce); pb.progress(75)
        listar_conteudo_videoteca(); pb.progress(100)
        time.sleep(0.3)
    loading.empty()

    # 1. MISSÕES DIÁRIAS (BARRA DE PROGRESSO BLOQUEADA)
    st.subheader("🚀 Missões do Dia")
    if not df_m.empty:
        cols = st.columns(len(df_m))
        for i, row in df_m.iterrows():
            with cols[i]:
                with st.container(border=True):
                    st.markdown(f"**{row['Icon']} {row['Meta']}**")
                    prog = min(row['Prog'] / row['Objetivo'], 1.0)
                    st.progress(prog)
                    st.caption(f"{row['Prog']} / {row['Objetivo']} {row['Unid']}")
                    if row['Prog'] >= row['Objetivo']: st.success("Concluída!")

    st.divider()

    # 2. ANÁLISE MULTIDIMENSIONAL (ESPECIALIDADE X TEMPO)
    if not df.empty:
        st.subheader("📈 Performance por Especialidade")
        t_dia, t_sem, t_mes = st.tabs(["📅 Diário", "🗓️ Semanal", "📊 Mensal"])

        def plot_pro(dataframe, col, chart_type='bar'):
            # Agrupamento fixo por área e período
            df_g = dataframe.groupby([col, 'area']).agg({'acertos':'sum', 'total':'sum'}).reset_index()
            df_g['%'] = (df_g['acertos'] / df_g['total'] * 100).round(1)
            
            if chart_type == 'line':
                fig = px.line(df_g, x=col, y='%', color='area', markers=True, line_shape="spline", color_discrete_sequence=px.colors.qualitative.Bold)
            else:
                fig = px.bar(df_g, x=col, y='%', color='area', barmode='group', text_auto='.1f', color_discrete_sequence=px.colors.qualitative.Bold)
            
            fig.update_layout(yaxis_range=[0, 105], template="plotly_white", height=400, margin=dict(l=0,r=0,t=20,b=0), legend=dict(orientation="h", y=1.1, x=0))
            return fig

        with t_dia:
            df['dia'] = df['data'].dt.date
            st.plotly_chart(plot_pro(df.tail(30), 'dia', 'line'), use_container_width=True, config={'displayModeBar': False})
        with t_sem:
            df['semana'] = df['data'].dt.to_period('W').apply(lambda r: r.start_time)
            st.plotly_chart(plot_pro(df, 'semana'), use_container_width=True, config={'displayModeBar': False})
        with t_mes:
            df['mes'] = df['data'].dt.strftime('%m/%Y')
            st.plotly_chart(plot_pro(df, 'mes'), use_container_width=True, config={'displayModeBar': False})

        # 3. KPI TOTAIS
        st.divider()
        m1, m2, m3 = st.columns(3)
        tq, ta = df['total'].sum(), df['acertos'].sum()
        m1.metric("Questões Totais", int(tq))
        m2.metric("Acertos Totais", int(ta))
        m3.metric("Aproveitamento Geral", f"{(ta/tq*100 if tq>0 else 0):.1f}%")