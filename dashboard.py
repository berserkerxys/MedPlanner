import streamlit as st
import plotly.express as px
import time
from database import get_status_gamer, get_dados_graficos, listar_conteudo_videoteca

def render_dashboard(conn_ignored):
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    # --- SISTEMA DE PRÉ-CARREGAMENTO COM BARRA DE PROGRESSO EM TEMPO REAL ---
    # Criamos um container temporário para a tela de loading
    loading_placeholder = st.empty()
    
    with loading_placeholder.container():
        st.markdown("<h3 style='text-align: center;'>🩺 Sincronizando dados médicos...</h3>", unsafe_allow_html=True)
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Passo 1: Status e Perfil Gamer
        status_text.caption("Obtendo perfil do aluno...")
        status, df_m = get_status_gamer(u, nonce)
        progress_bar.progress(25)
        time.sleep(0.2)
        
        # Passo 2: Histórico e Performance
        status_text.caption("Analisando histórico de desempenho...")
        df = get_dados_graficos(u, nonce)
        progress_bar.progress(50)
        time.sleep(0.2)
        
        # Passo 3: Cache da Videoteca
        status_text.caption("Preparando biblioteca de conteúdos...")
        listar_conteudo_videoteca()
        progress_bar.progress(75)
        time.sleep(0.2)
        
        # Passo 4: Finalização da UI
        status_text.caption("Renderizando painel de controle...")
        progress_bar.progress(100)
        time.sleep(0.3)
    
    # Limpa a tela de loading para mostrar o site
    loading_placeholder.empty()

    # --- INÍCIO DA INTERFACE DO DASHBOARD ---
    
    # 1. CABEÇALHO DE STATUS (GAMIFICAÇÃO)
    if status:
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"### 🏆 {status['titulo']} - Nível {status['nivel']}")
            prog_total = status['xp_atual'] / status['xp_proximo']
            st.progress(prog_total, text=f"XP: {status['xp_atual']} / {status['xp_proximo']} para o próximo nível")
        with c2:
            st.metric("XP Total Acumulado", f"{status['xp_total']} pts")

    st.divider()

    # 2. SEÇÃO DE MISSÕES (OBJETIVOS DIÁRIOS)
    st.subheader("🚀 Missões de Hoje")
    if not df_m.empty:
        cols = st.columns(3)
        for i, row in df_m.iterrows():
            with cols[i]:
                with st.container(border=True):
                    st.markdown(f"**{row['Icon']} {row['Meta']}**")
                    prog_m = min(row['Prog'] / row['Objetivo'], 1.0)
                    st.progress(prog_m)
                    st.markdown(f"<p style='text-align: right; font-size: 0.8rem; color: gray;'>{row['Prog']} / {row['Objetivo']}</p>", unsafe_allow_html=True)
    
    st.divider()
    
    # 3. GRÁFICOS PROFISSIONAIS (Cores de Alto Contraste)
    if not df.empty:
        st.subheader("📈 Análise de Performance")
        c1, c2 = st.columns(2)
        
        with c1:
            # Gráfico de Evolução com cor Indigo Profissional
            df_evo = df.groupby(df['data'].dt.date)['percentual'].mean().reset_index()
            fig_line = px.line(df_evo, x='data', y='percentual', 
                              title="Evolução de Aproveitamento (%)",
                              markers=True, line_shape="spline",
                              color_discrete_sequence=["#4f46e5"])
            
            fig_line.update_layout(
                yaxis_range=[0,105], 
                template="plotly_white",
                margin=dict(l=20, r=20, t=40, b=20),
                hovermode="x unified"
            )
            st.plotly_chart(fig_line, use_container_width=True)
            
        with c2:
            # Barras com paleta "Bold" para distinguir as especialidades
            df_area = df.groupby('area')[['acertos', 'total']].sum().reset_index()
            df_area['%'] = (df_area['acertos'] / df_area['total'] * 100).round(1)
            
            fig_bar = px.bar(df_area, x='area', y='%', color='area',
                            title="Desempenho por Especialidade",
                            color_discrete_sequence=px.colors.qualitative.Bold,
                            text_auto='.1f')
            
            fig_bar.update_layout(
                yaxis_range=[0,105], 
                showlegend=False, 
                template="plotly_white",
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # 4. MÉTRICAS TOTAIS (KPIs)
        st.markdown("### 📊 Resumo de Carreira")
        m1, m2, m3 = st.columns(3)
        total_q = df['total'].sum()
        total_a = df['acertos'].sum()
        
        with m1:
            st.metric("Total de Questões", int(total_q))
        with m2:
            st.metric("Total de Acertos", int(total_a))
        with m3:
            media = (total_a/total_q*100) if total_q > 0 else 0
            st.metric("Aproveitamento Geral", f"{media:.1f}%")
    else:
        st.info("Ainda não existem dados de desempenho suficientes para gerar gráficos. Continue a estudar!")