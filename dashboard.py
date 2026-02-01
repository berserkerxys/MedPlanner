import streamlit as st
import plotly.express as px
from database import get_status_gamer, get_dados_graficos

def render_dashboard(conn_ignored):
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    perfil, _ = get_status_gamer(u, nonce)
    
    if perfil:
        c1, c2 = st.columns([1, 4])
        with c1: st.markdown("<h1 style='text-align:center;'>🏆</h1>", unsafe_allow_html=True)
        with c2:
            st.subheader(f"{perfil['titulo']} - Nível {perfil['nivel']}")
            st.progress(perfil['xp_atual'] / perfil['xp_proximo'])
            st.caption(f"XP: {perfil['xp_atual']} / {perfil['xp_proximo']} para subir")

    df = get_dados_graficos(u, nonce)
    if not df.empty:
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            df_area = df.groupby('area')[['acertos', 'total']].sum().reset_index()
            df_area['%'] = (df_area['acertos'] / df_area['total'] * 100).round(1)
            st.plotly_chart(px.bar(df_area, x='area', y='%', color='area', title="Performance (%)"), use_container_width=True)
        with col2:
            df_evo = df.groupby('data')['percentual'].mean().reset_index()
            st.plotly_chart(px.line(df_evo, x='data', y='percentual', title="Sua Evolução", markers=True), use_container_width=True)

        st.subheader("📊 Totais")
        m1, m2, m3 = st.columns(3)
        m1.metric("Questões", int(df['total'].sum()))
        m2.metric("Acertos", int(df['acertos'].sum()))
        m3.metric("Média", f"{(df['acertos'].sum()/df['total'].sum()*100):.1f}%")