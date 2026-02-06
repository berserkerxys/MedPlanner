import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import calendar
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
    
    # --- ABAS DE NAVEGAÇÃO ---
    tab_hoje, tab_semana, tab_mes, tab_lista = st.tabs(["🔥 Foco Hoje", "🗓️ Semana", "📅 Mês", "📚 Lista Completa"])

    # --- 1. VISÃO DE HOJE (FOCO) ---
    with tab_hoje:
        tarefas_hoje = df[(df['data_agendada'].dt.date == hoje) & (df['status'] == 'Pendente')]
        atrasadas = df[(df['data_agendada'].dt.date < hoje) & (df['status'] == 'Pendente')]
        
        # KPIs
        c1, c2, c3 = st.columns(3)
        c1.metric("Para Hoje", len(tarefas_hoje))
        c2.metric("Atrasadas", len(atrasadas), delta_color="inverse")
        c3.metric("Futuras", len(df[(df['data_agendada'].dt.date > hoje) & (df['status'] == 'Pendente')]))
        
        st.divider()

        # Renderiza Atrasadas primeiro (Urgência)
        if not atrasadas.empty:
            st.error(f"⚠️ Você tem {len(atrasadas)} revisões atrasadas!")
            for i, row in atrasadas.iterrows():
                render_cartao_tarefa(row, "atrasada", hoje)
        
        # Renderiza Hoje
        if not tarefas_hoje.empty:
            st.subheader("📝 Tarefas do Dia")
            for i, row in tarefas_hoje.iterrows():
                render_cartao_tarefa(row, "hoje", hoje)
        elif atrasadas.empty:
            st.success("🎉 Tudo em dia! Você não tem revisões pendentes para hoje.")

    # --- 2. VISÃO SEMANAL (COLUNAS) ---
    with tab_semana:
        if 'agenda_week_offset' not in st.session_state:
            st.session_state.agenda_week_offset = 0
            
        c_nav1, c_nav2, c_nav3 = st.columns([1, 6, 1])
        if c_nav1.button("◀", key="prev_week"): st.session_state.agenda_week_offset -= 1; st.rerun()
        if c_nav3.button("▶", key="next_week"): st.session_state.agenda_week_offset += 1; st.rerun()
        
        start_week = hoje - timedelta(days=hoje.weekday()) + timedelta(weeks=st.session_state.agenda_week_offset)
        end_week = start_week + timedelta(days=6)
        
        c_nav2.markdown(f"<div style='text-align:center; font-weight:bold'>{start_week.strftime('%d/%m')} - {end_week.strftime('%d/%m')}</div>", unsafe_allow_html=True)
        
        cols = st.columns(7)
        days = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        
        for i, d_name in enumerate(days):
            d_date = start_week + timedelta(days=i)
            # Filtra tarefas
            tasks = df[df['data_agendada'].dt.date == d_date]
            
            with cols[i]:
                # Header do dia
                color = "red" if d_date == hoje else "black"
                st.markdown(f"<div style='text-align:center; color:{color}'>{d_name}<br><b>{d_date.day}</b></div>", unsafe_allow_html=True)
                st.markdown("---")
                
                for _, t in tasks.iterrows():
                    bg = "#e3f2fd" if t['status'] == 'Pendente' else "#e8f5e9"
                    icon = "⏳" if t['status'] == 'Pendente' else "✅"
                    # Tooltip nativo do HTML para detalhes
                    st.markdown(
                        f"""<div style='background-color:{bg}; padding:4px; border-radius:4px; margin-bottom:4px; font-size:0.75em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;' title='{t['assunto_nome']}'>
                        {icon} {t['assunto_nome'][:10]}
                        </div>""", 
                        unsafe_allow_html=True
                    )

    # --- 3. VISÃO MENSAL (CALENDÁRIO GRADE) ---
    with tab_mes:
        if 'agenda_month_offset' not in st.session_state: st.session_state.agenda_month_offset = 0
        
        # Navegação Mês
        cm1, cm2, cm3 = st.columns([1, 6, 1])
        if cm1.button("◀", key="prev_month"): st.session_state.agenda_month_offset -= 1; st.rerun()
        if cm3.button("▶", key="next_month"): st.session_state.agenda_month_offset += 1; st.rerun()
        
        # Calcula mês atual baseado no offset
        curr_date = hoje.replace(day=1) 
        # Lógica simples para mover meses (pode precisar de ajuste fino para virada de ano)
        month_target = (curr_date.month - 1 + st.session_state.agenda_month_offset) % 12 + 1
        year_target = curr_date.year + (curr_date.month - 1 + st.session_state.agenda_month_offset) // 12
        
        cm2.markdown(f"<h4 style='text-align:center'>{calendar.month_name[month_target].capitalize()} {year_target}</h4>", unsafe_allow_html=True)
        
        # Gera matriz do mês
        cal = calendar.monthcalendar(year_target, month_target)
        
        # Cabeçalho Dias
        cols_h = st.columns(7)
        for i, d in enumerate(days): cols_h[i].markdown(f"**{d}**")
        
        # Dias
        for week in cal:
            cols = st.columns(7)
            for i, day in enumerate(week):
                with cols[i]:
                    if day == 0:
                        st.write("")
                    else:
                        d_date = date(year_target, month_target, day)
                        # Filtra tarefas
                        t_day = df[df['data_agendada'].dt.date == d_date]
                        
                        # Estilo do dia
                        border = "2px solid red" if d_date == hoje else "1px solid #ddd"
                        bg_day = "#fff"
                        
                        # Conteúdo do dia
                        with st.container(border=True):
                            st.markdown(f"**{day}**")
                            if not t_day.empty:
                                pend = len(t_day[t_day['status'] == 'Pendente'])
                                done = len(t_day[t_day['status'] == 'Concluido'])
                                if pend > 0: st.markdown(f":red[● {pend}]")
                                if done > 0: st.markdown(f":green[● {done}]")

    # --- 4. LISTA COMPLETA ---
    with tab_lista:
        filtro = st.radio("Mostrar:", ["Pendentes", "Concluídas", "Todas"], horizontal=True)
        
        df_view = df.copy()
        if filtro == "Pendentes": df_view = df_view[df_view['status'] == 'Pendente']
        elif filtro == "Concluídas": df_view = df_view[df_view['status'] == 'Concluido']
        
        st.dataframe(
            df_view[['data_agendada', 'assunto_nome', 'grande_area', 'tipo', 'status']].sort_values('data_agendada'),
            column_config={
                "data_agendada": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "status": st.column_config.TextColumn("Estado"),
            },
            use_container_width=True,
            hide_index=True
        )

