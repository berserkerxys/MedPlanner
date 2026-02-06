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
    # Adicionada a aba "🔮 Futuro"
    tab_hoje, tab_semana, tab_futuro, tab_mes, tab_lista = st.tabs(["🔥 Foco Hoje", "🗓️ Semana", "🔮 Futuro", "📅 Mês", "📚 Lista Completa"])

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
            st.error(f"⚠️ Você tem {len(atrasadas)} revisões atrasadas! Vamos colocar em dia?")
            for i, row in atrasadas.iterrows():
                render_cartao_tarefa(row, "atrasada", hoje)
        
        # Renderiza Hoje
        if not tarefas_hoje.empty:
            st.subheader("📝 Tarefas do Dia")
            for i, row in tarefas_hoje.iterrows():
                render_cartao_tarefa(row, "hoje", hoje)
        elif atrasadas.empty:
            st.success("🎉 Tudo em dia! Você não tem revisões pendentes para hoje. Aproveite para adiantar o Cronograma!")

    # --- 2. VISÃO SEMANAL (COLUNAS) ---
    with tab_semana:
        if 'agenda_week_offset' not in st.session_state:
            st.session_state.agenda_week_offset = 0
            
        c_nav1, c_nav2, c_nav3 = st.columns([1, 6, 1])
        if c_nav1.button("◀ Semana Anterior", key="prev_week"): st.session_state.agenda_week_offset -= 1; st.rerun()
        if c_nav3.button("Próxima Semana ▶", key="next_week"): st.session_state.agenda_week_offset += 1; st.rerun()
        
        start_week = hoje - timedelta(days=hoje.weekday()) + timedelta(weeks=st.session_state.agenda_week_offset)
        end_week = start_week + timedelta(days=6)
        
        c_nav2.markdown(f"<div style='text-align:center; font-weight:bold; font-size: 1.2em'>{start_week.strftime('%d/%m')} - {end_week.strftime('%d/%m')}</div>", unsafe_allow_html=True)
        
        cols = st.columns(7)
        days = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        
        for i, d_name in enumerate(days):
            d_date = start_week + timedelta(days=i)
            # Filtra tarefas
            tasks = df[df['data_agendada'].dt.date == d_date]
            
            with cols[i]:
                # Header do dia
                color = "red" if d_date == hoje else "black"
                bg_header = "#ffebee" if d_date == hoje else "transparent"
                st.markdown(
                    f"<div style='text-align:center; color:{color}; background-color:{bg_header}; border-radius: 8px; padding: 5px;'>"
                    f"<b>{d_name}</b><br><span style='font-size:1.2em'>{d_date.day}</span></div>", 
                    unsafe_allow_html=True
                )
                st.markdown("---")
                
                for _, t in tasks.iterrows():
                    bg = "#e3f2fd" if t['status'] == 'Pendente' else "#e8f5e9"
                    icon = "⏳" if t['status'] == 'Pendente' else "✅"
                    
                    # Cartão clicável na semana (usando expander para detalhes)
                    with st.expander(f"{icon} {t['assunto_nome'][:15]}...", expanded=False):
                        st.caption(f"{t['grande_area']}")
                        st.markdown(f"**{t['assunto_nome']}**")
                        
                        if t['status'] == 'Pendente':
                            st.markdown("**Como foi?**")
                            # Botões de Desempenho Compactos
                            c_s1, c_s2 = st.columns(2)
                            if c_s1.button("👎", key=f"wk_bad_{t['id']}", help="Ruim (Reset ou intervalo curto)"): 
                                reagendar_inteligente(t['id'], "Ruim"); st.rerun()
                            if c_s2.button("👍", key=f"wk_good_{t['id']}", help="Bom (Aumenta intervalo)"): 
                                reagendar_inteligente(t['id'], "Bom"); st.rerun()
                            
                            # Opção extra "Excelente" se quiser mais granularidade no popover
                            if st.button("🌟 Dominei!", key=f"wk_exc_{t['id']}", use_container_width=True):
                                reagendar_inteligente(t['id'], "Excelente"); st.rerun()
                                
                        else:
                            st.caption("Concluído!")

    # --- 3. VISÃO FUTURA (LISTA DE PREVISÃO) ---
    with tab_futuro:
        st.subheader("🔮 Previsão de Revisões Futuras")
        st.caption("Aqui você vê o que está planejado para além da semana atual.")
        
        # Filtra apenas tarefas futuras (> hoje) e pendentes
        futuras = df[(df['data_agendada'].dt.date > hoje) & (df['status'] == 'Pendente')].sort_values('data_agendada')
        
        if futuras.empty:
            st.success("Nada pendente para o futuro próximo! Você está em dia.")
        else:
            # Agrupa por mês para facilitar a visualização
            futuras['mes_ano'] = futuras['data_agendada'].dt.strftime('%B %Y')
            meses_unicos = futuras['mes_ano'].unique()
            
            for mes in meses_unicos:
                with st.expander(f"📅 {mes}", expanded=True):
                    tarefas_mes = futuras[futuras['mes_ano'] == mes]
                    
                    for _, row in tarefas_mes.iterrows():
                        render_cartao_tarefa_futura(row, "futuro")

    # --- 4. VISÃO MENSAL (CALENDÁRIO GRADE) ---
    with tab_mes:
        if 'agenda_month_offset' not in st.session_state: st.session_state.agenda_month_offset = 0
        
        # Navegação Mês
        cm1, cm2, cm3 = st.columns([1, 6, 1])
        if cm1.button("◀ Mês Anterior", key="prev_month"): st.session_state.agenda_month_offset -= 1; st.rerun()
        if cm3.button("Próximo Mês ▶", key="next_month"): st.session_state.agenda_month_offset += 1; st.rerun()
        
        # Calcula mês atual baseado no offset
        curr_date_ref = hoje.replace(day=1)
        total_months = curr_date_ref.year * 12 + curr_date_ref.month - 1 + st.session_state.agenda_month_offset
        year_target = total_months // 12
        month_target = total_months % 12 + 1
        
        cm2.markdown(f"<h3 style='text-align:center'>{calendar.month_name[month_target].capitalize()} {year_target}</h3>", unsafe_allow_html=True)
        
        cal = calendar.monthcalendar(year_target, month_target)
        
        cols_h = st.columns(7)
        days = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        for i, d in enumerate(days): cols_h[i].markdown(f"**{d}**")
        
        for week in cal:
            cols = st.columns(7)
            for i, day in enumerate(week):
                with cols[i]:
                    if day == 0:
                        st.write("")
                    else:
                        d_date = date(year_target, month_target, day)
                        t_day = df[df['data_agendada'].dt.date == d_date]
                        
                        if d_date == hoje:
                            st.markdown(f"🔴 **{day}**")
                        else:
                            st.markdown(f"**{day}**")
                            
                        if not t_day.empty:
                            pend = len(t_day[t_day['status'] == 'Pendente'])
                            done = len(t_day[t_day['status'] == 'Concluido'])
                            if pend > 0: st.markdown(f":red[● {pend}]")
                            if done > 0: st.markdown(f":green[● {done}]")
                            
                            with st.popover("Ver"):
                                for _, t in t_day.iterrows():
                                    icon = "⏳" if t['status'] == 'Pendente' else "✅"
                                    st.write(f"{icon} {t['assunto_nome']}")

    # --- 5. LISTA COMPLETA ---
    with tab_lista:
        c_filt1, c_filt2 = st.columns([1, 3])
        filtro = c_filt1.radio("Filtrar por Status:", ["Pendentes", "Concluídas", "Todas"], horizontal=False)
        
        df_view = df.copy()
        if filtro == "Pendentes": df_view = df_view[df_view['status'] == 'Pendente']
        elif filtro == "Concluídas": df_view = df_view[df_view['status'] == 'Concluido']
        
        st.dataframe(
            df_view[['data_agendada', 'assunto_nome', 'grande_area', 'tipo', 'status']].sort_values('data_agendada'),
            column_config={
                "data_agendada": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "assunto_nome": "Tema",
                "grande_area": "Área",
                "tipo": "Fase SRS",
                "status": st.column_config.TextColumn("Estado"),
            },
            use_container_width=True,
            hide_index=True
        )

