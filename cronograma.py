import streamlit as st
import pandas as pd
import re
import time
from database import (
    get_cronograma_status, 
    salvar_cronograma_status, 
    normalizar_area, 
    calcular_meta_questoes,
    resetar_revisoes_aula,
    registrar_estudo
)

# Configuração Visual das Prioridades
PRIORIDADES_STYLE = {
    "Diamante": {"icon": "💎", "color": "#9C27B0", "bg": "#F3E5F5", "label": "Diamante"},
    "Vermelho": {"icon": "🔴", "color": "#D32F2F", "bg": "#FFEBEE", "label": "Alta"},
    "Amarelo":  {"icon": "🟡", "color": "#FBC02D", "bg": "#FFFDE7", "label": "Média"},
    "Verde":    {"icon": "🟢", "color": "#388E3C", "bg": "#E8F5E9", "label": "Baixa"},
    "Normal":   {"icon": "⚪", "color": "#757575", "bg": "#F5F5F5", "label": "Normal"}
}

def update_row_callback(u, aula_nome, full_state):
    """Atualiza o checkbox de conclusão e salva."""
    check = st.session_state.get(f"chk_{aula_nome}", False)
    d_atual = full_state.get(aula_nome, {})
    d_atual["feito"] = check
    full_state[aula_nome] = d_atual
    salvar_cronograma_status(u, full_state)
    st.toast("Progresso salvo!", icon="✅")

def reset_callback(u, aula_nome):
    """Zera o ciclo de revisão."""
    if resetar_revisoes_aula(u, aula_nome):
        st.toast(f"Ciclo de '{aula_nome}' reiniciado!", icon="🔄")
        time.sleep(0.5)
        st.rerun()

def agendar_revisao_callback(u, aula_nome, acertos_total, total_total):
    """Marca como revisado e cria agendamento na agenda."""
    msg = registrar_estudo(u, aula_nome, acertos_total, total_total, tipo_estudo="Pos-Aula", srs=True)
    if "agendada" in msg or "Salvo" in msg or "salvo" in msg:
        st.toast(f"Revisão agendada para {aula_nome}!", icon="📅")
    else:
        st.error(f"Erro ao agendar: {msg}")

