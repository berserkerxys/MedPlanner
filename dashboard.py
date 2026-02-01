import streamlit as st
import plotly.express as px
from database import get_status_gamer, get_dados_graficos

def render_dashboard(conn_ignored):
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    status, df_m = get_status_gamer(u, nonce)
    
    # 1. METAS DO DIA (MISSÕES)
    st.subheader("🚀 Missões de Hoje")
    if not df_m.empty:
        cols = st.columns(3)
        for i, row in df_m.iterrows():
            with cols[i]:
                st.markdown(f"**{row['Icon']} {row['Meta']}**")
                prog = min(row['Prog'] / row['Objetivo'], 1.0)
                st.progress(prog, text=f"{row['Prog']} / {row['Objetivo']}")
    
    st.divider()
    
    # 2. GRÁFICOS PROFISSIONAIS (Cores de Alto Contraste)
    df = get_dados_graficos(u, nonce)
    if not df.empty:
        c1, c2 = st.columns(2)
        
        with c1:
            df_evo = df.groupby(df['data'].dt.date)['percentual'].mean().reset_index()
            fig_line = px.line(df_evo, x='data', y='percentual', title="Evolução de Aproveitamento (%)",
                              markers=True, line_shape="spline",
                              color_discrete_sequence=["#2563eb"])
            fig_line.update_layout(yaxis_range=[0,105], template="plotly_white")
            st.plotly_chart(fig_line, use_container_width=True)
            
        with c2:
            df_area = df.groupby('area')[['acertos', 'total']].sum().reset_index()
            df_area['%'] = (df_area['acertos'] / df_area['total'] * 100).round(1)
            # Paleta de cores distinta (Bold)
            fig_bar = px.bar(df_area, x='area', y='%', color='area',
                            title="Desempenho por Especialidade",
                            color_discrete_sequence=px.colors.qualitative.Prism,
                            text_auto=True)
            fig_bar.update_layout(yaxis_range=[0,105], showlegend=False, template="plotly_white")
            st.plotly_chart(fig_bar, use_container_width=True)

        # 3. MÉTRICAS TOTAIS
        st.subheader("📊 Histórico Geral")
        m1, m2, m3 = st.columns(3)
        total_q = df['total'].sum()
        total_a = df['acertos'].sum()
        m1.metric("Questões Totais", int(total_q))
        m2.metric("Acertos", int(total_a))
        m3.metric("Média Geral", f"{(total_a/total_q*100):.1f}%")