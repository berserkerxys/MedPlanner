import streamlit as st
import plotly.express as px
import time
import pandas as pd
from database import get_status_gamer, get_dados_graficos, listar_conteudo_videoteca

def render_dashboard(conn_ignored):
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    # --- PRÉ-CARREGAMENTO COM BARRA DE PROGRESSO REAL ---
    loading = st.empty()
    with loading.container():
        st.markdown("<h3 style='text-align: center;'>🩺 Sincronizando Carreira...</h3>", unsafe_allow_html=True)
        pb = st.progress(0)
        status, df_m = get_status_gamer(u, nonce); pb.progress(30)
        df = get_dados_graficos(u, nonce); pb.progress(70)
        listar_conteudo_videoteca(); pb.progress(100)
        time.sleep(0.3)
    loading.empty()

    # 1. GAMIFICAÇÃO
    if status:
        st.markdown(f"### 🏆 {status['titulo']} - Nível {status['nivel']}")
        st.progress(status['xp_atual'] / 1000)

    st.divider()

    # 2. MISSÕES (FIXAS)
    st.subheader("🚀 Missões do Dia")
    if not df_m.empty:
        cols = st.columns(3)
        for i, row in df_m.iterrows():
            with cols[i]:
                with st.container(border=True):
                    st.markdown(f"**{row['Icon']} {row['Meta']}**")
                    p = min(row['Prog'] / row['Objetivo'], 1.0)
                    st.progress(p)
                    st.caption(f"{row['Prog']} / {row['Objetivo']} {row['Unid']}")

    st.divider()

    # 3. ANÁLISE MULTIDIMENSIONAL (ESPECIALIDADE X TEMPO)
    if not df.empty:
        st.subheader("📈 Performance por Especialidade")
        t1, t2, t3 = st.tabs(["📅 Diário", "🗓️ Semanal", "📊 Mensal"])

        def plot_pro(dataframe, col, chart_type='bar'):
            # Cores qualitativas Bold para contraste total
            df_g = dataframe.groupby([col, 'area']).agg({'acertos':'sum', 'total':'sum'}).reset_index()
            df_g['%'] = (df_g['acertos'] / df_g['total'] * 100).round(1)
            
            if chart_type == 'line':
                fig = px.line(df_g, x=col, y='%', color='area', markers=True, line_shape="spline", color_discrete_sequence=px.colors.qualitative.Bold)
            else:
                fig = px.bar(df_g, x=col, y='%', color='area', barmode='group', text_auto='.1f', color_discrete_sequence=px.colors.qualitative.Bold)
            
            fig.update_layout(yaxis_range=[0, 105], template="plotly_white", height=400, margin=dict(l=0,r=0,t=20,b=0), legend=dict(orientation="h", y=1.1))
            return fig

        with t1:
            df['dia'] = df['data'].dt.date
            st.plotly_chart(plot_pro(df.tail(30), 'dia', 'line'), use_container_width=True, config={'displayModeBar': False})
        with t2:
            df['semana'] = df['data'].dt.to_period('W').apply(lambda r: r.start_time)
            st.plotly_chart(plot_pro(df, 'semana'), use_container_width=True, config={'displayModeBar': False})
        with t3:
            df['mes'] = df['data'].dt.strftime('%m/%Y')
            st.plotly_chart(plot_pro(df, 'mes'), use_container_width=True, config={'displayModeBar': False})

        st.divider()
        m1, m2, m3 = st.columns(3)
        tq, ta = df['total'].sum(), df['acertos'].sum()
        m1.metric("Total Questões", int(tq))
        m2.metric("Acertos", int(ta))
        m3.metric("Média Geral", f"{(ta/tq*100):.1f}%")
    else:
        st.info("Registre estudos para visualizar a sua evolução.")