import streamlit as st
import pandas as pd
import time # CORREÇÃO: Adicionado o import de time que estava faltando
from database import (
    get_cronograma_status, 
    salvar_cronograma_status, 
    get_lista_assuntos_nativa,
    get_area_por_assunto,
    registrar_estudo,
    calcular_meta_questoes
)

def render_cronograma(conn_ignored):
    st.header("🗂️ Cronograma de Estudos")
    u = st.session_state.username
    
    # 1. Carregamento de Dados e Estado
    try:
        from aulas_medcof import DADOS_LIMPOS
        df_aulas = pd.DataFrame(DADOS_LIMPOS, columns=['Aula', 'Area', 'Prioridade'])
    except:
        st.error("Erro ao carregar aulas_medcof.py")
        return
        
    estado = get_cronograma_status(u)
    
    # 2. Filtros Superiores
    c1, c2, c3 = st.columns([2, 1, 1])
    busca = c1.text_input("🔍 Buscar aula ou tema...", placeholder="Ex: Diabetes, Trauma...")
    area_f = c2.selectbox("Área:", ["Todas"] + sorted(df_aulas['Area'].unique().tolist()))
    prio_f = c3.selectbox("Prioridade:", ["Todas", "Diamante", "Verde (Alta)", "Amarelo (Média)", "Vermelho (Baixa)"])

    # 3. Lógica de Filtragem
    df_f = df_aulas.copy()
    if area_f != "Todas": df_f = df_f[df_f['Area'] == area_f]
    if prio_f != "Todas":
        prio_map = {"Diamante": "Diamante", "Verde (Alta)": "Verde", "Amarelo (Média)": "Amarelo", "Vermelho (Baixa)": "Vermelho"}
        df_f = df_f[df_f['Prioridade'] == prio_map[prio_f]]
    if busca:
        df_f = df_f[df_f['Aula'].str.contains(busca, case=False)]

    # 4. Painel de Progresso Geral
    total_aulas = len(df_aulas)
    feitas = sum(1 for a in estado.values() if a.get('feito'))
    progresso_total = feitas / total_aulas if total_aulas > 0 else 0
    
    st.markdown(f"### Progresso Geral: {feitas}/{total_aulas} ({progresso_total:.1%})")
    st.progress(progresso_total)
    
    st.divider()

    # 5. Cores de Prioridade
    cor_prio = {
        "Diamante": "#9b59b6", # Roxo
        "Verde": "#2ecc71",    # Alta
        "Amarelo": "#f1c40f",  # Média
        "Vermelho": "#e74c3c"  # Baixa
    }

    for area in sorted(df_f['Area'].unique()):
        with st.expander(f"📁 {area.upper()}", expanded=(area_f != "Todas")):
            aulas_area = df_f[df_f['Area'] == area]
            
            for _, row in aulas_area.iterrows():
                aula = row['Aula']
                prio = row['Prioridade']
                dados = estado.get(aula, {"feito": False, "acertos_pre": 0, "total_pre": 0, "acertos_pos": 0, "total_pos": 0})
                
                with st.container(border=True):
                    col1, col2, col3 = st.columns([0.05, 0.65, 0.3])
                    
                    # Checkbox de Conclusão
                    novo_feito = col1.checkbox("", value=dados.get('feito', False), key=f"chk_{aula}")
                    if novo_feito != dados.get('feito'):
                        dados['feito'] = novo_feito
                        estado[aula] = dados
                        salvar_cronograma_status(u, estado)
                        st.rerun()

                    # Título e Badge
                    with col2:
                        st.markdown(f"**{aula}** <span style='background-color:{cor_prio.get(prio, '#666')}; color:white; padding:2px 6px; border-radius:4px; font-size:10px;'>{prio}</span>", unsafe_allow_html=True)
                        pre = dados.get('acertos_pre', 0)
                        pos = dados.get('acertos_pos', 0)
                        st.caption(f"📊 Pré: {pre}/{dados.get('total_pre', 0)} | Pós: {pos}/{dados.get('total_pos', 0)}")

                    # Lançamento de Notas
                    with col3:
                        with st.popover("📝 Lançar"):
                            m_pre, m_pos = calcular_meta_questoes(prio)
                            st.caption(f"Metas: Pré {m_pre}q | Pós {m_pos}q")
                            t_estudo = st.radio("Fase:", ["Pre-Aula", "Pos-Aula"], key=f"rad_{aula}")
                            c_ac, c_tot = st.columns(2)
                            ac = c_ac.number_input("Acertos", 0, 100, 0, key=f"ac_{aula}")
                            tot = c_tot.number_input("Total", 1, 100, 10, key=f"tot_{aula}")
                            
                            if st.button("Salvar", key=f"btn_{aula}", use_container_width=True):
                                msg = registrar_estudo(u, aula, ac, tot, tipo_estudo=t_estudo, srs=True)
                                st.success(msg)
                                time.sleep(0.5) # Agora o 'time' está definido!
                                st.rerun()

    if st.button("💾 Sincronizar Cronograma", use_container_width=True):
        salvar_cronograma_status(u, estado)
        st.success("Salvo!")