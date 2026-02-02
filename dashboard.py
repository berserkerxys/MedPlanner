import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from database import get_status_gamer, get_dados_graficos, get_benchmark_dados

def plot_pro(dataframe, col, tipo='bar'):
    # --- BLINDAGEM CONTRA ERRO DE COLUNA ---
    # Trabalha com uma cópia para evitar SettingWithCopyWarning
    df_chart = dataframe.copy()
    
    # Se a coluna 'area' não existir, cria com valor padrão
    if 'area' not in df_chart.columns:
        if 'area_manual' in df_chart.columns:
            df_chart['area'] = df_chart['area_manual'].fillna('Geral')
        else:
            df_chart['area'] = 'Geral'
            
    # Garante que não sobrou nenhum Nulo/NaN
    df_chart['area'] = df_chart['area'].fillna('Geral')
    # ---------------------------------------

    # Agrupamento seguro
    df_g = df_chart.groupby([col, 'area']).agg({'acertos':'sum', 'total':'sum'}).reset_index()
    df_g['%'] = (df_g['acertos'] / df_g['total'] * 100).round(1)
    
    if tipo == 'line': 
        fig = px.line(df_g, x=col, y='%', color='area', markers=True, template="plotly_white")
    else: 
        fig = px.bar(df_g, x=col, y='total', color='area', barmode='group', template="plotly_white")
    
    fig.update_layout(height=350, margin=dict(l=0,r=0,t=20,b=0))
    return fig

def plot_radar(df):
    fig = go.Figure()
    ud = df[df['Tipo']=='Você']
    fig.add_trace(go.Scatterpolar(r=ud['Performance'], theta=ud['Area'], fill='toself', name='Você'))
    cd = df[df['Tipo']=='Comunidade']
    fig.add_trace(go.Scatterpolar(r=cd['Performance'], theta=cd['Area'], fill='toself', name='Média'))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), height=400, margin=dict(t=20, b=20))
    return fig

def render_dashboard(conn_ignored):
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    # Busca dados (agora mais robusto no database.py também)
    df = get_dados_graficos(u, nonce)
    
    # Busca status atualizado do gamer (incluindo meta diária do banco)
    status, df_m = get_status_gamer(u, nonce)
    
    # Se estiver vazio, não tenta renderizar nada que possa quebrar
    if df.empty and df_m.empty:
        st.info("Sem dados suficientes. Registre seus primeiros estudos na barra lateral ou agenda!")
        return

    # Garante que a coluna 'area' existe no dataframe principal antes de dividir nas abas
    if not df.empty and 'area' not in df.columns:
        df['area'] = df.get('area_manual', 'Geral').fillna('Geral')

    # --- KPIs SUPERIORES (META DIÁRIA) ---
    if not df_m.empty:
        st.subheader("🚀 Missões do Dia")
        cols = st.columns(3)
        row = df_m.iloc[0]
        
        # A meta aqui vem de 'get_status_gamer', que lê do banco
        meta_banco = int(status.get('meta_diaria', 50))
        progresso_hoje = int(row['Prog'])
        
        cols[0].metric("Meta Diária", f"{progresso_hoje} / {meta_banco}")
        cols[1].progress(min(progresso_hoje/meta_banco, 1.0) if meta_banco > 0 else 0)
        
        # XP Ganho Hoje
        xp_hoje = progresso_hoje * 2 # Exemplo de cálculo simples
        cols[2].metric("XP Gerado", f"+{xp_hoje} XP")

    st.divider()

    st.subheader("⚖️ Comparativo (Benchmark)")
    try:
        df_bench = get_benchmark_dados(u, df)
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(plot_radar(df_bench), use_container_width=True)
        with c2: st.dataframe(df_bench.pivot(index='Area', columns='Tipo', values='Performance'), use_container_width=True)
    except Exception as e:
        st.error(f"Erro ao gerar benchmark: {e}")
    
    st.divider()
    
    if not df.empty:
        st.subheader("📈 Evolução Temporal")
        
        t1, t2, t3 = st.tabs(["Diário", "Semanal", "Mensal"])
        
        # Tratamento de datas seguro
        if 'data' in df.columns:
            df['data'] = pd.to_datetime(df['data'])
            
            with t1: 
                df['d'] = df['data'].dt.strftime('%d/%m')
                # Passa df.tail(30) que é uma fatia, mas o plot_pro agora faz .copy()
                st.plotly_chart(plot_pro(df.tail(30), 'd', 'line'), use_container_width=True)
            with t2:
                df['s'] = df['data'].dt.to_period('W').apply(lambda r: r.start_time.strftime('%d/%m'))
                st.plotly_chart(plot_pro(df, 's', 'bar'), use_container_width=True)
            with t3:
                df['m'] = df['data'].dt.strftime('%m/%Y')
                st.plotly_chart(plot_pro(df, 'm', 'bar'), use_container_width=True)