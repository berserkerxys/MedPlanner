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
    # Recupera estado atual ou cria novo se não existir
    d_atual = full_state.get(aula_nome, {})
    d_atual["feito"] = check
    full_state[aula_nome] = d_atual
    
    salvar_cronograma_status(u, full_state)
    st.toast("Progresso salvo!", icon="✅")

def reset_callback(u, aula_nome):
    """Zera o ciclo de revisão."""
    if resetar_revisoes_aula(u, aula_nome):
        st.toast(f"Ciclo de '{aula_nome}' reiniciado!", icon="🔄")
        # Opcional: st.rerun() se precisar de refresh imediato

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
                    # Tenta pegar prioridade se existir na tupla (Nome, Area, Prioridade)
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
    
    # Controle de Visão (Estado da Sessão)
    if 'cronograma_view_mode' not in st.session_state:
        st.session_state.cronograma_view_mode = "Lista"

    # Header com Controles e KPIs
    c_kpi, c_ctrl = st.columns([3, 1])
    
    with c_kpi:
        concluidas = sum(1 for k, v in estado.items() if v.get('feito'))
        total_aulas = len(df)
        total_q = sum((v.get('total_pos', 0) or 0) + (v.get('total_pre', 0) or 0) for v in estado.values())
        
        prog_pct = min(concluidas / total_aulas, 1.0) if total_aulas > 0 else 0
        st.progress(prog_pct, text=f"Progresso: {concluidas}/{total_aulas} temas ({int(prog_pct*100)}%) | Questões: {total_q}")

    with c_ctrl:
        # Botão de Alternância
        btn_label = "📅 Ver Blocos" if st.session_state.cronograma_view_mode == "Lista" else "📝 Ver Lista"
        if st.button(btn_label, use_container_width=True):
            st.session_state.cronograma_view_mode = "Blocos" if st.session_state.cronograma_view_mode == "Lista" else "Lista"
            st.rerun()
    
    st.divider()

    # --- RENDERIZAÇÃO CONDICIONAL ---

    if st.session_state.cronograma_view_mode == "Blocos":
        # === VISÃO DE BLOCOS (CARDS) ===
        blocos = df['Bloco'].unique()
        bloco_sel = st.selectbox("Filtrar Bloco:", ["Todos"] + list(blocos))
        
        df_view = df if bloco_sel == "Todos" else df[df['Bloco'] == bloco_sel]
        
        # Grid de cards (3 colunas)
        cols = st.columns(3)
        for idx, row in df_view.iterrows():
            aula = row['Aula']
            prio = row['Prioridade']
            d = estado.get(aula, {})
            
            with cols[idx % 3]:
                with st.container(border=True):
                    # Cabeçalho do Card
                    st.markdown(f"**{aula}**")
                    
                    # Badge Visual
                    style = PRIORIDADES_STYLE.get(prio, PRIORIDADES_STYLE["Normal"])
                    st.markdown(
                        f"<div style='background-color:{style['bg']};color:{style['color']};padding:2px;border-radius:4px;text-align:center;font-size:0.75em;font-weight:bold;margin-bottom:5px'>"
                        f"{style['icon']} {style['label']}</div>", 
                        unsafe_allow_html=True
                    )
                    
                    # Checkbox
                    c_chk, c_meta = st.columns([0.2, 0.8])
                    c_chk.checkbox("Feito", value=d.get('feito', False), key=f"cb_blk_{aula}", on_change=update_row_callback, args=(u, aula, estado), label_visibility="collapsed")
                    
                    # Metas e Progresso (Barra de Progresso por Assunto no Card)
                    meta_pre, meta_pos = calcular_meta_questoes(prio, d.get('ultimo_desempenho'))
                    
                    tt_pre = d.get('total_pre', 0)
                    tt_pos = d.get('total_pos', 0)
                    
                    # Barra Combinada (Pré + Pós / Metas)
                    total_atual = tt_pre + tt_pos
                    total_meta = meta_pre + meta_pos
                    prog_assunto = min(total_atual / total_meta, 1.0) if total_meta > 0 else 0
                    
                    st.progress(prog_assunto, text=f"{int(prog_assunto*100)}% ({total_atual}/{total_meta}q)")
                    
                    st.caption(f"Pré: {tt_pre}/{meta_pre} | Pós: {tt_pos}/{meta_pos}")
                    
                    # Ações Rápidas
                    c_agd, c_rst = st.columns(2)
                    ac_pos = d.get('acertos_pos', 0)
                    
                    if c_agd.button("📅 Agendar", key=f"agd_blk_{aula}", help="Agendar Revisão", disabled=tt_pos==0):
                        agendar_revisao_callback(u, aula, ac_pos, tt_pos)
                        st.rerun()
                    
                    if c_rst.button("↺ Reset", key=f"rst_blk_{aula}"):
                        reset_callback(u, aula)
                        st.rerun()

    else:
        # === VISÃO DE LISTA (DETALHADA) ===
        for bloco in df['Bloco'].unique():
            df_bloco = df[df['Bloco'] == bloco]
            feitas = sum(1 for a in df_bloco['Aula'] if estado.get(a, {}).get('feito'))
            
            with st.expander(f"{bloco} ({feitas}/{len(df_bloco)})", expanded=False):
                # Cabeçalhos da Tabela
                c_h1, c_h2, c_h3, c_h4, c_h5, c_h6 = st.columns([0.05, 0.15, 0.30, 0.15, 0.15, 0.20])
                c_h1.caption("✔")
                c_h2.caption("Prioridade")
                c_h3.caption("Aula")
                c_h4.caption("Pré-Aula")
                c_h5.caption("Pós-Aula")
                c_h6.caption("Ação")

                for _, row in df_bloco.iterrows():
                    aula = row['Aula']
                    prio = row['Prioridade']
                    d = estado.get(aula, {})
                    
                    meta_pre, meta_pos = calcular_meta_questoes(prio, d.get('ultimo_desempenho'))
                    
                    # Linha de Dados
                    c1, c2, c3, c4, c5, c6 = st.columns([0.05, 0.15, 0.30, 0.15, 0.15, 0.20])
                    
                    # 1. Checkbox
                    c1.checkbox(" ", value=d.get('feito', False), key=f"chk_{aula}", on_change=update_row_callback, args=(u, aula, estado), label_visibility="collapsed")
                    
                    # 2. Prioridade
                    with c2:
                        s = PRIORIDADES_STYLE.get(prio, PRIORIDADES_STYLE["Normal"])
                        st.markdown(f"<div style='background:{s['bg']};color:{s['color']};padding:2px;border-radius:4px;text-align:center;font-size:0.7em;font-weight:bold'>{s['icon']} {s['label']}</div>", unsafe_allow_html=True)
                        st.caption(f"Metas: {meta_pre}|{meta_pos}")
                    
                    # 3. Tema
                    with c3:
                        st.markdown(f"**{aula}**")
                        st.caption(f"{row['Area']}")
                        # Barra de Progresso por Assunto (Visualização na Lista)
                        tt_total = d.get('total_pre', 0) + d.get('total_pos', 0)
                        meta_total = meta_pre + meta_pos
                        prog_subj = min(tt_total / meta_total, 1.0) if meta_total > 0 else 0
                        st.progress(prog_subj)
                    
                    # 4. Progresso Pré
                    acp, ttp = d.get('acertos_pre', 0), d.get('total_pre', 0)
                    with c4: st.progress(min(ttp/meta_pre, 1.0) if meta_pre>0 else 0, text=f"{acp}/{ttp}")
                    
                    # 5. Progresso Pós
                    acps, ttps = d.get('acertos_pos', 0), d.get('total_pos', 0)
                    with c5: st.progress(min(ttps/meta_pos, 1.0) if meta_pos>0 else 0, text=f"{acps}/{ttps}")
                    
                    # 6. Ações
                    with c6:
                        tt_geral = ttp + ttps
                        if tt_geral > 0:
                            ca, cb = st.columns(2)
                            if ca.button("📅", key=f"agd_{aula}", help="Agendar Revisão"):
                                agendar_revisao_callback(u, aula, acp+acps, tt_geral)
                                st.rerun()
                            if cb.button("↺", key=f"rst_{aula}", help="Reiniciar"):
                                reset_callback(u, aula)
                                st.rerun()
                        else:
                            st.caption("—")
                    
                    st.markdown("<hr style='margin:2px 0; border-top: 1px solid #f0f2f6;'>", unsafe_allow_html=True)