import streamlit as st
import pandas as pd
from datetime import datetime
from database import listar_revisoes_completas, concluir_revisao

def render_agenda(conn_ignored):
    st.header("📅 Agenda de Revisões")
    u = st.session_state.username
    df = listar_revisoes_completas(u)
    
    if df.empty: st.info("Nenhuma revisão agendada. Use o botão '📅 Agendar' no Cronograma."); return
    
    df['data_agendada'] = pd.to_datetime(df['data_agendada'])
    hoje = pd.to_datetime(datetime.now().date())
    
    tabs = st.tabs(["🔥 Hoje", "⏳ Atrasadas", "📅 Futuras", "📚 Todas"])
    
    def show(dframe, k):
        if dframe.empty: st.write("Vazio."); return
        for i, r in dframe.sort_values('data_agendada').iterrows():
            with st.container():
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.markdown(f"**{r['assunto_nome']}**"); c1.caption(f"{r['tipo']}")
                dt = r['data_agendada'].strftime('%d/%m')
                
                if r['status'] == 'Concluido': c2.success(f"Feito {dt}")
                elif r['data_agendada'] == hoje: c2.warning("Hoje!")
                elif r['data_agendada'] < hoje: c2.error(f"Atrasado {dt}")
                else: c2.info(dt)
                
                if r['status'] == 'Pendente':
                    if c3.button("✅ Feito", key=f"dn_{k}_{r['id']}"):
                        concluir_revisao(r['id'], 0, 0) # Simplificado para check rápido
                        st.rerun()
                st.divider()

    with tabs[0]: show(df[(df['data_agendada']==hoje) & (df['status']=='Pendente')], "hj")
    with tabs[1]: show(df[(df['data_agendada']<hoje) & (df['status']=='Pendente')], "at")
    with tabs[2]: show(df[(df['data_agendada']>hoje) & (df['status']=='Pendente')], "ft")
    with tabs[3]: show(df, "all")