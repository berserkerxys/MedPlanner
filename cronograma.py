import streamlit as st
import pandas as pd
import time
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
        # DataFrame complexo com todas as colunas
        df_aulas = pd.DataFrame(DADOS_LIMPOS, columns=['Aula', 'Area', 'Prioridade'])
    except Exception as e:
        st.error(f"Erro ao carregar base de aulas: {e}")
        return
        
    estado = get_cronograma_status(u)
    
    # 2. Filtros Superiores (Recuperando a complexidade)
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        busca = st.text_input("🔍 Buscar aula ou tema...", placeholder="Ex: Diabetes, Trauma...")
    with c2:
        area_f = st.selectbox("Filtrar Área:", ["Todas"] + sorted(df_aulas['Area'].unique().tolist()))
    with c3:
        prio_f = st.selectbox("Prioridade:", ["Todas", "Diamante", "Verde (Alta)", "Amarelo (Média)", "Vermelho (Baixa)"])

    # 3. Lógica de Filtragem Multi-nível
    df_f = df_aulas.copy()
    if area_f != "Todas": 
        df_f = df_f[df_f['Area'] == area_f]
    
    if prio_f != "Todas":
        prio_map = {
            "Diamante": "Diamante", 
            "Verde (Alta)": "Verde", 
            "Amarelo (Média)": "Amarelo", 
            "Vermelho (Baixa)": "Vermelho"
        }
        df_f = df_f[df_f['Prioridade'] == prio_map[prio_f]]
        
    if busca:
        df_f = df_f[df_f['Aula'].str.contains(busca, case=False)]

    # 4. Painel de Progresso Geral (Visual Complexo)
    total_aulas = len(df_aulas)
    feitas = sum(1 for a in estado.values() if a.get('feito'))
    progresso_total = feitas / total_aulas if total_aulas > 0 else 0
    
    with st.container(border=True):
        col_m1, col_m2 = st.columns([1, 4])
        col_m1.metric("Aulas Concluídas", f"{feitas}/{total_aulas}")
        with col_m2:
            st.write(f"**Progresso do Curso: {progresso_total:.1%}**")
            st.progress(progresso_total)
    
    st.divider()

    # 5. Cores de Prioridade Solicitadas
    # Verde = Alta, Vermelho = Baixa
    cor_prio = {
        "Diamante": "#9b59b6", # Roxo
        "Verde": "#2ecc71",    # Alta Prioridade
        "Amarelo": "#f1c40f",  # Média
        "Vermelho": "#e74c3c"  # Baixa Prioridade
    }

    # 6. Renderização por Grande Área (Expanders)
    areas_visiveis = sorted(df_f['Area'].unique())
    
    for area in areas_visiveis:
        with st.expander(f"📁 {area.upper()}", expanded=(area_f != "Todas")):
            aulas_area = df_f[df_f['Area'] == area]
            
            for _, row in aulas_area.iterrows():
                aula = row['Aula']
                prio = row['Prioridade']
                dados = estado.get(aula, {"feito": False, "acertos_pre": 0, "total_pre": 0, "acertos_pos": 0, "total_pos": 0})
                
                with st.container(border=True):
                    c_chk, c_txt, c_btn = st.columns([0.05, 0.7, 0.25])
                    
                    # Checkbox de Conclusão Manual
                    novo_feito = c_chk.checkbox("", value=dados.get('feito', False), key=f"chk_{aula}")
                    if novo_feito != dados.get('feito'):
                        dados['feito'] = novo_feito
                        estado[aula] = dados
                        salvar_cronograma_status(u, estado)
                        st.rerun()

                    # Informações da Aula
                    with c_txt:
                        st.markdown(
                            f"**{aula}** <span style='background-color:{cor_prio.get(prio, '#666')}; color:white; padding:2px 6px; border-radius:4px; font-size:10px; margin-left:10px;'>{prio}</span>", 
                            unsafe_allow_html=True
                        )
                        
                        # Sub-indicadores de desempenho
                        pre_ac = dados.get('acertos_pre', 0)
                        pre_tot = dados.get('total_pre', 0)
                        pos_ac = dados.get('acertos_pos', 0)
                        pos_tot = dados.get('total_pos', 0)
                        
                        st.caption(f"🎯 Pré-Aula: {pre_ac}/{pre_tot} | 🏆 Pós-Aula: {pos_ac}/{pos_tot}")

                    # Botão de Ação (Popover de Lançamento)
                    with c_btn:
                        with st.popover("📝 Lançar Notas", use_container_width=True):
                            m_pre, m_pos = calcular_meta_questoes(prio)
                            st.write(f"**Sugestão MedCof:** Pré: {m_pre}q | Pós: {m_pos}q")
                            
                            fase = st.radio("Fase:", ["Pre-Aula", "Pos-Aula"], key=f"fase_{aula}")
                            c_a, c_t = st.columns(2)
                            ac = c_a.number_input("Acertos", 0, 100, 0, key=f"ac_{aula}")
                            tot = c_t.number_input("Total", 1, 100, 10, key=f"tot_{aula}")
                            
                            if st.button("Salvar Questões", key=f"btn_{aula}", use_container_width=True, type="primary"):
                                msg = registrar_estudo(u, aula, ac, tot, tipo_estudo=fase, srs=True)
                                st.success(msg)
                                time.sleep(0.5)
                                st.rerun()

    # 7. Sincronização Global
    st.divider()
    if st.button("💾 Sincronizar Todo o Cronograma", use_container_width=True):
        salvar_cronograma_status(u, estado)
        st.success("Tudo sincronizado com a nuvem!")