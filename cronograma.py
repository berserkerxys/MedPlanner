import streamlit as st
import pandas as pd
import re
from database import (
    get_cronograma_status, 
    salvar_cronograma_status, 
    normalizar_area, 
    calcular_meta_questoes,
    resetar_revisoes_aula
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
    st.caption("Acompanhe o cumprimento das metas de Pré e Pós aula.")
    
    u = st.session_state.username
    dados_mapa = ler_dados_nativos()
    
    if not dados_mapa: st.warning("Sem dados."); return
    df = pd.DataFrame(dados_mapa)
    estado = get_cronograma_status(u)
    
    # KPIs
    concluidas = sum(1 for k, v in estado.items() if v.get('feito'))
    total_q = sum(v.get('total_pos', 0) + v.get('total_pre', 0) for v in estado.values())
    st.progress(concluidas/len(df), text=f"Progresso: {concluidas}/{len(df)} temas | Questões Totais: {total_q}")
    st.divider()

    for bloco in df['Bloco'].unique():
        df_bloco = df[df['Bloco'] == bloco]
        feitas = sum(1 for a in df_bloco['Aula'] if estado.get(a, {}).get('feito'))
        
        with st.expander(f"{bloco} ({feitas}/{len(df_bloco)})", expanded=False):
            # Cabeçalho da tabela interna
            c_h1, c_h2, c_h3, c_h4, c_h5 = st.columns([0.05, 0.2, 0.35, 0.2, 0.2])
            c_h1.caption("✔")
            c_h2.caption("Prioridade")
            c_h3.caption("Tema")
            c_h4.caption("Pré-Aula")
            c_h5.caption("Pós-Aula")

            for _, row in df_bloco.iterrows():
                aula = row['Aula']
                prio = row['Prioridade']
                d = estado.get(aula, {})
                
                # Metas Inteligentes
                desempenho_ant = d.get('ultimo_desempenho')
                meta_pre, meta_pos = calcular_meta_questoes(prio, desempenho_ant)
                
                # Layout
                c1, c2, c3, c4, c5 = st.columns([0.05, 0.2, 0.35, 0.2, 0.2])
                
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
                    cor_barra = "green" if tt_pre >= meta_pre else "blue"
                    
                    if tt_pre > 0:
                        st.progress(prog_pre, text=f"{ac_pre}/{tt_pre} (Meta {meta_pre})")
                    else:
                        st.caption(f"0/{meta_pre}")

                # 5. Contador Pós-Aula + Reset
                with c5:
                    ac_pos = d.get('acertos_pos', 0)
                    tt_pos = d.get('total_pos', 0)
                    
                    prog_pos = min(tt_pos / meta_pos, 1.0) if meta_pos > 0 else 0
                    
                    if tt_pos > 0:
                        st.progress(prog_pos, text=f"{ac_pos}/{tt_pos} (Meta {meta_pos})")
                    else:
                        st.caption(f"0/{meta_pos}")
                    
                    # Botão Reset discreto
                    if tt_pos > 0 or d.get('feito', False):
                        if st.button("↺", key=f"rst_{aula}", help="Reiniciar ciclo de revisões"):
                            reset_callback(u, aula)
                            st.rerun()

                st.markdown("<hr style='margin:2px 0; border-top: 1px solid #f0f2f6;'>", unsafe_allow_html=True)