def ler_dados_nativos():
    """Lê o arquivo de aulas e extrai blocos e prioridades."""
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
    
    if not dados_mapa: st.warning("Sem dados de aulas."); return
    df = pd.DataFrame(dados_mapa)
    estado = get_cronograma_status(u)
    
    # --- CONTROLE DE ESTADO DA VISÃO ---
    if 'cronograma_view_mode' not in st.session_state:
        st.session_state.cronograma_view_mode = "Lista"
    if 'cronograma_group_by' not in st.session_state:
        st.session_state.cronograma_group_by = "Bloco" # Padrão: Por Bloco

    # --- HEADER E CONTROLES ---
    c_kpi, c_ctrl1, c_ctrl2 = st.columns([4, 1.5, 1.5])
    
    with c_kpi:
        concluidas = sum(1 for k, v in estado.items() if v.get('feito'))
        total_aulas = len(df)
        total_q = sum((v.get('total_pos', 0) or 0) + (v.get('total_pre', 0) or 0) for v in estado.values())
        
        prog_pct = min(concluidas / total_aulas, 1.0) if total_aulas > 0 else 0
        st.progress(prog_pct, text=f"Progresso: {concluidas}/{total_aulas} temas ({int(prog_pct*100)}%) | Questões: {total_q}")

    with c_ctrl1:
        # Botão para alternar entre Lista e Cards
        icon_view = "📅" if st.session_state.cronograma_view_mode == "Lista" else "📝"
        label_view = "Ver Cards" if st.session_state.cronograma_view_mode == "Lista" else "Ver Lista"
        if st.button(f"{icon_view} {label_view}", use_container_width=True):
            st.session_state.cronograma_view_mode = "Blocos" if st.session_state.cronograma_view_mode == "Lista" else "Lista"
            st.rerun()
            
    with c_ctrl2:
        # Botão para alternar agrupamento (Bloco vs Matéria)
        icon_grp = "📚" if st.session_state.cronograma_group_by == "Bloco" else "🗂️"
        label_grp = "Por Matéria" if st.session_state.cronograma_group_by == "Bloco" else "Por Bloco"
        if st.button(f"{icon_grp} {label_grp}", use_container_width=True, help="Alternar organização entre Blocos Cronológicos e Grandes Áreas"):
            st.session_state.cronograma_group_by = "Area" if st.session_state.cronograma_group_by == "Bloco" else "Bloco"
            st.rerun()
    
    st.divider()

    # Define a coluna de agrupamento baseado na escolha
    coluna_agrupamento = st.session_state.cronograma_group_by # 'Bloco' ou 'Area'
    grupos_unicos = sorted(df[coluna_agrupamento].unique())

    # --- RENDERIZAÇÃO ---

    if st.session_state.cronograma_view_mode == "Blocos":
        # === VISÃO DE CARDS ===
        grupo_sel = st.selectbox(f"Filtrar {coluna_agrupamento}:", ["Todos"] + list(grupos_unicos))
        
        df_view = df if grupo_sel == "Todos" else df[df[coluna_agrupamento] == grupo_sel]
        
        cols = st.columns(3)
        for idx, row in df_view.iterrows():
            aula = row['Aula']
            prio = row['Prioridade']
            d = estado.get(aula, {})
            
            with cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"**{aula}**")
                    
                    style = PRIORIDADES_STYLE.get(prio, PRIORIDADES_STYLE["Normal"])
                    st.markdown(
                        f"<div style='background-color:{style['bg']};color:{style['color']};padding:2px;border-radius:4px;text-align:center;font-size:0.75em;font-weight:bold;margin-bottom:5px'>"
                        f"{style['icon']} {style['label']}</div>", 
                        unsafe_allow_html=True
                    )
                    
                    c_chk, c_meta = st.columns([0.2, 0.8])
                    c_chk.checkbox("Feito", value=d.get('feito', False), key=f"cb_blk_{aula}", on_change=update_row_callback, args=(u, aula, estado), label_visibility="collapsed")
                    
                    meta_pre, meta_pos = calcular_meta_questoes(prio, d.get('ultimo_desempenho'))
                    c_meta.caption(f"Pré: {d.get('total_pre',0)}/{meta_pre} | Pós: {d.get('total_pos',0)}/{meta_pos}")
                    
                    c_agd, c_rst = st.columns(2)
                    tt_pos = d.get('total_pos', 0)
                    ac_pos = d.get('acertos_pos', 0)
                    
                    if c_agd.button("📅 Agendar", key=f"agd_blk_{aula}", help="Agendar Revisão", disabled=tt_pos==0):
                        agendar_revisao_callback(u, aula, ac_pos, tt_pos)
                        st.rerun()
                    
                    if c_rst.button("↺ Reset", key=f"rst_blk_{aula}"):
                        reset_callback(u, aula)

    else:
        # === VISÃO DE LISTA (EXPANDERS) ===
        for grupo in grupos_unicos:
            df_grupo = df[df[coluna_agrupamento] == grupo]
            feitas_grupo = sum(1 for a in df_grupo['Aula'] if estado.get(a, {}).get('feito'))
            
            # Título do Expander muda conforme o agrupamento
            titulo_expander = f"{grupo}"
            if coluna_agrupamento == 'Area':
                titulo_expander = f"🏥 {grupo.upper()}"
            
            with st.expander(f"{titulo_expander} ({feitas_grupo}/{len(df_grupo)})", expanded=False):
                # Cabeçalhos
                c_h1, c_h2, c_h3, c_h4, c_h5, c_h6 = st.columns([0.05, 0.15, 0.30, 0.15, 0.15, 0.20])
                c_h1.caption("✔")
                c_h2.caption("Prioridade")
                c_h3.caption("Aula")
                c_h4.caption("Pré-Aula")
                c_h5.caption("Pós-Aula")
                c_h6.caption("Ação")

                for _, row in df_grupo.iterrows():
                    aula = row['Aula']
                    prio = row['Prioridade']
                    d = estado.get(aula, {})
                    meta_pre, meta_pos = calcular_meta_questoes(prio, d.get('ultimo_desempenho'))
                    
                    c1, c2, c3, c4, c5, c6 = st.columns([0.05, 0.15, 0.30, 0.15, 0.15, 0.20])
                    
                    c1.checkbox(" ", value=d.get('feito', False), key=f"chk_{aula}", on_change=update_row_callback, args=(u, aula, estado), label_visibility="collapsed")
                    
                    with c2:
                        s = PRIORIDADES_STYLE.get(prio, PRIORIDADES_STYLE["Normal"])
                        st.markdown(f"<div style='background:{s['bg']};color:{s['color']};padding:2px;border-radius:4px;text")