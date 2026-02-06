import streamlit as st
import pandas as pd
import re
from database import (
    get_cronograma_status, 
    salvar_cronograma_status, 
    normalizar_area, 
    calcular_meta_questoes,
    resetar_revisoes_aula,
    registrar_estudo
)

# Estilo
PRIORIDADES_STYLE = {
    "Diamante": {"icon": "💎", "color": "#9C27B0", "bg": "#F3E5F5", "label": "Diamante"},
    "Vermelho": {"icon": "🔴", "color": "#D32F2F", "bg": "#FFEBEE", "label": "Alta"},
    "Amarelo":  {"icon": "🟡", "color": "#FBC02D", "bg": "#FFFDE7", "label": "Média"},
    "Verde":    {"icon": "🟢", "color": "#388E3C", "bg": "#E8F5E9", "label": "Baixa"},
    "Normal":   {"icon": "⚪", "color": "#757575", "bg": "#F5F5F5", "label": "Normal"}
}

def update_row_callback(u, aula_nome, full_state):
    check = st.session_state.get(f"chk_{aula_nome}", False)
    d = full_state.get(aula_nome, {})
    d["feito"] = check
    full_state[aula_nome] = d
    salvar_cronograma_status(u, full_state)
    st.toast("Salvo!", icon="✅")

def reset_callback(u, aula_nome):
    if resetar_revisoes_aula(u, aula_nome):
        st.toast(f"Ciclo de '{aula_nome}' reiniciado!", icon="🔄")

def agendar_revisao_callback(u, aula, ac_total, tt_total):
    # Agenda revisão chamando com srs=True
    msg = registrar_estudo(u, aula, ac_total, tt_total, tipo_estudo="Pos-Aula", srs=True)
    if "agendada" in msg or "Salvo" in msg:
        st.toast(f"Revisão Criada na Agenda!", icon="📅")
    else:
        st.error(msg)

def ler_dados_nativos():
    mapa = []
    try:
        import aulas_medcof; dados = getattr(aulas_medcof, 'DADOS_LIMPOS', [])
        with open('aulas_medcof.py', 'r', encoding='utf-8') as f: lines = f.readlines()
        
        idx, curr = 0, "Geral"
        for l in lines:
            m = re.search(r'#\s*-+\s*(BLOCO\s*.*)\s*-+', l, re.IGNORECASE)
            if m: curr = m.group(1).strip()
            
            if idx < len(dados):
                item = dados[idx]; nome = item[0]
                if nome in l:
                    area = item[1]
                    prio = item[2] if len(item)>2 else "Normal"
                    mapa.append({"Bloco": curr, "Aula": nome, "Area": area, "Prioridade": prio})
                    idx += 1
        return mapa
    except: return []

def render_cronograma(conn_ignored):
    st.header("🗂️ Cronograma & Metas")
    u = st.session_state.username
    dados = ler_dados_nativos()
    if not dados: st.warning("Sem dados."); return
    df = pd.DataFrame(dados)
    estado = get_cronograma_status(u)
    
    concluidas = sum(1 for k, v in estado.items() if v.get('feito'))
    total_q = sum((v.get('total_pos',0) + v.get('total_pre',0)) for v in estado.values())
    
    prog_pct = concluidas/len(df) if len(df) > 0 else 0
    st.progress(prog_pct, text=f"Progresso: {concluidas}/{len(df)} temas ({int(prog_pct*100)}%) | Questões: {total_q}")
    st.divider()

    for bloco in df['Bloco'].unique():
        df_b = df[df['Bloco']==bloco]
        feitas = sum(1 for a in df_b['Aula'] if estado.get(a, {}).get('feito'))
        
        with st.expander(f"{bloco} ({feitas}/{len(df_b)})", expanded=False):
            
            # Cabeçalho
            c1, c2, c3, c4, c5, c6 = st.columns([0.05, 0.15, 0.30, 0.15, 0.15, 0.20])
            c1.caption("✔"); c2.caption("Prioridade"); c3.caption("Aula"); c4.caption("Pré-Aula"); c5.caption("Pós-Aula"); c6.caption("Ação")

            for _, r in df_b.iterrows():
                aula = r['Aula']; prio = r['Prioridade']
                d = estado.get(aula, {})
                m_pre, m_pos = calcular_meta_questoes(prio, d.get('ultimo_desempenho'))
                
                c1, c2, c3, c4, c5, c6 = st.columns([0.05, 0.15, 0.30, 0.15, 0.15, 0.20])
                
                c1.checkbox(" ", value=d.get('feito', False), key=f"chk_{aula}", on_change=update_row_callback, args=(u, aula, estado), label_visibility="collapsed")
                
                with c2:
                    s = PRIORIDADES_STYLE.get(prio, PRIORIDADES_STYLE["Normal"])
                    st.markdown(f"<div style='background:{s['bg']};color:{s['color']};padding:2px;border-radius:4px;text-align:center;font-size:0.7em;font-weight:bold'>{s['icon']} {s['label']}</div>", unsafe_allow_html=True)
                    st.caption(f"Meta: {m_pre}|{m_pos}")
                
                with c3: st.markdown(f"**{aula}**"); st.caption(f"{r['Area']}")
                
                acp, ttp = d.get('acertos_pre', 0), d.get('total_pre', 0)
                with c4: st.progress(min(ttp/m_pre, 1.0) if m_pre>0 else 0, text=f"{acp}/{ttp}")
                
                acps, ttps = d.get('acertos_pos', 0), d.get('total_pos', 0)
                with c5: st.progress(min(ttps/m_pos, 1.0) if m_pos>0 else 0, text=f"{acps}/{ttps}")
                
                with c6:
                    tt_geral = ttp + ttps
                    if tt_geral > 0:
                        c_act1, c_act2 = st.columns(2)
                        # Botão Agendar
                        if c_act1.button("📅", key=f"agd_{aula}", help="Agendar Revisão (Cria na Agenda)"):
                            agendar_revisao_callback(u, aula, acp+acps, tt_geral)
                            st.rerun()
                        # Botão Reset
                        if c_act2.button("↺", key=f"rst_{aula}", help="Reiniciar"):
                            reset_callback(u, aula)
                            st.rerun()
                    else:
                        st.caption("—")
                st.markdown("<hr style='margin:2px 0; border-top: 1px solid #f0f2f6;'>", unsafe_allow_html=True)