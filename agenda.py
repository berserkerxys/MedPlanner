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
    
    df['data_agendada'] = pd.to_datetime(df['data_agendada'])
    hoje = datetime.now().date()
    
    tab_hoje, tab_semana, tab_futuro, tab_mes, tab_lista = st.tabs(["🔥 Foco Hoje", "🗓️ Semana", "🔮 Futuro", "📅 Mês", "📚 Lista Completa"])

    # --- 1. HOJE ---
    with tab_hoje:
        tarefas_hoje = df[(df['data_agendada'].dt.date == hoje) & (df['status'] == 'Pendente')]
        atrasadas = df[(df['data_agendada'].dt.date < hoje) & (df['status'] == 'Pendente')]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Para Hoje", len(tarefas_hoje))
        c2.metric("Atrasadas", len(atrasadas), delta_color="inverse")
        c3.metric("Futuras", len(df[(df['data_agendada'].dt.date > hoje) & (df['status'] == 'Pendente')]))
        
        st.divider()

        if not atrasadas.empty:
            st.error(f"⚠️ {len(atrasadas)} revisões atrasadas!")
            for i, row in atrasadas.iterrows():
                render_cartao_tarefa(row, "atrasada", hoje)
        
        if not tarefas_hoje.empty:
            st.subheader("📝 Tarefas do Dia")
            for i, row in tarefas_hoje.iterrows():
                render_cartao_tarefa(row, "hoje", hoje)
        elif atrasadas.empty:
            st.success("🎉 Tudo em dia!")

    # --- 2. SEMANA ---
    with tab_semana:
        if 'agenda_week_offset' not in st.session_state: st.session_state.agenda_week_offset = 0
        c1, c2, c3 = st.columns([1, 6, 1])
        if c1.button("◀", key="p_w"): st.session_state.agenda_week_offset -= 1; st.rerun()
        if c3.button("▶", key="n_w"): st.session_state.agenda_week_offset += 1; st.rerun()
        
        start = hoje - timedelta(days=hoje.weekday()) + timedelta(weeks=st.session_state.agenda_week_offset)
        c2.markdown(f"<div style='text-align:center;font-weight:bold'>{start.strftime('%d/%m')} - {(start+timedelta(days=6)).strftime('%d/%m')}</div>", unsafe_allow_html=True)
        
        cols = st.columns(7)
        for i, d_name in enumerate(["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]):
            dt_dia = start + timedelta(days=i)
            with cols[i]:
                color = "red" if dt_dia == hoje else "black"
                st.markdown(f"<div style='text-align:center;color:{color}'>{d_name}<br><b>{dt_dia.day}</b></div>", unsafe_allow_html=True)
                st.markdown("---")
                
                tasks = df[df['data_agendada'].dt.date == dt_dia]
                for _, t in tasks.iterrows():
                    icon = "⏳" if t['status'] == 'Pendente' else "✅"
                    with st.expander(f"{icon} {t['assunto_nome'][:10]}...", expanded=False):
                        st.caption(t['assunto_nome'])
                        if t['status'] == 'Pendente':
                            c_b1, c_b2 = st.columns(2)
                            if c_b1.button("👎", key=f"wk_bad_{t['id']}"): reagendar_inteligente(t['id'], "Ruim"); st.rerun()
                            if c_b2.button("👍", key=f"wk_good_{t['id']}"): reagendar_inteligente(t['id'], "Bom"); st.rerun()

    # --- 3. FUTURO ---
    with tab_futuro:
        st.subheader("🔮 Previsão Futura")
        futuras = df[(df['data_agendada'].dt.date > hoje) & (df['status'] == 'Pendente')].sort_values('data_agendada')
        if futuras.empty: st.success("Nada pendente.")
        else:
            futuras['mes'] = futuras['data_agendada'].dt.strftime('%B %Y')
            for m in futuras['mes'].unique():
                with st.expander(f"📅 {m}", expanded=True):
                    for _, r in futuras[futuras['mes']==m].iterrows():
                        render_cartao_tarefa_futura(r, "fut")

    # --- 4. MÊS ---
    with tab_mes:
        if 'agenda_month_offset' not in st.session_state: st.session_state.agenda_month_offset = 0
        c1, c2, c3 = st.columns([1, 6, 1])
        if c1.button("◀", key="p_m"): st.session_state.agenda_month_offset -= 1; st.rerun()
        if c3.button("▶", key="n_m"): st.session_state.agenda_month_offset += 1; st.rerun()
        
        curr = hoje.replace(day=1)
        tot_m = curr.year * 12 + curr.month - 1 + st.session_state.agenda_month_offset
        y, m = tot_m // 12, tot_m % 12 + 1
        
        c2.markdown(f"<h3 style='text-align:center'>{calendar.month_name[m].capitalize()} {y}</h3>", unsafe_allow_html=True)
        cal = calendar.monthcalendar(y, m)
        cols_h = st.columns(7)
        for i, d in enumerate(["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]): cols_h[i].markdown(f"**{d}**")
        
        for w in cal:
            cols = st.columns(7)
            for i, d in enumerate(w):
                with cols[i]:
                    if d == 0: st.write("")
                    else:
                        dt = date(y, m, d)
                        ts = df[df['data_agendada'].dt.date == dt]
                        border = "2px solid red" if dt == hoje else "1px solid #ddd"
                        with st.container(border=True):
                            st.markdown(f"**{d}**")
                            if not ts.empty:
                                p = len(ts[ts['status']=='Pendente'])
                                if p > 0: st.markdown(f":red[● {p}]")

    # --- 5. LISTA ---
    with tab_lista:
        filtro = st.radio("Filtro:", ["Pendentes", "Concluídas", "Todas"])
        df_v = df.copy()
        if filtro == "Pendentes": df_v = df_v[df_v['status']=='Pendente']
        elif filtro == "Concluídas": df_v = df_v[df_v['status']=='Concluido']
        st.dataframe(df_v[['data_agendada', 'assunto_nome', 'status']].sort_values('data_agendada'), hide_index=True, use_container_width=True)

def render_cartao_tarefa(row, k, hoje):
    with st.container(border=True):
        c1, c2, c3 = st.columns([0.6, 0.3, 0.1])
        with c1:
            st.markdown(f"**{row['assunto_nome']}**")
            st.caption(f"{row['grande_area']}")
            if row['data_agendada'].date() < hoje: st.markdown(":red[**ATRASADO**]")
        with c2:
            with st.popover("✅ Revisar"):
                st.write("Desempenho:")
                c_b1, c_b2 = st.columns(2)
                if c_b1.button("😭 Ruim", key=f"b_{k}_{row['id']}"): reagendar_inteligente(row['id'], "Muito Ruim"); st.rerun()
                if c_b2.button("😕 Difícil", key=f"h_{k}_{row['id']}"): reagendar_inteligente(row['id'], "Ruim"); st.rerun()
                c_g1, c_g2 = st.columns(2)
                if c_g1.button("🙂 Bom", key=f"g_{k}_{row['id']}"): reagendar_inteligente(row['id'], "Bom"); st.rerun()
                if c_g2.button("🤩 Ótimo", key=f"e_{k}_{row['id']}"): reagendar_inteligente(row['id'], "Excelente"); st.rerun()
        with c3:
            if st.button("🗑️", key=f"d_{k}_{row['id']}"): excluir_revisao(row['id']); st.rerun()

def render_cartao_tarefa_futura(row, k):
    with st.container(border=True):
        c1, c2, c3 = st.columns([0.6, 0.2, 0.2])
        with c1:
            st.markdown(f"**{row['data_agendada'].strftime('%d/%m')}** - {row['assunto_nome']}")
            st.caption(f"{row['grande_area']}")
        with c2:
            with st.popover("⚡ Antecipar"):
                st.write("Antecipar revisão?")
                c1, c2 = st.columns(2)
                if c1.button("👎 Ruim", key=f"f_b_{k}_{row['id']}"): reagendar_inteligente(row['id'], "Ruim"); st.rerun()
                if c2.button("👍 Bom", key=f"f_g_{k}_{row['id']}"): reagendar_inteligente(row['id'], "Bom"); st.rerun()
        with c3:
            if st.button("🗑️", key=f"f_d_{k}_{row['id']}"): excluir_revisao(row['id']); st.rerun()