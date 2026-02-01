import streamlit as st
import pandas as pd
from datetime import datetime
from database import listar_revisoes_completas, concluir_revisao

def render_agenda(conn_ignored):
    st.header("📅 Minha Agenda de Revisões")
    
    u = st.session_state.username
    nonce = st.session_state.data_nonce
    
    # Carregar dados
    df = listar_revisoes_completas(u, nonce)
    
    if df.empty:
        st.info("Você ainda não tem revisões agendadas. Complete um tema na barra lateral para gerar o primeiro ciclo!")
        return

    # Preparação dos dados
    df['data_agendada'] = pd.to_datetime(df['data_agendada'])
    hoje = pd.to_datetime(datetime.now().date())

    # --- SISTEMA DE FILTROS ---
    aba_hoje, aba_pendentes, aba_futuras, aba_todas = st.tabs([
        "🔥 Hoje", "⏳ Pendentes", "📅 Futuras", "📚 Todas"
    ])

    def exibir_tabela_revisao(dataframe, chave_aba):
        if dataframe.empty:
            st.write("Nada por aqui! 😌")
            return
        
        # Ordenar por data mais antiga primeiro
        dataframe = dataframe.sort_values('data_agendada')
        
        for idx, row in dataframe.iterrows():
            with st.container():
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.markdown(f"**{row['assunto_nome']}**")
                    st.caption(f"📂 {row['grande_area']} | 🕒 {row['tipo']}")
                
                with col2:
                    dt_str = row['data_agendada'].strftime('%d/%m/%Y')
                    if row['data_agendada'] < hoje and row['status'] == 'Pendente':
                        st.error(f"Atrasado: {dt_str}")
                    else:
                        st.info(dt_str)

                with col3:
                    if row['status'] == 'Pendente':
                        # Form com inputs de acertos/total para a revisão
                        with st.popover("Concluir"):
                            ac = st.number_input("Acertos", 0, 100, 10, key=f"ac_{chave_aba}_{row['id']}")
                            tot = st.number_input("Total", 1, 100, 10, key=f"tot_{chave_aba}_{row['id']}")
                            if st.button("Confirmar", key=f"btn_{chave_aba}_{row['id']}"):
                                res = concluir_revisao(row['id'], ac, tot)
                                st.success(res)
                                st.rerun()
                    else:
                        st.success("Concluído")
                st.divider()

    # Lógica de Filtragem
    with aba_hoje:
        df_hoje = df[(df['data_agendada'] == hoje) & (df['status'] == 'Pendente')]
        exibir_tabela_revisao(df_hoje, "hoje")

    with aba_pendentes:
        df_atrasadas = df[(df['data_agendada'] < hoje) & (df['status'] == 'Pendente')]
        exibir_tabela_revisao(df_atrasadas, "pend")

    with aba_futuras:
        df_futuras = df[(df['data_agendada'] > hoje) & (df['status'] == 'Pendente')]
        exibir_tabela_revisao(df_futuras, "fut")

    with aba_todas:
        exibir_tabela_revisao(df, "todas")