import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import listar_revisoes_completas, concluir_revisao, excluir_revisao, reagendar_inteligente

def render_agenda(conn_ignored):
    st.header("📅 Agenda de Revisões Inteligente")
    st.caption("O sistema agendará a próxima revisão baseada na sua memória (Curva de Esquecimento).")
    
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
                c1, c2, c3 = st.columns([2, 1.5, 2]) # Ajustei colunas para caber os botões
                
                # Info
                with c1:
                    st.markdown(f"**{r['assunto_nome']}**")
                    st.caption(f"{r['grande_area']} • {r['tipo']}")

                # Status
                with c2:
                    dt = r['data_agendada'].strftime('%d/%m')
                    late = r['data_agendada'] < hoje and r['status'] == 'Pendente'
                    if r['status']=='Concluido': st.success(f"Feito {dt}")
                    elif late: st.error(f"Atrasado ({dt})")
                    elif r['data_agendada']==hoje: st.warning("Hoje!")
                    else: st.info(dt)

                # Ações SRS
                with c3:
                    if r['status']=='Pendente':
                        with st.expander("✅ Revisar"):
                            st.write("Como foi seu desempenho?")
                            col_srs1, col_srs2 = st.columns(2)
                            
                            # Botões de Feedback
                            if col_srs1.button("😭 Ruim", key=f"bad_{k}_{r['id']}", help="Errei muito. (Reset)"):
                                ok, dt_prox = reagendar_inteligente(r['id'], "Muito Ruim")
                                if ok: st.toast(f"Reagendado para {dt_prox} (Recuperação)"); st.rerun()
                                
                            if col_srs2.button("😕 Difícil", key=f"hard_{k}_{r['id']}", help="Acertei, mas foi difícil. (x0.5)"):
                                ok, dt_prox = reagendar_inteligente(r['id'], "Ruim")
                                if ok: st.toast(f"Reagendado para {dt_prox}"); st.rerun()
                                
                            col_srs3, col_srs4 = st.columns(2)
                            if col_srs3.button("🙂 Bom", key=f"good_{k}_{r['id']}", help="Acertei bem. (x1.5)"):
                                ok, dt_prox = reagendar_inteligente(r['id'], "Bom")
                                if ok: st.toast(f"Reagendado para {dt_prox}"); st.rerun()
                                
                            if col_srs4.button("🤩 Fácil", key=f"easy_{k}_{r['id']}", help="Dominei! (x2.5)"):
                                ok, dt_prox = reagendar_inteligente(r['id'], "Excelente")
                                if ok: st.toast(f"Reagendado para {dt_prox}"); st.rerun()
                                
                            st.divider()
                            if st.button("🗑️ Excluir", key=f"del_{k}_{r['id']}"):
                                if excluir_revisao(r['id']): st.rerun()
                    else:
                        st.write("✅")
                
                st.divider()

    with t1: show(df[(df['data_agendada']==hoje) & (df['status']=='Pendente')], "hj")
    with t2: show(df[(df['data_agendada']<hoje) & (df['status']=='Pendente')], "at")
    with t3: show(df[(df['data_agendada']>hoje) & (df['status']=='Pendente')], "ft")
    with t4: show(df, "all")