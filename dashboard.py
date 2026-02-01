import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import time
from database import get_status_gamer, get_dados_graficos, listar_conteudo_videoteca

def render_dashboard(conn_ignored):
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    # --- TELA DE CARREGAMENTO ÚNICA ---
    loading_placeholder = st.empty()
    with loading_placeholder.container():
        st.markdown("<h3 style='text-align: center;'>🩺 Sincronizando sua performance médica...</h3>", unsafe_allow_html=True)
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.caption("Obtendo perfil...")
        status, df_m = get_status_gamer(u, nonce)
        progress_bar.progress(30)
        
        status_text.caption("Processando estatísticas avançadas...")
        df = get_dados_graficos(u, nonce)
        progress_bar.progress(70)
        
        status_text.caption("Finalizando ambiente...")
        listar_conteudo_videoteca()
        progress_bar.progress(100)
        time.sleep(0.4)
    
    loading_placeholder.empty()

    # 1. STATUS DE GAMIFICAÇÃO
    if status:
        st.markdown(f"### 🏆 {status['titulo']} - Nível {status['nivel']}")
        prog_total = status['xp_atual'] / status['xp_proximo']
        st.progress(prog_total, text=f"XP: {status['xp_atual']} / {status['xp_proximo']}")

    st.divider()

    # 2. MISSÕES DIÁRIAS (DESIGN FIXO)
    st.subheader("🚀 Missões Ativas")
    if not df_m.empty:
        m_cols = st.columns(3)
        for i, row in df_m.iterrows():
            with m_cols[i]:
                with st.container(border=True):
                    st.markdown(f"**{row['Icon']} {row['Meta']}**")
                    prog_m = min(row['Prog'] / row['Objetivo'], 1.0)
                    st.progress(prog_m)
                    st.caption(f"{row['Prog']} / {row['Objetivo']}")

    st.divider()

    # 3. ANÁLISE TEMPORAL (DIÁRIO, SEMANAL, MENSAL)
    if not df.empty:
        st.subheader("📈 Evolução de Aproveitamento")
        
        # Criamos abas para os diferentes períodos
        tab_dia, tab_semana, tab_mes, tab_especialidade = st.tabs([
            "📅 Diário", "🗓️ Semanal", "📊 Mensal", "🩺 Por Área"
        ])

        with tab_dia:
            # Agrupamento Diário (Últimos 15 registros de dias)
            df_day = df.groupby(df['data'].dt.date).agg({'acertos':'sum', 'total':'sum'}).reset_index()
            df_day['%'] = (df_day['acertos'] / df_day['total'] * 100).round(1)
            fig_day = px.line(df_day.tail(15), x='data', y='%', markers=True, title="Performance por Dia (%)", 
                             line_shape="spline", color_discrete_sequence=["#2563eb"])
            fig_day.update_layout(yaxis_range=[0, 105], template="plotly_white", height=350)
            st.plotly_chart(fig_day, use_container_width=True, config={'displayModeBar': False})

        with tab_semana:
            # Agrupamento Semanal
            df['semana'] = df['data'].dt.to_period('W').apply(lambda r: r.start_time)
            df_week = df.groupby('semana').agg({'acertos':'sum', 'total':'sum'}).reset_index()
            df_week['%'] = (df_week['acertos'] / df_week['total'] * 100).round(1)
            fig_week = px.bar(df_week, x='semana', y='%', text_auto='.1f', title="Média Semanal (%)", 
                             color_discrete_sequence=["#6366f1"])
            fig_week.update_layout(yaxis_range=[0, 105], template="plotly_white", height=350)
            st.plotly_chart(fig_week, use_container_width=True, config={'displayModeBar': False})

        with tab_mes:
            # Agrupamento Mensal
            df['mes'] = df['data'].dt.strftime('%b/%Y')
            df_month = df.groupby('mes').agg({'acertos':'sum', 'total':'sum'}).reset_index()
            df_month['%'] = (df_month['acertos'] / df_month['total'] * 100).round(1)
            fig_month = px.bar(df_month, x='mes', y='%', title="Consolidado Mensal (%)", 
                              color_discrete_sequence=["#8b5cf6"], text_auto='.1f')
            fig_month.update_layout(yaxis_range=[0, 105], template="plotly_white", height=350)
            st.plotly_chart(fig_month, use_container_width=True, config={'displayModeBar': False})
            
        with tab_especialidade:
            # Gráfico de Barras Fixo por Área
            df_area = df.groupby('area').agg({'acertos':'sum', 'total':'sum'}).reset_index()
            df_area['%'] = (df_area['acertos'] / df_area['total'] * 100).round(1)
            fig_area = px.bar(df_area, x='area', y='%', color='area', title="Aproveitamento por Especialidade",
                             color_discrete_sequence=px.colors.qualitative.Bold, text_auto='.1f')
            fig_area.update_layout(yaxis_range=[0, 105], showlegend=False, template="plotly_white", height=350)
            st.plotly_chart(fig_area, use_container_width=True, config={'displayModeBar': False})

        # 4. KPIs TOTAIS (CORREÇÃO DE SIMULADOS)
        st.divider()
        st.markdown("### 📊 Totais Acumulados")
        m1, m2, m3 = st.columns(3)
        total_q = int(df['total'].sum())
        total_a = int(df['acertos'].sum())
        media_geral = (total_a / total_q * 100) if total_q > 0 else 0
        
        m1.metric("Questões Respondidas", total_q)
        m2.metric("Acertos Totais", total_a)
        m3.metric("Aproveitamento Geral", f"{media_geral:.1f}%")

    else:
        st.info("Registre seus primeiros estudos para visualizar os gráficos de desempenho.")