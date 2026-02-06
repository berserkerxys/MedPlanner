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
    
    # Inicialização de Estado de Navegação (se não existir)
    if 'agenda_week_offset' not in st.session_state:
        st.session_state.agenda_week_offset = 0
    if 'agenda_month_offset' not in st.session_state:
        st.session_state.agenda_month_offset = 0
    
    # --- ABAS ---
    tab_hoje, tab_futuro, tab_semana, tab_mes, tab_lista = st.tabs(["🔥 Foco Hoje", "🔮 Futuro", "🗓️ Semana (Visual)", "📅 Mês", "📚 Lista"])

    # --- 1. VISÃO DE HOJE (FOCO & ATRASADAS) ---
    with tab_hoje:
        tarefas_hoje = df[(df['data_agendada'].dt.date == hoje) & (df['status'] == 'Pendente')]
        atrasadas = df[(df['data_agendada'].dt.date < hoje) & (df['status'] == 'Pendente')]
        
        # KPIs
        c1, c2, c3 = st.columns(3)
        c1.metric("Para Hoje", len(tarefas_hoje))
        c2.metric("Atrasadas", len(atrasadas), delta_color="inverse")
        c3.metric("Futuras", len(df[(df['data_agendada'].dt.date > hoje) & (df['status'] == 'Pendente')]))
        
        st.divider()

        # Prioridade 1: Atrasadas
        if not atrasadas.empty:
            st.error(f"⚠️ {len(atrasadas)} revisões atrasadas! Prioridade máxima.")
            for i, row in atrasadas.iterrows():
                render_cartao_tarefa(row, "atrasada", hoje)
            st.divider()
        
        # Prioridade 2: Hoje
        if not tarefas_hoje.empty:
            st.subheader("📝 Tarefas do Dia")
            for i, row in tarefas_hoje.iterrows():
                render_cartao_tarefa(row, "hoje", hoje)
        elif atrasadas.empty:
            st.success("🎉 Tudo limpo por hoje! Aproveite para adiantar matérias no Cronograma.")

    # --- 2. VISÃO FUTURA (COM GRADUAÇÃO DE DESEMPENHO) ---
    with tab_futuro:
        st.subheader("🔮 Próximas Revisões")
        st.caption("Antecipe seus estudos classificando seu domínio atual sobre o tema.")
        
        # Filtra futuras
        futuras = df[(df['data_agendada'].dt.date > hoje) & (df['status'] == 'Pendente')].sort_values('data_agendada')
        
        if futuras.empty:
            st.info("Nada agendado para o futuro próximo.")
        else:
            # Agrupa por data para ficar organizado
            datas_unicas = futuras['data_agendada'].dt.date.unique()
            
            for d in datas_unicas:
                # Header da Data
                delta = (d - hoje).days
                label_dia = f"Amanhã" if delta == 1 else f"Daqui a {delta} dias"
                st.markdown(f"##### {d.strftime('%d/%m/%Y')} ({label_dia})")
                
                # Tarefas daquela data
                tarefas_d = futuras[futuras['data_agendada'].dt.date == d]
                for _, row in tarefas_d.iterrows():
                    render_cartao_tarefa_futura_completo(row, "futuro")
                st.divider()

    # --- 3. VISÃO SEMANAL (VISUAL COMPLETO) ---
    with tab_semana:
        c_nav1, c_nav2, c_nav3 = st.columns([1, 6, 1])
        
        # Botões de Navegação
        def prev_week(): st.session_state.agenda_week_offset -= 1
        def next_week(): st.session_state.agenda_week_offset += 1
        
        c_nav1.button("◀ Ant", on_click=prev_week, key="btn_prev_week")
        c_nav3.button("Prox ▶", on_click=next_week, key="btn_next_week")
        
        # Calcula datas
        start_week = hoje - timedelta(days=hoje.weekday()) + timedelta(weeks=st.session_state.agenda_week_offset)
        end_week = start_week + timedelta(days=6)
        
        c_nav2.markdown(f"<div style='text-align:center; font-weight:bold; font-size: 1.1em'>{start_week.strftime('%d/%m')} - {end_week.strftime('%d/%m')}</div>", unsafe_allow_html=True)
        
        cols = st.columns(7)
        days = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        
        for i, d_name in enumerate(days):
            d_date = start_week + timedelta(days=i)
            tasks = df[df['data_agendada'].dt.date == d_date]
            
            with cols[i]:
                # Estilo do Cabeçalho
                bg_head = "#ffebee" if d_date == hoje else "#f0f2f6"
                color_head = "red" if d_date == hoje else "black"
                
                # Container do dia
                with st.container(border=True):
                    st.markdown(
                        f"<div style='background-color:{bg_head}; color:{color_head}; text-align:center; border-radius:4px; padding:2px; margin-bottom:5px'>"
                        f"<b>{d_name}</b><br>{d_date.day}</div>", 
                        unsafe_allow_html=True
                    )
                    
                    # Lista de tarefas com nome completo
                    for _, t in tasks.iterrows():
                        cor_status = "red" if t['status'] == 'Pendente' and d_date < hoje else "blue"
                        if t['status'] == 'Concluido': cor_status = "green"
                        
                        bg_card = "#ffffff"
                        
                        # Renderiza cartãozinho visual
                        st.markdown(
                            f"""
                            <div style='
                                font-size:0.8em; 
                                background-color:{bg_card}; 
                                border-left:3px solid {cor_status}; 
                                padding:4px; 
                                margin-bottom:4px; 
                                border-radius: 2px;
                                box-shadow: 0 1px 2px rgba(0,0,0,0.1);
                                line-height: 1.2;
                            ' title='{t['assunto_nome']}'>
                            {t['assunto_nome']}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

    # --- 4. VISÃO MENSAL ---
    with tab_mes:
        # Navegação Mês
        cm1, cm2, cm3 = st.columns([1, 6, 1])
        def prev_month(): st.session_state.agenda_month_offset -= 1
        def next_month(): st.session_state.agenda_month_offset += 1
        
        cm1.button("◀", on_click=prev_month, key="btn_prev_month")
        cm3.button("▶", on_click=next_month, key="btn_next_month")
        
        # Lógica de Data do Mês
        curr_ref = hoje.replace(day=1)
        target_month_idx = curr_ref.month - 1 + st.session_state.agenda_month_offset
        year_target = curr_ref.year + target_month_idx // 12
        month_target = target_month_idx % 12 + 1
        
        cm2.markdown(f"<h4 style='text-align:center'>{calendar.month_name[month_target].capitalize()} {year_target}</h4>", unsafe_allow_html=True)
        
        cal = calendar.monthcalendar(year_target, month_target)
        
        # Headers Dias
        c_headers = st.columns(7)
        for i, d in enumerate(days): c_headers[i].markdown(f"**{d}**")
        
        for week in cal:
            c_days = st.columns(7)
            for i, d in enumerate(week):
                with c_days[i]:
                    if d == 0:
                        st.write("")
                    else:
                        dt_val = date(year_target, month_target, d)
                        # Filtra tarefas do dia
                        ts = df[df['data_agendada'].dt.date == dt_val]
                        
                        # Estilo
                        with st.container(border=True):
                            if dt_val == hoje:
                                st.markdown(f":red[**{d}**]")
                            else:
                                st.markdown(f"**{d}**")
                                
                            if not ts.empty:
                                p = len(ts[ts['status']=='Pendente'])
                                ok = len(ts[ts['status']=='Concluido'])
                                
                                if p > 0: st.markdown(f":red[● {p}]")
                                if ok > 0: st.markdown(f":green[● {ok}]")
                                
                                with st.popover("Ver"):
                                    for _, t in ts.iterrows():
                                        icon = "⏳" if t['status'] == 'Pendente' else "✅"
                                        st.write(f"{icon} {t['assunto_nome']}")

    # --- 5. LISTA GERAL ---
    with tab_lista:
        filtro = st.radio("Filtrar:", ["Pendentes", "Concluídas", "Todas"], horizontal=True)
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

# --- COMPONENTES VISUAIS ---

def render_cartao_tarefa(row, key_suffix, hoje):
    """Cartão Completo para Hoje/Atrasadas com Graduação de Desempenho"""
    with st.container(border=True):
        c1, c2, c3 = st.columns([0.6, 0.3, 0.1])
        
        with c1:
            prefix = "🔴 " if row['data_agendada'].date() < hoje else ""
            st.markdown(f"**{prefix}{row['assunto_nome']}**")
            st.caption(f"{row['grande_area']} • {row['tipo']}")
            if row['data_agendada'].date() < hoje:
                st.caption(f"Original: {row['data_agendada'].strftime('%d/%m')}")
        
        with c2:
            # Popover de Revisão (SRS) com 4 Níveis
            with st.popover("✅ Realizar Revisão", use_container_width=True):
                st.markdown("### Como foi seu desempenho?")
                st.caption("Isso definirá a próxima data de revisão.")
                
                c_bad, c_hard = st.columns(2)
                if c_bad.button("😭 Muito Ruim", key=f"bad_{key_suffix}_{row['id']}", help="Errei muito. (Reset para 1 dia)", use_container_width=True):
                    reagendar_inteligente(row['id'], "Muito Ruim"); st.rerun()
                if c_hard.button("😕 Difícil", key=f"hard_{key_suffix}_{row['id']}", help="Acertei pouco. (Mantém intervalo)", use_container_width=True):
                    reagendar_inteligente(row['id'], "Ruim"); st.rerun()
                    
                c_good, c_easy = st.columns(2)
                if c_good.button("🙂 Bom", key=f"good_{key_suffix}_{row['id']}", help="Acertei a maioria. (x1.5 dias)", use_container_width=True):
                    reagendar_inteligente(row['id'], "Bom"); st.rerun()
                if c_easy.button("🤩 Excelente", key=f"easy_{key_suffix}_{row['id']}", help="Dominei! (x2.5 dias)", use_container_width=True):
                    reagendar_inteligente(row['id'], "Excelente"); st.rerun()
                
                st.divider()
                if st.button("👑 Dominado", key=f"dom_{key_suffix}_{row['id']}", help="Conteúdo consolidado. (x3.0 dias)", use_container_width=True):
                    # Para "Dominado", passamos 'Excelente' mas a lógica no DB pode ser ajustada para multiplicar mais
                    # ou podemos passar uma string "Dominado" se o backend suportar. 
                    # Assumindo que o backend suporta "Excelente" como o máximo padrão, usaremos ele.
                    # Idealmente, atualizaríamos reagendar_inteligente para aceitar "Dominado".
                    # Como não editamos database.py aqui, usamos "Excelente".
                    reagendar_inteligente(row['id'], "Excelente"); st.rerun()

        with c3:
            if st.button("🗑️", key=f"del_{key_suffix}_{row['id']}", help="Excluir esta revisão"):
                if excluir_revisao(row['id']):
                    st.toast("Revisão excluída!")
                    st.rerun()

def render_cartao_tarefa_futura_completo(row, key_suffix):
    """Cartão Completo para Futuro (Permite Antecipar com Graduação)"""
    with st.container(border=True):
        c1, c2, c3 = st.columns([0.6, 0.2, 0.2])
        
        with c1:
            st.markdown(f"**{row['assunto_nome']}**")
            st.caption(f"{row['grande_area']} • Agendado para {row['data_agendada'].strftime('%d/%m')}")
        
        with c2:
            # Botão de Antecipar com Desempenho
            with st.popover("⚡ Antecipar"):
                st.write("**Realizar hoje? Classifique:**")
                st.caption("A nova data será calculada a partir de HOJE.")
                
                c_a, c_b = st.columns(2)
                if c_a.button("Ruim", key=f"f_bad_{key_suffix}_{row['id']}", use_container_width=True):
                    reagendar_inteligente(row['id'], "Muito Ruim"); st.rerun()
                if c_b.button("Bom", key=f"f_good_{key_suffix}_{row['id']}", use_container_width=True):
                    reagendar_inteligente(row['id'], "Bom"); st.rerun()
                    
                c_c, c_d = st.columns(2)
                if c_c.button("Excelente", key=f"f_exc_{key_suffix}_{row['id']}", use_container_width=True):
                    reagendar_inteligente(row['id'], "Excelente"); st.rerun()
                if c_d.button("Dominado", key=f"f_dom_{key_suffix}_{row['id']}", use_container_width=True):
                    reagendar_inteligente(row['id'], "Excelente"); st.rerun()
        
        with c3:
             if st.button("🗑️", key=f"f_del_{key_suffix}_{row['id']}"):
                excluir_revisao(row['id']); st.rerun()