def render_cartao_tarefa(row, key_suffix, hoje):
    """Renderiza um cartão individual de tarefa com ações"""
    with st.container(border=True):
        c1, c2, c3 = st.columns([0.6, 0.3, 0.1])
        
        with c1:
            st.markdown(f"**{row['assunto_nome']}**")
            st.caption(f"{row['grande_area']} • {row['tipo']}")
            if row['data_agendada'].date() < hoje:
                st.markdown(":red[Atrasado]")
        
        with c2:
            with st.popover("✅ Revisar"):
                st.write("Desempenho:")
                cb1, cb2 = st.columns(2)
                if cb1.button("😕 Difícil", key=f"h_{key_suffix}_{row['id']}"):
                    reagendar_inteligente(row['id'], "Ruim"); st.rerun()
                if cb2.button("🙂 Bom", key=f"g_{key_suffix}_{row['id']}"):
                    reagendar_inteligente(row['id'], "Bom"); st.rerun()
                if st.button("🤩 Fácil", key=f"e_{key_suffix}_{row['id']}", use_container_width=True):
                    reagendar_inteligente(row['id'], "Excelente"); st.rerun()
        
        with c3:
            if st.button("🗑️", key=f"d_{key_suffix}_{row['id']}"):
                excluir_revisao(row['id']); st.rerun()