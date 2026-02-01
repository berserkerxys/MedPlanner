import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from database import get_status_gamer, get_dados_graficos

def render_dashboard(conn_ignored):
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    status, df_missoes = get_status_gamer(u, nonce)
    
    # 1. Cabeçalho de Gamificação
    if status:
        st.markdown(f"### Nível {status['nivel']} • {status['titulo']}")
        col1, col2 = st.columns([3, 1])
        with col1:
            progress = status['xp_atual'] / status['xp_proximo']
            st.progress(progress, text=f"XP: {status['xp_atual']} / {status['xp_proximo']}")
        with col2:
            st.metric("Total XP", f"{status['xp_total']} pts")

    st.divider()

    # 2. SEÇÃO DE MISSÕES (CORRIGIDA)
    st.subheader("🚀 Missões do Dia")
    if not df_missoes.empty:
        cols = st.columns(len(df_missoes))
        for i, row in df_missoes.iterrows():
            with cols[i]:
                percent = min(row['Progresso'] / row['Meta'], 1.0)
                st.markdown(f"**{row['Icon']} {row['Missão']}**")
                st.markdown(f"**{row['Progresso']}** / {row['Meta']} {row['Unid']}")
                st.progress(percent)
    
    st.divider()

    # 3. GRÁFICOS MELHORADOS
    df = get_dados_graficos(u, nonce)
    if not df.empty:
        st.subheader("📈 Análise de Performance")
        
        tab_evo, tab_area = st.tabs(["Evolução Temporal", "Aproveitamento por Área"])
        
        with tab_evo:
            # Gráfico de Evolução Otimizado
            df_day = df.groupby(df['data'].dt.date)['percentual'].mean().reset_index()
            fig_evo = px.line(df_day, x='data', y='percentual', 
                             title="Média de Acertos Diária",
                             markers=True, line_shape="spline",
                             color_discrete_sequence=['#3b82f6'])
            fig_evo.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=30, b=0),
                                 yaxis_range=[0, 105], hovermode="x unified")
            st.plotly_chart(fig_evo, use_container_width=True)

        with tab_area:
            # Gráfico de Barras Moderno
            df_area = df.groupby('area')[['acertos', 'total']].sum().reset_index()
            df_area['%'] = (df_area['acertos'] / df_area['total'] * 100).round(1)
            
            fig_area = px.bar(df_area, x='area', y='%', 
                             text='%', color='%',
                             color_continuous_scale="Blues",
                             title="Aproveitamento por Área Médica")
            fig_area.update_layout(template="plotly_white", showlegend=False,
                                  yaxis_range=[0, 105], coloraxis_showscale=False)
            st.plotly_chart(fig_area, use_container_width=True)

        # 4. TABELA DE REGISTROS RECENTES
        with st.expander("📝 Ver Histórico Detalhado"):
            st.dataframe(df[['data_estudo', 'assunto_nome', 'area_manual', 'acertos', 'total', 'percentual']].sort_values('data_estudo', ascending=False), 
                        use_container_width=True, hide_index=True)