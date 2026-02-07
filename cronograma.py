import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
from database import (
    get_cronograma_status, 
    salvar_cronograma_status, 
    normalizar_area, 
    calcular_meta_questoes,
    resetar_revisoes_aula,
    registrar_estudo # Necessário para agendar a revisão no histórico/agenda
)

# Configuração Visual
PRIORIDADES_STYLE = {
    "Diamante": {"icon": "💎", "color": "#9C27B0", "bg": "#F3E5F5", "label": "Diamante"},
    "Vermelho": {"icon": "🔴", "color": "#D32F2F", "bg": "#FFEBEE", "label": "Alta"},
    "Amarelo":  {"icon": "🟡", "color": "#FBC02D", "bg": "#FFFDE7", "label": "Média"},
    "Verde":    {"icon": "🟢", "color": "#388E3C", "bg": "#E8F5E9", "label": "Baixa"},
    "Normal":   {"icon": "⚪", "color": "#757575", "bg": "#F5F5F5", "label": "Normal"}
}

def update_row_callback(u, aula_nome, full_state):
    check = st.session_state.get(f"chk_{aula_nome}", False)
    d_atual = full_state.get(aula_nome, {})
    d_atual["feito"] = check
    full_state[aula_nome] = d_atual
    salvar_cronograma_status(u, full_state)
    st.toast("Progresso salvo!", icon="✅")

def reset_callback(u, aula_nome):
    if resetar_revisoes_aula(u, aula_nome):
        st.toast(f"Ciclo de '{aula_nome}' reiniciado!", icon="🔄")
        # st.rerun() 

def agendar_revisao_callback(u, aula_nome, acertos_total, total_total):
    """
    Marca o estudo como encerrado e agenda a revisão na agenda.
    """
    msg = registrar_estudo(u, aula_nome, acertos_total, total_total, tipo_estudo="Pos-Aula", srs=True)
    
    if "salvo" in msg or "Salvo" in msg:
        st.toast(f"Revisão agendada para {aula_nome}!", icon="📅")
    else:
        st.error(f"Erro ao agendar: {msg}")

def ler_dados_nativos():
    mapa = []
    try:
        import aulas_medcof
        dados_brutos = getattr(aulas_medcof, 'DADOS_LIMPOS', [])
        
        with open('aulas_medcof.py', 'r', encoding='utf-8') as f: lines = f.readlines()
        
        idx = 0
        bloco_atual = "Geral"
        
        for line in lines:
            m = re.search(r'#\s*-+\s*(BLOCO\s*.*)\s*-+', line, re.IGNORECASE)
            if m: bloco_atual = m.group(1).strip()
            
            if idx < len(dados_brutos):
                item = dados_brutos[idx]
                nome = item[0]
                if nome in line:
                    area = item[1]
                    prio = item[2] if len(item) > 2 else "Normal"
                    mapa.append({"Bloco": bloco_atual, "Aula": nome, "Area": area, "Prioridade": prio})
                    idx += 1
        return mapa
    except: return []

