import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from database import get_status_gamer, get_dados_graficos

def render_dashboard(conn_ignored):
    u = st.session_state.username
    perfil, _ = get_status_gamer(u)
    
    # --- CABEÇALHO PREMIUM ---
    if perfil:
        with st.container():
            c1, c2 = st.columns([1, 3])
            with c1:
                # Avatar Simples
                st.markdown(f"<div style='font-size: 80px; text-align: center;'>🩺</div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"### {perfil['titulo']} - Nível {perfil['nivel']}")
                xp_prog = perfil['xp_atual'] / perfil['xp_proximo']
                st.progress(xp_prog)
                st.caption(f"XP: {perfil['xp_atual']} / {perfil['xp_proximo']} para o próximo nível")

    st.divider()
    
    # --- GRÁFICOS ---
    df = get_dados_graficos(u)
    
    if df.empty:
        st.info("Regista as tuas primeiras questões para veres a tua evolução!")
        return

    col1, col2 = st.columns(2)
    
    with col1:
        # Performance por Área
        df_area = df.groupby('area')[['acertos', 'total']].sum().reset_index()
        df_area['% Aproveitamento'] = (df_area['acertos'] / df_area['total'] * 100).round(1)
        
        fig_bar = px.bar(
            df_area, x='area', y='% Aproveitamento', 
            color='area', title="Desempenho por Grande Área",
            text_auto=True, color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_bar.update_layout(showlegend=False, yaxis_range=[0, 105])
        st.plotly_chart(fig_bar, use_container_width=True)

    with col2:
        # Evolução Temporal
        df_evo = df.groupby('data')['percentual'].mean().reset_index()
        fig_line = px.line(
            df_evo, x='data', y='percentual', 
            title="Sua Evolução Diária (%)", markers=True
        )
        fig_line.update_layout(yaxis_range=[0, 105])
        st.plotly_chart(fig_line, use_container_width=True)

    # Tabela de Resumo
    st.subheader("📈 Resumo Geral")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Questões", int(df['total'].sum()))
    c2.metric("Acertos Totais", int(df['acertos'].sum()))
    c3.metric("Média Geral", f"{(df['acertos'].sum() / df['total'].sum() * 100):.1f}%")