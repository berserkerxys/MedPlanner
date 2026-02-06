import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import listar_revisoes_completas, concluir_revisao, excluir_revisao, reagendar_inteligente

def render_agenda(conn_ignored):
    st.header("📅 Agenda de Revisões")
    
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    df = listar_revisoes_completas(u, nonce)
    
    if df.empty:
        st.info("Sua agenda está vazia! Complete temas no Cronograma para agendar revisões.")
        return
    
    # Processamento de Datas
    df['data_agendada'] = pd.to_datetime(df['data_agendada'])
    hoje = datetime.now().date()
    
    # --- 1. VISÃO DE HOJE (FOCO) ---
    tarefas_hoje = df[(df['data_agendada'].dt.date == hoje) & (df['status'] == 'Pendente')]
    atrasadas = df[(df['data_agendada'].dt.date < hoje) & (df['status'] == 'Pendente')]
    
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    col_kpi1.metric("Para Hoje", f"{len(tarefas_hoje)}", delta="Foco Total")
    col_kpi2.metric("Atrasadas", f"{len(atrasadas)}", delta="- Atenção", delta_color="inverse")
    col_kpi3.metric("Total Agendado", f"{len(df[df['status'] == 'Pendente'])}")
    
    st.divider()

    # --- 2. ÁREA DE AÇÃO (HOJE & ATRASADAS) ---
    if not tarefas_hoje.empty or not atrasadas.empty:
        st.subheader("🚀 Foco do Dia")
        
        # Combina atrasadas (prioridade) e hoje
        fila_revisao = pd.concat([atrasadas, tarefas_hoje])
        
        for i, row in fila_revisao.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([0.6, 0.2, 0.2])
                
                # Info do Tema
                with c1:
                    is_late = row['data_agendada'].dt.date < hoje
                    prefix = "🔴 ATRASADO: " if is_late else "🔥 HOJE: "
                    st.markdown(f"**{prefix}{row['assunto_nome']}**")
                    st.caption(f"{row['grande_area']} • {row['tipo']}")
                
                # Botões de Ação Rápida
                with c2:
                    with st.popover("✅ Revisar Agora"):
                        st.write("Como foi seu desempenho?")
                        cb1, cb2 = st.columns(2)
                        if cb1.button("😕 Difícil", key=f"hard_{row['id']}"):
                            reagendar_inteligente(row['id'], "Ruim"); st.rerun()
                        if cb2.button("🙂 Bom", key=f"good_{row['id']}"):
                            reagendar_inteligente(row['id'], "Bom"); st.rerun()
                        if st.button("🤩 Excelente (Fácil)", key=f"exc_{row['id']}", use_container_width=True):
                            reagendar_inteligente(row['id'], "Excelente"); st.rerun()
                
                with c3:
                    if st.button("🗑️", key=f"del_top_{row['id']}", help="Excluir da agenda"):
                        excluir_revisao(row['id']); st.rerun()

    # --- 3. VISÃO SEMANAL (CALENDÁRIO) ---
    st.subheader("🗓️ Visão Semanal")
    
    if 'agenda_week_offset' not in st.session_state:
        st.session_state.agenda_week_offset = 0
        
    # Navegação da Semana
    cn1, cn2, cn3 = st.columns([1, 6, 1])
    if cn1.button("◀"): st.session_state.agenda_week_offset -= 1; st.rerun()
    if cn3.button("▶"): st.session_state.agenda_week_offset += 1; st.rerun()
    
    start_of_week = hoje - timedelta(days=hoje.weekday()) + timedelta(weeks=st.session_state.agenda_week_offset)
    
    with cn2:
        st.markdown(f"<div style='text-align:center; font-weight:bold'>{start_of_week.strftime('%d/%m')} a {(start_of_week + timedelta(days=6)).strftime('%d/%m')}</div>", unsafe_allow_html=True)

    # Grid da Semana
    cols_dias = st.columns(7)
    dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    
    for i, dia_nome in enumerate(dias_semana):
        data_atual = start_of_week + timedelta(days=i)
        
        # Filtra tarefas deste dia específico
        tarefas_dia = df[df['data_agendada'].dt.date == data_atual]
        pendentes_dia = tarefas_dia[tarefas_dia['status'] == 'Pendente']
        concluidas_dia = tarefas_dia[tarefas_dia['status'] == 'Concluido']
        
        with cols_dias[i]:
            # Cabeçalho do dia
            cor_dia = "red" if data_atual == hoje else "black"
            st.markdown(f"<div style='color:{cor_dia}; text-align:center; font-size:0.9em'>{dia_nome}<br><b>{data_atual.day}</b></div>", unsafe_allow_html=True)
            st.markdown("---")
            
            # Bolinhas de Tarefas
            if not pendentes_dia.empty:
                for _, t in pendentes_dia.iterrows():
                    st.markdown(f"<div style='background-color:#E3F2FD; color:#1565C0; padding:4px; border-radius:4px; margin-bottom:4px; font-size:0.75em; text-align:center' title='{t['assunto_nome']}'>{t['assunto_nome'][:10]}..</div>", unsafe_allow_html=True)
            
            if not concluidas_dia.empty:
                st.markdown(f"<div style='color:green; font-size:0.8em; text-align:center'>✅ {len(concluidas_dia)} feitos</div>", unsafe_allow_html=True)

    st.divider()

    # --- 4. LISTA COMPLETA (EXPANSÍVEL) ---
    with st.expander("📚 Ver Todas as Revisões (Histórico e Futuro)"):
        # Filtros rápidos
        filtro = st.radio("Filtrar:", ["Pendentes", "Concluídas", "Todas"], horizontal=True)
        
        df_view = df.copy()
        if filtro == "Pendentes":
            df_view = df_view[df_view['status'] == 'Pendente']
        elif filtro == "Concluídas":
            df_view = df_view[df_view['status'] == 'Concluido']
            
        st.dataframe(
            df_view[['data_agendada', 'assunto_nome', 'grande_area', 'tipo', 'status']].sort_values('data_agendada'),
            column_config={
                "data_agendada": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "assunto_nome": "Tema",
                "grande_area": "Área",
                "tipo": "Etapa",
                "status": "Estado"
            },
            use_container_width=True,
            hide_index=True
        )