def render_cartao_tarefa(row, key_suffix, hoje):
    """Renderiza um cartão individual de tarefa com ações completas de SRS"""
    with st.container(border=True):
        c1, c2, c3 = st.columns([0.6, 0.3, 0.1])
        
        with c1:
            st.markdown(f"**{row['assunto_nome']}**")
            st.caption(f"{row['grande_area']} • {row['tipo']}")
            if row['data_agendada'].date() < hoje:
                st.markdown(":red[**ATRASADO**]")
        
        with c2:
            with st.popover("✅ Realizar Revisão", use_container_width=True):
                st.markdown("### Como foi seu desempenho?")
                st.caption("Isso definirá a próxima data de revisão.")
                
                c_bad, c_hard = st.columns(2)
                if c_bad.button("😭 Muito Ruim", key=f"bad_{key_suffix}_{row['id']}", help="Errei quase tudo. (Reset para 1 dia)", use_container_width=True):
                    reagendar_inteligente(row['id'], "Muito Ruim"); st.rerun()
                if c_hard.button("😕 Difícil", key=f"hard_{key_suffix}_{row['id']}", help="Acertei pouco. (Mantém intervalo)", use_container_width=True):
                    reagendar_inteligente(row['id'], "Ruim"); st.rerun()
                    
                c_good, c_easy = st.columns(2)
                if c_good.button("🙂 Bom", key=f"good_{key_suffix}_{row['id']}", help="Acertei a maioria. (x1.5 dias)", use_container_width=True):
                    reagendar_inteligente(row['id'], "Bom"); st.rerun()
                if c_easy.button("🤩 Excelente", key=f"easy_{key_suffix}_{row['id']}", help="Dominei! (x2.5 dias)", use_container_width=True):
                    reagendar_inteligente(row['id'], "Excelente"); st.rerun()

        with c3:
            if st.button("🗑️", key=f"del_{key_suffix}_{row['id']}", help="Excluir esta revisão"):
                if excluir_revisao(row['id']):
                    st.toast("Revisão excluída!")
                    st.rerun()

def render_cartao_tarefa_futura(row, key_suffix):
    """Cartão simplificado para revisões futuras, permitindo antecipar"""
    with st.container(border=True):
        c1, c2, c3 = st.columns([0.6, 0.2, 0.2])
        
        with c1:
            dt_str = row['data_agendada'].strftime('%d/%m/%Y')
            st.markdown(f"**{dt_str}** - {row['assunto_nome']}")
            st.caption(f"{row['grande_area']}")
        
        with c2:
            # Permite antecipar a revisão usando a mesma lógica de desempenho
            with st.popover("⚡ Antecipar"):
                st.write("Deseja realizar esta revisão hoje?")
                st.caption("Informe seu desempenho:")
                
                c_a, c_b = st.columns(2)
                if c_a.button("👍 Bom", key=f"fut_good_{key_suffix}_{row['id']}"):
                    reagendar_inteligente(row['id'], "Bom"); st.rerun()
                if c_b.button("🤩 Ótimo", key=f"fut_exc_{key_suffix}_{row['id']}"):
                    reagendar_inteligente(row['id'], "Excelente"); st.rerun()
        
        with c3:
            if st.button("🗑️", key=f"fut_del_{key_suffix}_{row['id']}"):
                excluir_revisao(row['id']); st.rerun()