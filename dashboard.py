import streamlit as st
import plotly.express as px
import time
import pandas as pd
from database import get_status_gamer, get_dados_graficos, listar_conteudo_videoteca

def render_dashboard(conn_ignored):
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    # --- PRÉ-CARREGAMENTO ---
    loading = st.empty()
    with loading.container():
        st.markdown("<h3 style='text-align: center;'>🩺 Sincronizando Performance Médica...</h3>", unsafe_allow_html=True)
        pb = st.progress(0)
        status, df_m = get_status_gamer(u, nonce); pb.progress(40)
        df = get_dados_graficos(u, nonce); pb.progress(80)
        listar_conteudo_videoteca(); pb.progress(100)
        time.sleep(0.3)
    loading.empty()

    # 1. CABEÇALHO
    if status:
        st.markdown(f"### 🏆 {status['titulo']} - Nível {status['nivel']}")
        st.progress(status['xp_atual'] / 1000, text=f"XP: {status['xp_atual']} / 1000")

    st.divider()

    # 2. ANÁLISE MULTIDIMENSIONAL (FIXA/ESTÁTICA)
    if not df.empty:
        st.subheader("📈 Desempenho por Período e Área Médica")
        
        tab_dia, tab_sem, tab_mes = st.tabs(["📅 Diário", "🗓️ Semanal", "📊 Mensal"])

        # Configuração para BLOQUEAR interação (sem zoom, sem pan, sem clique alternando)
        chart_config = {'staticPlot': True}

        def plot_area_pro(dataframe, period_col, chart_type='bar'):
            # Agrupar explicitamente para evitar zoom excessivo no eixo X
            df_grouped = dataframe.groupby([period_col, 'area']).agg({'acertos':'sum', 'total':'sum'}).reset_index()
            df_grouped['%'] = (df_grouped['acertos'] / df_grouped['total'] * 100).round(1)
            
            if chart_type == 'line':
                # Gráfico de pontos formando linhas para evolução diária
                fig = px.line(df_grouped, x=period_col, y='%', color='area', markers=True,
                             line_shape="spline", color_discrete_sequence=px.colors.qualitative.Bold)
            else:
                fig = px.bar(df_grouped, x=period_col, y='%', color='area', barmode='group',
                            text_auto='.1f', color_discrete_sequence=px.colors.qualitative.Bold)
            
            fig.update_layout(
                yaxis_range=[0, 105], 
                template="plotly_white", 
                height=400,
                margin=dict(l=0, r=0, t=30, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                xaxis_title=None,
                yaxis_title="Aproveitamento (%)"
            )
            return fig

        with tab_dia:
            # Pegar os últimos 15 dias para o gráfico não ficar esmagado
            df_day = df.copy()
            df_day['data_dia'] = df_day['data'].dt.date
            recent_days = sorted(df_day['data_dia'].unique())[-15:]
            df_recent = df_day[df_day['data_dia'].isin(recent_days)]
            
            st.plotly_chart(plot_area_pro(df_recent, 'data_dia', 'line'), 
                           use_container_width=True, config=chart_config)

        with tab_sem:
            df['semana'] = df['data'].dt.to_period('W').apply(lambda r: r.start_time)
            st.plotly_chart(plot_area_pro(df, 'semana'), 
                           use_container_width=True, config=chart_config)

        with tab_mes:
            df['mes'] = df['data'].dt.strftime('%m/%Y')
            st.plotly_chart(plot_area_pro(df, 'mes'), 
                           use_container_width=True, config=chart_config)

        # 3. MÉTRICAS TOTAIS
        st.divider()
        m1, m2, m3 = st.columns(3)
        t_q, t_a = int(df['total'].sum()), int(df['acertos'].sum())
        m1.metric("Total de Questões", t_q)
        m2.metric("Acertos Totais", t_a)
        m3.metric("Média Geral", f"{(t_a/t_q*100 if t_q>0 else 0):.1f}%")

    else:
        st.info("Registre seus primeiros estudos para visualizar a sua evolução.")