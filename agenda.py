import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import listar_revisoes_completas, concluir_revisao, excluir_revisao, reagendar_inteligente

def render_agenda(conn_ignored):
    st.header("📅 Agenda Semanal de Revisões")
    
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    df = listar_revisoes_completas(u, nonce)
    
    if df.empty:
        st.info("Sua agenda está vazia! Complete temas no Cronograma para agendar revisões.")
        return
    
    # Processamento de Datas
    df['data_agendada'] = pd.to_datetime(df['data_agendada'])
    hoje = datetime.now().date()
    
    # --- NAVEGAÇÃO DE SEMANA ---
    if 'agenda_week_offset' not in st.session_state:
        st.session_state.agenda_week_offset = 0
        
    c_nav1, c_nav2, c_nav3 = st.columns([1, 4, 1])
    if c_nav1.button("⬅️ Anterior"):
        st.session_state.agenda_week_offset -= 1
        st.rerun()
    if c_nav3.button("Próxima ➡️"):
        st.session_state.agenda_week_offset += 1
        st.rerun()
        
    # Calcula intervalo da semana exibida
    start_of_week = hoje - timedelta(days=hoje.weekday()) + timedelta(weeks=st.session_state.agenda_week_offset)
    end_of_week = start_of_week + timedelta(days=6)
    
    with c_nav2:
        st.markdown(f"<h4 style='text-align: center;'>Semana de {start_of_week.strftime('%d/%m')} a {end_of_week.strftime('%d/%m')}</h4>", unsafe_allow_html=True)

    # Filtra revisões desta semana
    # Convertendo para date para comparação
    mask_week = (df['data_agendada'].dt.date >= start_of_week) & (df['data_agendada'].dt.date <= end_of_week)
    df_week = df[mask_week].sort_values('data_agendada')
    
    # Também busca atrasadas (anteriores a hoje e pendentes) para mostrar em alerta
    mask_late = (df['data_agendada'].dt.date < hoje) & (df['status'] == 'Pendente')
    df_late = df[mask_late]

    # --- ALERTAS DE ATRASO ---
    if not df_late.empty:
        with st.expander(f"⚠️ {len(df_late)} Revisões Atrasadas (Clique para ver)", expanded=True):
            for i, r in df_late.iterrows():
                cols = st.columns([3, 1, 1])
                cols[0].error(f"{r['assunto_nome']} ({r['data_agendada'].strftime('%d/%m')})")
                with cols[1].popover("Resolver"):
                    st.write("Reagendar ou Concluir?")
                    if st.button("Concluir Agora", key=f"late_ok_{r['id']}"):
                        reagendar_inteligente(r['id'], "Bom") # Default para atrasadas
                        st.rerun()
                if cols[2].button("🗑️", key=f"late_del_{r['id']}"):
                    excluir_revisao(r['id']); st.rerun()

    st.divider()

    # --- CALENDÁRIO VISUAL (COLUNAS) ---
    dias_semana = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    cols_dias = st.columns(7)
    
    for i, nome_dia in enumerate(dias_semana):
        data_dia = start_of_week + timedelta(days=i)
        is_today = data_dia == hoje
        
        with cols_dias[i]:
            # Cabeçalho do Dia
            if is_today:
                st.markdown(f":red[**{nome_dia}**]")
                st.markdown(f":red[**{data_dia.day}**]")
            else:
                st.markdown(f"**{nome_dia}**")
                st.caption(f"{data_dia.day}")
            
            # Filtra tarefas do dia
            tarefas_dia = df_week[df_week['data_agendada'].dt.date == data_dia]
            
            if tarefas_dia.empty:
                st.caption("—")
            else:
                for idx, row in tarefas_dia.iterrows():
                    status_icon = "✅" if row['status'] == 'Concluido' else "🔲"
                    
                    # Cartão da Tarefa
                    with st.container(border=True):
                        st.caption(f"{row['grande_area'][:10]}...")
                        st.markdown(f"**{row['assunto_nome']}**")
                        
                        if row['status'] == 'Pendente':
                            with st.popover("Revisar"):
                                st.write("Desempenho:")
                                c_fb1, c_fb2 = st.columns(2)
                                if c_fb1.button("😡 Ruim", key=f"bad_{row['id']}"):
                                    reagendar_inteligente(row['id'], "Ruim"); st.rerun()
                                if c_fb2.button("🙂 Bom", key=f"good_{row['id']}"):
                                    reagendar_inteligente(row['id'], "Bom"); st.rerun()
                                if st.button("🤩 Ótimo", key=f"exc_{row['id']}", use_container_width=True):
                                    reagendar_inteligente(row['id'], "Excelente"); st.rerun()
                                st.divider()
                                if st.button("🗑️", key=f"del_{row['id']}"):
                                    excluir_revisao(row['id']); st.rerun()
                        else:
                            st.success("Feito!")