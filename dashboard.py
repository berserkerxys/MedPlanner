import streamlit as st
import pandas as pd
import plotly.express as px
from database import get_status_gamer, get_dados_graficos, listar_conteudo_videoteca

def plot_pro(dataframe, col, tipo='bar'):
    # --- CORREÇÃO DO ERRO KeyError: 'area' ---
    # Garante que a coluna 'area' exista e não tenha valores nulos
    if 'area' not in dataframe.columns:
        if 'area_manual' in dataframe.columns:
            dataframe['area'] = dataframe['area_manual'].fillna("Geral")
        else:
            dataframe['area'] = "Geral"
    
    dataframe['area'] = dataframe['area'].replace("", "Geral").fillna("Geral")
    # ------------------------------------------

    df_g = dataframe.groupby([col, 'area']).agg({'acertos':'sum', 'total':'sum'}).reset_index()
    df_g['Perc'] = (df_g['acertos'] / df_g['total'] * 100).round(1)
    
    if tipo == 'line':
        fig = px.line(df_g, x=col, y='Perc', color='area', markers=True, template="plotly_white")
    else:
        fig = px.bar(df_g, x=col, y='total', color='area', barmode='group', template="plotly_white")
    
    fig.update_layout(margin=dict(l=20, r=20, t=30, b=20), height=300)
    return fig

def render_dashboard(conn_ignored):
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    # 1. Dados de Gamificação
    status, missoes = get_status_gamer(u, nonce)
    
    if status:
        c1, c2, c3 = st.columns([1, 1, 2])
        c1.metric("Nível", f"{status['nivel']}")
        c2.metric("XP Total", f"{status['xp_total']}")
        c3.markdown(f"### 🏆 Título: {status['titulo']}")
        
        st.write("---")
        st.subheader("🚀 Missões Diárias")
        cols = st.columns(len(missoes))
        for i, row in missoes.iterrows():
            with cols[i]:
                prog = min(row['Prog'] / row['Objetivo'], 1.0) if row['Objetivo'] > 0 else 0
                st.write(f"{row['Icon']} **{row['Meta']}**")
                st.progress(prog)
                st.caption(f"{row['Prog']} / {row['Objetivo']} {row['Unid']}")

    st.write("---")
    
    # 2. Gráficos de Performance
    df = get_dados_graficos(u, nonce)
    
    if not df.empty:
        # Criar coluna de dia formatado para o gráfico
        df['dia'] = df['data'].dt.strftime('%d/%m')
        
        chart_config = {'displayModeBar': False}
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📈 Evolução (% Acertos)")
            # Pegamos os últimos 30 registros para não poluir o gráfico
            st.plotly_chart(plot_pro(df.tail(30), 'dia', 'line'), use_container_width=True, config=chart_config)
            
        with col2:
            st.subheader("📊 Volume por Área")
            st.plotly_chart(plot_pro(df.tail(30), 'dia', 'bar'), use_container_width=True, config=chart_config)
            
        # Tabela Detalhada
        with st.expander("📄 Ver histórico completo"):
            st.dataframe(df.sort_values('data', ascending=False), use_container_width=True)
    else:
        st.info("Ainda não há dados suficientes para gerar os gráficos. Comece a registrar seus estudos na barra lateral!")