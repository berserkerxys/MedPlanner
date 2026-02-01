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

    # 2. ANÁLISE MULTIDIMENSIONAL (ESPECIALIDADE X TEMPO)
    if not df.empty:
        st.subheader("📈 Performance por Especialidade")
        t_dia, t_sem, t_mes = st.tabs(["📅 Diário", "🗓️ Semanal", "📊 Mensal"])

        # Configuração para BLOQUEAR interação e remover contadores de tempo
        chart_config = {
            'staticPlot': True,  # Bloqueia cliques e zoom
            'displayModeBar': False 
        }

        def plot_clean(dataframe, col, chart_type='bar'):
            # Agrupar por data e área
            df_g = dataframe.groupby([col, 'area']).agg({'acertos':'sum', 'total':'sum'}).reset_index()
            df_g['%'] = (df_g['acertos'] / df_g['total'] * 100).round(1)
            
            if chart_type == 'line':
                # Linha suave com pontos conforme solicitado
                fig = px.line(df_g, x=col, y='%', color='area', markers=True, 
                             line_shape="spline", color_discrete_sequence=px.colors.qualitative.Bold)
            else:
                fig = px.bar(df_g, x=col, y='%', color='area', barmode='group', 
                            text_auto='.1f', color_discrete_sequence=px.colors.qualitative.Bold)
            
            fig.update_layout(
                yaxis_range=[0, 105], 
                template="plotly_white", 
                height=400,
                margin=dict(l=0, r=0, t=30, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                xaxis_title=None,
                yaxis_title="Aproveitamento (%)",
                # FORÇA O EIXO X A SER APENAS DATA (SEM HORA/MINUTO)
                xaxis=dict(
                    type='category',  # Trata data como categoria para evitar milissegundos
                    tickformat="%d/%m"
                )
            )
            return fig

        with t_dia:
            # Gráfico de pontos formando linhas (Evolução Diária)
            # Pegamos os últimos 15 dias para não esmagar
            recent_days = sorted(df['data'].unique())[-15:]
            df_recent = df[df['data'].isin(recent_days)]
            st.plotly_chart(plot_clean(df_recent, 'data', 'line'), use_container_width=True, config=chart_config)
            
        with t_sem:
            # Agrupamento Semanal
            df_sem = df.copy()
            df_sem['semana'] = pd.to_datetime(df_sem['data']).dt.to_period('W').apply(lambda r: r.start_time.strftime('%d/%m'))
            st.plotly_chart(plot_clean(df_sem, 'semana'), use_container_width=True, config=chart_config)

        with t_mes:
            # Agrupamento Mensal
            df_mes = df.copy()
            df_mes['mes'] = pd.to_datetime(df_mes['data']).dt.strftime('%b/%Y')
            st.plotly_chart(plot_clean(df_mes, 'mes'), use_container_width=True, config=chart_config)

        # 3. KPIs TOTAIS
        st.divider()
        m1, m2, m3 = st.columns(3)
        tq, ta = df['total'].sum(), df['acertos'].sum()
        m1.metric("Questões Respondidas", int(tq))
        m2.metric("Acertos Totais", int(ta))
        m3.metric("Média Geral", f"{(ta/tq*100 if tq > 0 else 0):.1f}%")
    else:
        st.info("Registe estudos na barra lateral para ver a sua evolução.")