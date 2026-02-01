import streamlit as st
import plotly.express as px
import pandas as pd
import time
from database import get_status_gamer, get_dados_graficos, listar_conteudo_videoteca

def render_dashboard(conn_ignored):
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    # --- TELA DE CARREGAMENTO PROFISSIONAL ---
    loading_placeholder = st.empty()
    with loading_placeholder.container():
        st.markdown("<h3 style='text-align: center;'>🩺 Sincronizando Performance Médica...</h3>", unsafe_allow_html=True)
        progress_bar = st.progress(0)
        
        status, df_m = get_status_gamer(u, nonce); progress_bar.progress(40)
        df = get_dados_graficos(u, nonce); progress_bar.progress(80)
        listar_conteudo_videoteca(); progress_bar.progress(100)
        time.sleep(0.3)
    loading_placeholder.empty()

    # 1. CABEÇALHO
    if status:
        st.markdown(f"### 🏆 {status['titulo']} - Nível {status['nivel']}")
        st.progress(status['xp_atual'] / 1000, text=f"XP: {status['xp_atual']} / 1000")

    st.divider()

    # 2. ANÁLISE MULTIDIMENSIONAL (TRAVADA/BLOQUEADA)
    if not df.empty:
        st.subheader("📈 Performance por Período e Área")
        tab_dia, tab_sem, tab_mes = st.tabs(["📅 Diário", "🗓️ Semanal", "📊 Mensal"])

        # Configuração para travar interação (sem zoom/hover ativo)
        chart_config = {'staticPlot': True}

        def plot_area(dataframe, period_col, chart_type='bar'):
            df_g = dataframe.groupby([period_col, 'area']).agg({'acertos':'sum', 'total':'sum'}).reset_index()
            df_g['%'] = (df_g['acertos'] / df_g['total'] * 100).round(1)
            
            if chart_type == 'line':
                fig = px.line(df_g, x=period_col, y='%', color='area', markers=True, line_shape="spline", color_discrete_sequence=px.colors.qualitative.Bold)
            else:
                fig = px.bar(df_g, x=period_col, y='%', color='area', barmode='group', text_auto='.1f', color_discrete_sequence=px.colors.qualitative.Bold)
            
            fig.update_layout(yaxis_range=[0, 105], template="plotly_white", height=400, margin=dict(l=0,r=0,t=20,b=0), legend=dict(orientation="h", y=1.1, x=0))
            return fig

        with tab_dia:
            df['dia'] = df['data'].dt.date
            st.plotly_chart(plot_area(df.tail(30), 'dia', 'line'), use_container_width=True, config=chart_config)
        with tab_sem:
            df['semana'] = df['data'].dt.to_period('W').apply(lambda r: r.start_time)
            st.plotly_chart(plot_area(df, 'semana'), use_container_width=True, config=chart_config)
        with tab_mes:
            df['mes'] = df['data'].dt.strftime('%m/%Y')
            st.plotly_chart(plot_area(df, 'mes'), use_container_width=True, config=chart_config)

        st.divider()
        m1, m2, m3 = st.columns(3)
        tq, ta = df['total'].sum(), df['acertos'].sum()
        m1.metric("Total Questões", int(tq))
        m2.metric("Acertos Totais", int(ta))
        m3.metric("Média Geral", f"{(ta/tq*100 if tq>0 else 0):.1f}%")
    else:
        st.info("Registre estudos para visualizar a sua evolução.")