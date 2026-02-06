import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import calendar
from database import listar_revisoes_completas, concluir_revisao, excluir_revisao, reagendar_inteligente

def render_agenda(conn_ignored):
    st.header("📅 Agenda de Revisões")
    
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    # --- OTIMIZAÇÃO DE CARGA ---
    # Carrega TODOS os dados de uma vez e coloca em cache de função (st.cache_data no database.py já ajuda)
    # Aqui garantimos que só processamos datas uma vez por renderização
    df = listar_revisoes_completas(u, nonce)
    
    if df.empty:
        st.info("Sua agenda está vazia! Complete temas no Cronograma para agendar revisões.")
        return
    
    # Processamento ÚNICO de datas para todo o script
    if not pd.api.types.is_datetime64_any_dtype(df['data_agendada']):
        df['data_agendada'] = pd.to_datetime(df['data_agendada'])
    
    hoje = datetime.now().date()
    
    # Pré-cálculo de filtros comuns para agilidade
    mask_pendente = df['status'] == 'Pendente'
    df_pendente = df[mask_pendente]
    
    # --- ESTADO DE NAVEGAÇÃO ---
    if 'agenda_week_offset' not in st.session_state: st.session_state.agenda_week_offset = 0
    if 'agenda_month_offset' not in st.session_state: st.session_state.agenda_month_offset = 0
    
    # --- INTERFACE DE ABAS ---
    # Como 'df' já está na memória, a troca de abas é instantânea visualmente
    tab_hoje, tab_futuro, tab_semana, tab_mes, tab_lista = st.tabs(["🔥 Foco Hoje", "🔮 Futuro", "🗓️ Semana", "📅 Mês", "📚 Lista"])

    # --- 1. HOJE ---
    with tab_hoje:
        # Filtros rápidos em memória
        tarefas_hoje = df_pendente[df_pendente['data_agendada'].dt.date == hoje]
        atrasadas = df_pendente[df_pendente['data_agendada'].dt.date < hoje]
        futuras_count = len(df_pendente[df_pendente['data_agendada'].dt.date > hoje])
        
        # KPIs
        c1, c2, c3 = st.columns(3)
        c1.metric("Para Hoje", len(tarefas_hoje))
        c2.metric("Atrasadas", len(atrasadas), delta_color="inverse")
        c3.metric("Futuras", futuras_count)
        
        st.divider()

        if not atrasadas.empty:
            st.error(f"⚠️ {len(atrasadas)} revisões atrasadas! Prioridade máxima.")
            # Renderiza lista
            for i, row in atrasadas.sort_values('data_agendada').iterrows():
                render_cartao_tarefa(row, "atrasada", hoje)
            st.divider()
        
        if not tarefas_hoje.empty:
            st.subheader("📝 Tarefas do Dia")
            for i, row in tarefas_hoje.iterrows():
                render_cartao_tarefa(row, "hoje", hoje)
        elif atrasadas.empty:
            st.success("🎉 Tudo limpo por hoje!")

    # --- 2. FUTURO ---
    with tab_futuro:
        st.subheader("🔮 Próximas Revisões")
        futuras = df_pendente[df_pendente['data_agendada'].dt.date > hoje].sort_values('data_agendada')
        
        if futuras.empty:
            st.info("Nada agendado para o futuro próximo.")
        else:
            datas_unicas = futuras['data_agendada'].dt.date.unique()
            # Limita a exibição inicial para não travar se tiver mil revisões futuras
            # Mostra os próximos 30 dias com revisões
            MAX_DAYS_SHOW = 15
            
            for i, d in enumerate(datas_unicas):
                if i >= MAX_DAYS_SHOW:
                    st.caption(f"E mais {len(datas_unicas) - MAX_DAYS_SHOW} dias com revisões...")
                    break
                    
                delta = (d - hoje).days
                label_dia = f"Amanhã" if delta == 1 else f"Daqui a {delta} dias"
                
                with st.expander(f"📅 {d.strftime('%d/%m/%Y')} ({label_dia}) - {len(futuras[futuras['data_agendada'].dt.date == d])} tarefas", expanded=(i<3)):
                    tarefas_d = futuras[futuras['data_agendada'].dt.date == d]
                    for _, row in tarefas_d.iterrows():
                        render_cartao_tarefa_futura_completo(row, "futuro")

    # --- 3. SEMANA ---
    with tab_semana:
        c1, c2, c3 = st.columns([1, 6, 1])
        if c1.button("◀ Ant", key="pw"): st.session_state.agenda_week_offset -= 1; st.rerun()
        if c3.button("Prox ▶", key="nw"): st.session_state.agenda_week_offset += 1; st.rerun()
        
        start_week = hoje - timedelta(days=hoje.weekday()) + timedelta(weeks=st.session_state.agenda_week_offset)
        end_week = start_week + timedelta(days=6)
        
        c2.markdown(f"<div style='text-align:center; font-weight:bold; font-size:1.1em'>{start_week.strftime('%d/%m')} - {end_week.strftime('%d/%m')}</div>", unsafe_allow_html=True)
        
        # Filtra dataframe para a semana inteira de uma vez (muito mais rápido que filtrar dia a dia dentro do loop)
        # Convertendo start_week e end_week para datetime64 para comparação eficiente
        mask_week = (df['data_agendada'].dt.date >= start_week) & (df['data_agendada'].dt.date <= end_week)
        df_week = df[mask_week]
        
        cols = st.columns(7)
        days_names = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        
        for i, d_name in enumerate(days_names):
            d_date = start_week + timedelta(days=i)
            # Filtro rápido local
            tasks = df_week[df_week['data_agendada'].dt.date == d_date]
            
            with cols[i]:
                bg_head = "#ffebee" if d_date == hoje else "#f0f2f6"
                color_head = "red" if d_date == hoje else "black"
                
                with st.container(border=True):
                    st.markdown(
                        f"<div style='background-color:{bg_head}; color:{color_head}; text-align:center; border-radius:4px; padding:2px; margin-bottom:5px'>"
                        f"<b>{d_name}</b><br>{d_date.day}</div>", 
                        unsafe_allow_html=True
                    )
                    
                    if tasks.empty:
                        st.caption("-")
                    else:
                        for _, t in tasks.iterrows():
                            cor_status = "red" if t['status'] == 'Pendente' and d_date < hoje else "blue"
                            if t['status'] == 'Concluido': cor_status = "green"
                            
                            # Renderiza cartão simplificado
                            st.markdown(
                                f"""
                                <div style='
                                    font-size:0.75em; 
                                    background-color:white; 
                                    border-left:3px solid {cor_status}; 
                                    padding:3px; 
                                    margin-bottom:3px; 
                                    border-radius: 2px;
                                    line-height: 1.1;
                                    overflow:hidden;
                                    white-space:nowrap;
                                    text-overflow:ellipsis;
                                ' title='{t['assunto_nome']}'>
                                {t['assunto_nome']}
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

    # --- 4. MÊS ---
    with tab_mes:
        c1, c2, c3 = st.columns([1, 6, 1])
        if c1.button("◀", key="pm"): st.session_state.agenda_month_offset -= 1; st.rerun()
        if c3.button("▶", key="nm"): st.session_state.agenda_month_offset += 1; st.rerun()
        
        curr_ref = hoje.replace(day=1)
        tot_months = curr_ref.year * 12 + curr_ref.month - 1 + st.session_state.agenda_month_offset
        y_target = tot_months // 12
        m_target = tot_months % 12 + 1
        
        c2.markdown(f"<h4 style='text-align:center'>{calendar.month_name[m_target].capitalize()} {y_target}</h4>", unsafe_allow_html=True)
        
        cal = calendar.monthcalendar(y_target, m_target)
        
        # Filtro otimizado para o mês inteiro
        start_month = date(y_target, m_target, 1)
        # Hack simples para pegar o último dia do mês
        if m_target == 12: end_month = date(y_target + 1, 1, 1) - timedelta(days=1)
        else: end_month = date(y_target, m_target + 1, 1) - timedelta(days=1)
        
        mask_month = (df['data_agendada'].dt.date >= start_month) & (df['data_agendada'].dt.date <= end_month)
        df_month = df[mask_month]
        
        cols_h = st.columns(7)
        for i, d in enumerate(["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]): cols_h[i].markdown(f"**{d}**")
        
        for week in cal:
            c_days = st.columns(7)
            for i, d in enumerate(week):
                with c_days[i]:
                    if d == 0:
                        st.write("")
                    else:
                        dt_val = date(y_target, m_target, d)
                        # Filtro local no subset do mês
                        ts = df_month[df_month['data_agendada'].dt.date == dt_val]
                        
                        with st.container(border=True):
                            color_d = ":red" if dt_val == hoje else ""
                            st.markdown(f"{color_d}[**{d}**]")
                                
                            if not ts.empty:
                                p = len(ts[ts['status']=='Pendente'])
                                ok = len(ts[ts['status']=='Concluido'])
                                if p > 0: st.markdown(f":red[● {p}]")
                                if ok > 0: st.markdown(f":green[● {ok}]")
                                
                                # Popover leve apenas com lista
                                with st.popover("Ver"):
                                    for _, t in ts.iterrows():
                                        icon = "⏳" if t['status'] == 'Pendente' else "✅"
                                        st.caption(f"{icon} {t['assunto_nome']}")

    # --- 5. LISTA ---
    with tab_lista:
        filtro = st.radio("Filtro:", ["Pendentes", "Concluídas", "Todas"], horizontal=True)
        df_v = df.copy()
        if filtro == "Pendentes": df_v = df_v[df_v['status']=='Pendente']
        elif filtro == "Concluídas": df_v = df_v[df_v['status']=='Concluido']
        
        st.dataframe(
            df_v[['data_agendada', 'assunto_nome', 'grande_area', 'tipo', 'status']].sort_values('data_agendada'),
            column_config={
                "data_agendada": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "status": st.column_config.TextColumn("Estado"),
            },
            use_container_width=True,
            hide_index=True
        )

# --- COMPONENTES ---

def render_cartao_tarefa(row, key_suffix, hoje):
    with st.container(border=True):
        c1, c2, c3 = st.columns([0.6, 0.3, 0.1])
        with c1:
            prefix = "🔴 " if row['data_agendada'].date() < hoje else ""
            st.markdown(f"**{prefix}{row['assunto_nome']}**")
            st.caption(f"{row['grande_area']} • {row['tipo']}")
        with c2:
            with st.popover("✅ Realizar"):
                st.write("Desempenho:")
                c_a, c_b = st.columns(2)
                if c_a.button("😭 Ruim", key=f"bd_{key_suffix}_{row['id']}"): reagendar_inteligente(row['id'], "Muito Ruim"); st.rerun()
                if c_b.button("😕 Difícil", key=f"hd_{key_suffix}_{row['id']}"): reagendar_inteligente(row['id'], "Ruim"); st.rerun()
                c_c, c_d = st.columns(2)
                if c_c.button("🙂 Bom", key=f"gd_{key_suffix}_{row['id']}"): reagendar_inteligente(row['id'], "Bom"); st.rerun()
                if c_d.button("🤩 Ótimo", key=f"ex_{key_suffix}_{row['id']}"): reagendar_inteligente(row['id'], "Excelente"); st.rerun()
        with c3:
            if st.button("🗑️", key=f"dl_{key_suffix}_{row['id']}"): excluir_revisao(row['id']); st.rerun()

def render_cartao_tarefa_futura_completo(row, key_suffix):
    with st.container(border=True):
        c1, c2, c3 = st.columns([0.6, 0.2, 0.2])
        with c1:
            st.markdown(f"**{row['assunto_nome']}**")
            st.caption(f"{row['grande_area']} • {row['data_agendada'].strftime('%d/%m')}")
        with c2:
            with st.popover("⚡ Antecipar"):
                st.write("Realizar hoje?")
                c_a, c_b = st.columns(2)
                if c_a.button("Ruim", key=f"fbd_{key_suffix}_{row['id']}"): reagendar_inteligente(row['id'], "Muito Ruim"); st.rerun()
                if c_b.button("Bom", key=f"fgd_{key_suffix}_{row['id']}"): reagendar_inteligente(row['id'], "Bom"); st.rerun()
                c_c, c_d = st.columns(2)
                if c_c.button("Excelente", key=f"fex_{key_suffix}_{row['id']}"): reagendar_inteligente(row['id'], "Excelente"); st.rerun()
                if c_d.button("Dominado", key=f"fdo_{key_suffix}_{row['id']}"): reagendar_inteligente(row['id'], "Excelente"); st.rerun()
        with c3:
             if st.button("🗑️", key=f"fdl_{key_suffix}_{row['id']}"): excluir_revisao(row['id']); st.rerun()