def render_cronograma(conn_ignored):
    st.header("🗂️ Cronograma Extensivo")
    
    u = st.session_state.username
    dados_mapa = ler_dados_nativos()
    
    if not dados_mapa: st.warning("Sem dados."); return
    df = pd.DataFrame(dados_mapa)
    estado = get_cronograma_status(u)
    
    # Controle de Visão (Lista vs Blocos)
    if 'cronograma_view_mode' not in st.session_state:
        st.session_state.cronograma_view_mode = "Lista"

    # Header com Controles
    c_head1, c_head2 = st.columns([3, 1])
    with c_head1:
        st.caption("Acompanhe o cumprimento das metas de Pré e Pós aula.")
    with c_head2:
        # Botão para alternar a visão
        label_btn = "📅 Visão Blocos" if st.session_state.cronograma_view_mode == "Lista" else "📝 Visão Lista"
        if st.button(label_btn, use_container_width=True):
            st.session_state.cronograma_view_mode = "Blocos" if st.session_state.cronograma_view_mode == "Lista" else "Lista"
            st.rerun()

    # KPIs Calculados Dinamicamente
    concluidas = sum(1 for k, v in estado.items() if v.get('feito'))
    total_aulas = len(df)
    total_q = sum(v.get('total_pos', 0) + v.get('total_pre', 0) for v in estado.values())
    
    # Barra de Progresso Global Dinâmica
    if total_aulas > 0:
        progresso_percentual = min(concluidas / total_aulas, 1.0)
    else:
        progresso_percentual = 0.0
        
    st.progress(progresso_percentual, text=f"Progresso: {concluidas}/{total_aulas} temas ({int(progresso_percentual*100)}%) | Questões Totais: {total_q}")
    
    st.divider()

    # --- RENDERIZAÇÃO CONDICIONAL ---
    
    if st.session_state.cronograma_view_mode == "Blocos":
        # VISÃO EM BLOCOS (Cards lado a lado)
        blocos = df['Bloco'].unique()
        
        # Filtro de Bloco para não poluir a tela
        bloco_selecionado = st.selectbox("Selecione o Bloco:", blocos)
        
        if bloco_selecionado:
            df_bloco = df[df['Bloco'] == bloco_selecionado]
            
            # Grid de cards (ex: 3 por linha)
            cols = st.columns(3)
            for idx, row in df_bloco.iterrows():
                aula = row['Aula']
                prio = row['Prioridade']
                d = estado.get(aula, {})
                col_idx = idx % 3
                
                with cols[col_idx]:
                    with st.container(border=True):
                        # Cabeçalho do Card
                        st.markdown(f"**{aula}**")
                        
                        # Badge Prioridade
                        style = PRIORIDADES_STYLE.get(prio, PRIORIDADES_STYLE["Normal"])
                        st.markdown(f"<div style='background-color:{style['bg']};color:{style['color']};padding:2px;border-radius:4px;text-align:center;font-size:0.75em;font-weight:bold;margin-bottom:5px'>{style['icon']} {style['label']}</div>", unsafe_allow_html=True)
                        
                        # Checkbox Status
                        is_checked = st.checkbox("Concluído", value=d.get('feito', False), key=f"chk_blk_{aula}", on_change=update_row_callback, args=(u, aula, estado))
                        
                        # Metas e Progresso Compacto
                        desempenho_ant = d.get('ultimo_desempenho')
                        meta_pre, meta_pos = calcular_meta_questoes(prio, desempenho_ant)
                        
                        tt_pre = d.get('total_pre', 0)
                        tt_pos = d.get('total_pos', 0)
                        
                        st.caption(f"Pré: {tt_pre}/{meta_pre} | Pós: {tt_pos}/{meta_pos}")
                        
                        # Ações Compactas
                        c_a, c_b = st.columns(2)
                        if c_a.button("📅", key=f"agd_blk_{aula}", help="Agendar"):
                             agendar_revisao_callback(u, aula, d.get('acertos_pos',0), tt_pos)
                             st.rerun()
                        if c_b.button("↺", key=f"rst_blk_{aula}", help="Reset"):
                             reset_callback(u, aula)
                             st.rerun()

    else:
        # VISÃO LISTA (Expanders Padrão)
        for bloco in df['Bloco'].unique():
            df_bloco = df[df['Bloco'] == bloco]
            feitas = sum(1 for a in df_bloco['Aula'] if estado.get(a, {}).get('feito'))
            
            with st.expander(f"{bloco} ({feitas}/{len(df_bloco)})", expanded=False):
                # Cabeçalho da tabela interna
                c_h1, c_h2, c_h3, c_h4, c_h5, c_h6 = st.columns([0.05, 0.15, 0.30, 0.15, 0.15, 0.20])
                c_h1.caption("✔")
                c_h2.caption("Prioridade")
                c_h3.caption("Tema")
                c_h4.caption("Pré-Aula")
                c_h5.caption("Pós-Aula")
                c_h6.caption("Ação")

                for _, row in df_bloco.iterrows():
                    aula = row['Aula']
                    prio = row['Prioridade']
                    d = estado.get(aula, {})
                    
                    # Metas Inteligentes
                    desempenho_ant = d.get('ultimo_desempenho')
                    meta_pre, meta_pos = calcular_meta_questoes(prio, desempenho_ant)
                    
                    # Layout
                    c1, c2, c3, c4, c5, c6 = st.columns([0.05, 0.15, 0.30, 0.15, 0.15, 0.20])
                    
                    # 1. Checkbox
                    c1.checkbox(" ", value=d.get('feito', False), key=f"chk_{aula}", on_change=update_row_callback, args=(u, aula, estado), label_visibility="collapsed")
                    
                    # 2. Prioridade e Metas Texto
                    with c2:
                        style = PRIORIDADES_STYLE.get(prio, PRIORIDADES_STYLE["Normal"])
                        st.markdown(f"<div style='background-color:{style['bg']};color:{style['color']};padding:2px;border-radius:4px;text-align:center;font-size:0.75em;font-weight:bold'>{style['icon']} {style['label']}</div>", unsafe_allow_html=True)
                        st.caption(f"Meta: {meta_pre} | {meta_pos}")
                    
                    # 3. Tema
                    with c3:
                        st.markdown(f"**{aula}**")
                        st.caption(f"{row['Area']}")
                    
                    # 4. Contador Pré-Aula
                    with c4:
                        ac_pre = d.get('acertos_pre', 0)
                        tt_pre = d.get('total_pre', 0)
                        
                        # Barra visual relativa à META
                        prog_pre = min(tt_pre / meta_pre, 1.0) if meta_pre > 0 else 0
                        
                        if tt_pre > 0:
                            st.progress(prog_pre, text=f"{ac_pre}/{tt_pre}")
                        else:
                            st.caption(f"0/{meta_pre}")

                    # 5. Contador Pós-Aula
                    with c5:
                        ac_pos = d.get('acertos_pos', 0)
                        tt_pos = d.get('total_pos', 0)
                        
                        prog_pos = min(tt_pos / meta_pos, 1.0) if meta_pos > 0 else 0
                        
                        if tt_pos > 0:
                            st.progress(prog_pos, text=f"{ac_pos}/{tt_pos}")
                        else:
                            st.caption(f"0/{meta_pos}")
                    
                    # 6. Desempenho Geral e Ação
                    with c6:
                        tt_geral = tt_pre + tt_pos
                        
                        if tt_geral > 0:
                            # Botões de Ação
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1:
                                # Botão Agendar Revisão
                                if st.button("📅", key=f"agd_{aula}", help="Agendar Revisão (Marca como Encerrado)"):
                                    agendar_revisao_callback(u, aula, ac_pre+ac_pos, tt_geral)
                                    st.rerun()
                            
                            with col_btn2:
                                # Botão Reset
                                if st.button("↺", key=f"rst_{aula}", help="Reiniciar ciclo"):
                                    reset_callback(u, aula)
                                    st.rerun()
                        else:
                            st.caption("—")

                    st.markdown("<hr style='margin:2px 0; border-top: 1px solid #f0f2f6;'>", unsafe_allow_html=True)