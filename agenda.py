import streamlit as st
import pandas as pd
from database import listar_revisoes_completas, concluir_revisao

def render_agenda(conn_ignored):
    st.header("📅 Agenda de Revisões")
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    df = listar_revisoes_completas(u, nonce)

    if df.empty:
        st.info("Registe o seu primeiro estudo para começar!")
        return

    status = st.pills("Visualizar:", ["Pendente", "Concluido"], default="Pendente")
    df_f = df[df['status'] == status].sort_values('data_agendada')

    if df_f.empty:
        st.success("Nada para fazer aqui!")
        return

    for _, row in df_f.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1.5, 1])
            with c1:
                st.markdown(f"**{row['assunto_nome']}**")
                st.caption(f"{row.get('grande_area', 'Geral')} | {row['tipo']}")
            with c2:
                st.info(f"📅 {pd.to_datetime(row['data_agendada']).strftime('%d/%m/%Y')}")
            with c3:
                if row['status'] == 'Pendente':
                    with st.popover("Confirmar"):
                        q_t = st.number_input("Questões", 1, 100, 10, key=f"t_{row['id']}")
                        q_a = st.number_input("Acertos", 0, q_t, 8, key=f"a_{row['id']}")
                        if st.button("Finalizar", key=f"btn_{row['id']}", type="primary"):
                            st.toast(concluir_revisao(row['id'], q_a, q_t))
                            st.rerun()