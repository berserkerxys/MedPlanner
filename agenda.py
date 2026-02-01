import streamlit as st
import pandas as pd
from datetime import datetime
from database import listar_revisoes_completas, concluir_revisao

def render_agenda(conn_ignored):
    st.header("📅 Minha Agenda de Revisões")
    
    u = st.session_state.username
    nonce = st.session_state.data_nonce # Garante refresh quando algo muda
    
    df = listar_revisoes_completas(u, nonce)
    
    if df.empty:
        st.info("Tudo limpo! Complete um tema na barra lateral para agendar revisões automáticas.")
        return

    # Processamento de Datas
    df['data_agendada'] = pd.to_datetime(df['data_agendada'])
    hoje = pd.to_datetime(datetime.now().date())
    
    # Abas de Filtro
    tab1, tab2, tab3, tab4 = st.tabs(["🔥 Hoje", "⏳ Pendentes", "📅 Futuras", "📚 Todas"])

    def show_table(dframe, key_suffix):
        if dframe.empty:
            st.write("Nenhuma revisão nesta categoria.")
            return
            
        # Ordena: Atrasadas primeiro
        dframe = dframe.sort_values('data_agendada')
        
        for idx, row in dframe.iterrows():
            with st.container():
                c1, c2, c3 = st.columns([2, 1, 1])
                
                # Coluna 1: Info do Tema
                c1.markdown(f"**{row['assunto_nome']}**")
                c1.caption(f"{row['grande_area']} • {row['tipo']}")
                
                # Coluna 2: Data e Status
                dt_str = row['data_agendada'].strftime('%d/%m')
                is_late = row['data_agendada'] < hoje and row['status'] == 'Pendente'
                
                if row['status'] == 'Concluido':
                    c2.success(f"Feito em {dt_str}")
                elif is_late:
                    c2.error(f"Atrasado ({dt_str})")
                elif row['data_agendada'] == hoje:
                    c2.warning("É Hoje!")
                else:
                    c2.info(f"{dt_str}")

                # Coluna 3: Ação
                if row['status'] == 'Pendente':
                    with c3.popover("Concluir"):
                        st.write("Registrar Desempenho:")
                        # Inputs únicos por linha
                        ac = st.number_input("Acertos", 0, 200, 10, key=f"ac_{key_suffix}_{row['id']}")
                        tot = st.number_input("Total", 1, 200, 10, key=f"tot_{key_suffix}_{row['id']}")
                        
                        if st.button("Salvar", key=f"btn_{key_suffix}_{row['id']}"):
                            msg = concluir_revisao(row['id'], ac, tot)
                            st.success(msg)
                            st.rerun()
                else:
                    c3.write("✅")
                st.divider()

    # Lógica das Abas
    with tab1: # Hoje
        mask = (df['data_agendada'] == hoje) & (df['status'] == 'Pendente')
        show_table(df[mask], "hoje")
        
    with tab2: # Pendentes (Atrasadas)
        mask = (df['data_agendada'] < hoje) & (df['status'] == 'Pendente')
        show_table(df[mask], "pend")
        
    with tab3: # Futuras
        mask = (df['data_agendada'] > hoje) & (df['status'] == 'Pendente')
        show_table(df[mask], "fut")
        
    with tab4: # Todas
        show_table(df, "all")
