import streamlit as st
import pandas as pd
from datetime import datetime
from database import listar_revisoes_completas, concluir_revisao, excluir_revisao

def render_agenda(conn_ignored):
    st.header("📅 Agenda de Revisões")
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    df = listar_revisoes_completas(u, nonce)
    
    if df.empty: st.info("Tudo em dia! Sem revisões pendentes."); return
    
    df['data_agendada'] = pd.to_datetime(df['data_agendada'])
    hoje = pd.to_datetime(datetime.now().date())
    
    t1, t2, t3, t4 = st.tabs(["🔥 Hoje", "⏳ Atrasadas", "📅 Futuras", "📚 Todas"])
    
    def show(dframe, k):
        if dframe.empty: st.write("Nada aqui."); return
        dframe = dframe.sort_values('data_agendada')
        for i, r in dframe.iterrows():
            with st.container():
                c1, c2, c3, c4 = st.columns([2, 1, 1, 0.5])
                c1.markdown(f"**{r['assunto_nome']}**"); c1.caption(f"{r['grande_area']} • {r['tipo']}")
                dt = r['data_agendada'].strftime('%d/%m')
                late = r['data_agendada'] < hoje and r['status'] == 'Pendente'
                if r['status']=='Concluido': c2.success(f"Feito {dt}")
                elif late: c2.error(f"Atrasado {dt}")
                elif r['data_agendada']==hoje: c2.warning("Hoje!")
                else: c2.info(dt)
                
                if r['status']=='Pendente':
                    with c3.popover("Concluir"):
                        ac = st.number_input("Ac", 0, 200, 0, key=f"ac_{k}_{r['id']}")
                        tt = st.number_input("Tot", 1, 200, 10, key=f"tt_{k}_{r['id']}")
                        if st.button("Salvar", key=f"bt_{k}_{r['id']}"):
                            msg = concluir_revisao(r['id'], ac, tt)
                            st.success(msg); st.rerun()
                else: c3.write("✅")
                
                # Botão Excluir (Lixeira)
                if c4.button("🗑️", key=f"del_{k}_{r['id']}", help="Excluir revisão"):
                    if excluir_revisao(r['id']):
                        st.toast("Revisão excluída!", icon="🗑️")
                        st.rerun()
                    else:
                        st.error("Erro ao excluir")
                
                st.divider()

    with t1: show(df[(df['data_agendada']==hoje) & (df['status']=='Pendente')], "hj")
    with t2: show(df[(df['data_agendada']<hoje) & (df['status']=='Pendente')], "at")
    with t3: show(df[(df['data_agendada']>hoje) & (df['status']=='Pendente')], "ft")
    with t4: show(df, "all")