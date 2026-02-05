import streamlit as st
import pandas as pd
import re
from database import get_cronograma_status, salvar_cronograma_status, normalizar_area

# Opções de Prioridade
PRIORIDADES = ["Normal", "Diamante", "Ouro", "Prata", "Verde", "Vermelho"]

def update_row_callback(u, aula_nome, full_state):
    """
    Callback executado ao alterar qualquer widget de uma linha.
    Atualiza o estado global e salva no banco.
    """
    # Recupera valores atuais dos widgets daquela linha
    check = st.session_state.get(f"chk_{aula_nome}", False)
    prio = st.session_state.get(f"prio_{aula_nome}", "Normal")
    ac = st.session_state.get(f"ac_{aula_nome}", 0)
    tt = st.session_state.get(f"tt_{aula_nome}", 0)
    
    # Atualiza o dicionário mestre
    full_state[aula_nome] = {
        "feito": check,
        "prioridade": prio,
        "acertos": ac,
        "total": tt
    }
    
    # Salva no banco
    salvar_cronograma_status(u, full_state)
    st.toast("Progresso salvo!", icon="✅")

def ler_blocos():
    try:
        import aulas_medcof; dados = getattr(aulas_medcof, 'DADOS_LIMPOS', [])
        with open('aulas_medcof.py', 'r', encoding='utf-8') as f: lines = f.readlines()
        mapa, idx, curr = [], 0, "Geral"
        for l in lines:
            m = re.search(r'#\s*-+\s*(BLOCO\s*.*)\s*-+', l)
            if m: curr = m.group(1).strip()
            if idx < len(dados):
                aula, area = dados[idx]
                if aula in l:
                    mapa.append({"Bloco": curr, "Aula": aula, "Area": normalizar_area(area)})
                    idx += 1
        return mapa
    except: return []

def render_cronograma(conn_ignored):
    st.header("🗂️ Cronograma Extensivo")
    st.caption("Gerencie seu progresso detalhado: Prioridade, Questões e Conclusão.")
    
    u = st.session_state.username
    
    # 1. Carregar Estrutura
    mapa = ler_blocos()
    if not mapa: st.warning("Dados não carregados."); return
    df = pd.DataFrame(mapa)
    
    # 2. Carregar Estado do Usuário (Rich Data)
    # Formato: {'Aula': {'feito': T, 'prioridade': 'X', 'acertos': 10, 'total': 20}}
    estado_salvo = get_cronograma_status(u)
    
    # Barra de Progresso Global (Baseada em Checkbox 'Feito')
    total_aulas = len(df)
    concluidas = sum(1 for k, v in estado_salvo.items() if v.get('feito'))
    prog_global = concluidas / total_aulas if total_aulas > 0 else 0
    st.progress(prog_global, text=f"Progresso Geral: {concluidas}/{total_aulas} ({prog_global:.1%})")
    
    st.divider()

    # 3. Renderização por Blocos
    blocos = df['Bloco'].unique()
    
    for bloco in blocos:
        aulas_bloco = df[df['Bloco'] == bloco]
        
        # Header do Bloco com Contagem
        feitas_bloco = sum(1 for a in aulas_bloco['Aula'] if estado_salvo.get(a, {}).get('feito'))
        
        with st.expander(f"📚 {bloco} ({feitas_bloco}/{len(aulas_bloco)})", expanded=False):
            # Cabeçalho da "Tabela"
            c_h1, c_h2, c_h3, c_h4 = st.columns([0.5, 2, 1.5, 1])
            c_h1.caption("✔")
            c_h2.caption("Aula & Prioridade")
            c_h3.caption("Questões (Ac/Tot)")
            c_h4.caption("%")
            
            for _, row in aulas_bloco.iterrows():
                aula = row['Aula']
                dados_aula = estado_salvo.get(aula, {"feito": False, "prioridade": "Normal", "acertos": 0, "total": 0})
                
                # Layout da Linha
                c1, c2, c3, c4 = st.columns([0.5, 2, 1.5, 1])
                
                # Coluna 1: Checkbox (Feito)
                c1.checkbox(
                    " ", # Label vazio para alinhar
                    value=dados_aula.get('feito', False),
                    key=f"chk_{aula}",
                    on_change=update_row_callback,
                    args=(u, aula, estado_salvo),
                    label_visibility="collapsed"
                )
                
                # Coluna 2: Nome + Prioridade
                with c2:
                    st.markdown(f"**{aula}**")
                    # Badge de cor para prioridade
                    prio_atual = dados_aula.get('prioridade', 'Normal')
                    idx_prio = PRIORIDADES.index(prio_atual) if prio_atual in PRIORIDADES else 0
                    
                    st.selectbox(
                        "Prioridade", 
                        PRIORIDADES, 
                        index=idx_prio,
                        key=f"prio_{aula}",
                        on_change=update_row_callback,
                        args=(u, aula, estado_salvo),
                        label_visibility="collapsed"
                    )

                # Coluna 3: Questões (Lado a Lado)
                with c3:
                    ca, ct = st.columns(2)
                    ca.number_input("Ac", 0, 999, dados_aula.get('acertos', 0), key=f"ac_{aula}", on_change=update_row_callback, args=(u, aula, estado_salvo), label_visibility="collapsed")
                    ct.number_input("Tot", 0, 999, dados_aula.get('total', 0), key=f"tt_{aula}", on_change=update_row_callback, args=(u, aula, estado_salvo), label_visibility="collapsed")

                # Coluna 4: Percentual Visual
                with c4:
                    ac = dados_aula.get('acertos', 0)
                    tt = dados_aula.get('total', 0)
                    perc = ac / tt if tt > 0 else 0
                    st.progress(perc)
                    st.caption(f"{int(perc*100)}%")
                
                st.markdown("---")