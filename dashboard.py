import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import get_status_gamer, get_progresso_hoje, get_dados_graficos

def render_dashboard(conn_ignored):
    if 'username' not in st.session_state: return
    u = st.session_state.username

    # --- 1. CABEÇALHO GAMIFICADO (HERO SECTION) ---
    perfil, missoes = get_status_gamer(u)
    
    if perfil:
        # Layout de Cartão para o Perfil
        with st.container():
            c_avatar, c_stats = st.columns([1, 4])
            
            with c_avatar:
                # Avatar baseado no nível
                lvl = perfil['nivel']
                avatar = "👶" if lvl < 10 else "👨‍⚕️" if lvl < 50 else "🧙‍♂️"
                st.markdown(f"<div style='font-size: 60px; text-align: center;'>{avatar}</div>", unsafe_allow_html=True)
            
            with c_stats:
                st.markdown(f"### {perfil['titulo']}")
                c_lvl, c_xp = st.columns([1, 3])
                c_lvl.metric("Nível", perfil['nivel'])
                
                # Barra de XP Customizada
                xp_atual = perfil['xp_atual']
                xp_prox = perfil['xp_proximo']
                perc_xp = min(xp_atual / xp_prox, 1.0) if xp_prox > 0 else 0
                
                c_xp.write(f"**XP:** {xp_atual} / {xp_prox}")
                c_xp.progress(perc_xp)

    st.divider()

    # --- 2. PAINEL DE METAS E MISSÕES ---
    col_meta, col_missoes = st.columns([1, 2])
    
    with col_meta:
        # Gauge Chart Limpo
        questoes_hoje = get_progresso_hoje(u)
        meta_hoje = 50 
        
        fig_meta = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = questoes_hoje,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "<b>Meta Diária</b>", 'font': {'size': 16}},
            gauge = {
                'axis': {'range': [None, max(meta_hoje, questoes_hoje + 10)]},
                'bar': {'color': "#10b981"},
                'bgcolor': "white",
                'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': meta_hoje}
            }
        ))
        fig_meta.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig_meta, use_container_width=True)

    with col_missoes:
        st.subheader("📜 Missões Ativas")
        if missoes is None or missoes.empty:
            st.info("Todas as missões foram completadas (ou ainda não geradas).")
        else:
            # Grid de Missões
            for _, m in missoes.iterrows():
                with st.container(border=True):
                    cols_m = st.columns([0.1, 0.7, 0.2])
                    status_icon = "✅" if m['concluida'] else "⚔️"
                    cols_m[0].write(status_icon)
                    cols_m[1].write(f"**{m['descricao']}**")
                    cols_m[2].caption(f"+{m['xp_recompensa']} XP")
                    
                    if not m['concluida']:
                        prog = m['progresso_atual'] / m['meta_valor'] if m['meta_valor'] > 0 else 0
                        st.progress(min(prog, 1.0))

    st.divider()

    # --- 3. GRÁFICOS DE PERFORMANCE (DATA CLEANING) ---
    st.subheader("📊 Análise de Desempenho")
    
    df_perf = get_dados_graficos(u)
    
    if df_perf.empty:
        st.info("Registe o seu primeiro estudo para desbloquear os gráficos!")
    else:
        # Filtra dados para não poluir
        df_areas = df_perf[df_perf['grande_area'].isin(['Cirurgia', 'Clínica Médica', 'G.O.', 'Pediatria', 'Preventiva'])]
        
        if not df_areas.empty:
            # Agrupa por área
            df_agrupado = df_areas.groupby('grande_area')[['acertos', 'total']].sum().reset_index()
            df_agrupado['Nota'] = (df_agrupado['acertos'] / df_agrupado['total'] * 100).round(1)
            
            # Cores Oficiais
            cores_map = {
                'Cirurgia': '#3b82f6', 'Clínica Médica': '#10b981', 
                'G.O.': '#ec4899', 'Pediatria': '#f59e0b', 'Preventiva': '#6366f1'
            }

            c1, c2 = st.columns([2, 1])
            
            with c1:
                fig_bar = px.bar(
                    df_agrupado, x='grande_area', y='Nota', text='Nota', color='grande_area',
                    color_discrete_map=cores_map, title="Aproveitamento por Área (%)"
                )
                fig_bar.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_bar.update_layout(yaxis_range=[0, 110], showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)
                
            with c2:
                fig_pie = px.pie(df_agrupado, values='total', names='grande_area', color='grande_area',
                                 color_discrete_map=cores_map, hole=0.4, title="Volume de Questões")
                st.plotly_chart(fig_pie, use_container_width=True)
        
        # Evolução Temporal Limpa
        df_evo = df_perf.groupby('data_estudo')['percentual'].mean().reset_index()
        # Formata data para remover horas/minutos se existirem
        df_evo['Data'] = pd.to_datetime(df_evo['data_estudo']).dt.strftime('%d/%m')
        
        fig_line = px.line(df_evo, x='Data', y='percentual', markers=True, title="Evolução Diária de Acertos")
        fig_line.update_layout(yaxis_range=[0, 105])
        fig_line.update_traces(line_color="#2563eb", line_width=3)
        st.plotly_chart(fig_line, use_container_width=True)