import streamlit as st
import pandas as pd
import re
import os
from database import get_cronograma_status, salvar_cronograma_status, normalizar_area

# Prioridades do HTML (Cores -> Nomes)
MAPA_PRIORIDADES = {
    "red": "Vermelho",      # Alta Prioridade / Atrasado
    "orange": "Laranja",    # Atenção
    "yellow": "Amarelo",    # Médio
    "green": "Verde",       # Ok / Fácil
    "blue": "Azul",         # Complementar
    "purple": "Diamante",   # Muito Importante (Ex: Reta Final)
    "gray": "Cinza"         # Opcional
}

PRIORIDADES_VISUAIS = {
    "Diamante": "💎 Diamante",
    "Vermelho": "🔴 Vermelho",
    "Laranja": "🟠 Laranja",
    "Amarelo": "🟡 Amarelo",
    "Verde": "🟢 Verde",
    "Azul": "🔵 Azul",
    "Normal": "⚪ Normal"
}

def importar_prioridades_html():
    """
    Lê o ficheiro HTML enviado e extrai: {Nome da Aula: Prioridade}
    """
    mapa_prioridades = {}
    try:
        # Tenta encontrar o arquivo HTML no diretório
        arquivos = [f for f in os.listdir('.') if f.endswith('.html') and 'MEDCOF' in f]
        if not arquivos:
            return {}
            
        with open(arquivos[0], 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Regex para extrair linhas da tabela do Notion/HTML exportado
        # Procura: cor da prioridade ... título da aula
        # Ex: <span class="...color-red">Vermelho</span> ... <a ...>Aula X</a>
        
        # Padrão 1: Cor e depois Título
        padrao = re.compile(r'select-value-color-(\w+)">([^<]+)</span>.*?<td class="cell-title"><a href="[^"]+">([^<]+)</a>', re.DOTALL)
        matches = padrao.findall(content)
        
        for cor_ingles, nome_cor, titulo_aula in matches:
            # Limpeza do título
            titulo_limpo = titulo_aula.strip()
            # Mapeia cor inglês/português para nossa lista interna
            prio = MAPA_PRIORIDADES.get(cor_ingles, "Normal")
            
            # Ajuste fino: Se o texto for "Diamante", usa Diamante independente da cor
            if "Diamante" in nome_cor: prio = "Diamante"
            
            mapa_prioridades[titulo_limpo] = prio
            
    except Exception as e:
        print(f"Erro ao importar HTML: {e}")
        
    return mapa_prioridades

def update_row_callback(u, aula_nome, full_state):
    check = st.session_state.get(f"chk_{aula_nome}", False)
    # Tenta pegar a prioridade do selectbox, senão mantém a atual
    prio = st.session_state.get(f"prio_{aula_nome}", full_state.get(aula_nome, {}).get("prioridade", "Normal"))
    
    # Acertos e Total vêm da sessão ou do estado anterior (se não mudou)
    # Nota: Como a sidebar atualiza o banco, precisamos garantir que não estamos sobrescrevendo com zero
    # Se o widget numérico não estiver na tela (ex: fechado), usamos o valor do banco
    ac = st.session_state.get(f"ac_{aula_nome}", full_state.get(aula_nome, {}).get("acertos", 0))
    tt = st.session_state.get(f"tt_{aula_nome}", full_state.get(aula_nome, {}).get("total", 0))
    
    full_state[aula_nome] = {
        "feito": check,
        "prioridade": prio,
        "acertos": ac,
        "total": tt
    }
    salvar_cronograma_status(u, full_state)
    st.toast("Atualizado!", icon="✅")

def ler_blocos_e_prioridades():
    # 1. Carrega estrutura do arquivo Python
    try:
        import aulas_medcof; dados = getattr(aulas_medcof, 'DADOS_LIMPOS', [])
        with open('aulas_medcof.py', 'r', encoding='utf-8') as f: lines = f.readlines()
    except: return [], {}, []

    # 2. Carrega prioridades do HTML (Importação Única)
    prio_html = importar_prioridades_html()
    
    mapa, idx, curr = [], 0, "Geral"
    for l in lines:
        m = re.search(r'#\s*-+\s*(BLOCO\s*.*)\s*-+', l)
        if m: curr = m.group(1).strip()
        if idx < len(dados):
            item = dados[idx]
            aula = item[0] if isinstance(item, tuple) else item
            area = item[1] if isinstance(item, tuple) and len(item)>1 else "Geral"
            
            if aula in l:
                # Tenta casar o nome da aula com o do HTML (pode precisar de fuzzy match)
                # Aqui usamos match exato ou "contém"
                prio_detectada = "Normal"
                
                # Procura no dicionário do HTML
                for k, v in prio_html.items():
                    if k in aula or aula in k: # Match flexível
                        prio_detectada = v
                        break
                
                mapa.append({
                    "Bloco": curr, 
                    "Aula": aula, 
                    "Area": normalizar_area(area),
                    "Prioridade_HTML": prio_detectada
                })
                idx += 1
    return mapa, dados, prio_html

def render_cronograma(conn_ignored):
    st.header("🗂️ Cronograma & Prioridades")
    
    import os
    if os.path.exists("MEDCOF 2026 2fd60e4aba71806496a9d52180699c35.html"):
        st.success("Arquivo de prioridades (HTML) detetado e sincronizado.", icon="🔗")
    
    u = st.session_state.username
    mapa, bruto, prios_externas = ler_blocos_e_prioridades()
    
    if not mapa: st.warning("Sem dados."); return
    df = pd.DataFrame(mapa)
    
    # Carrega estado do banco
    estado = get_cronograma_status(u)
    
    # Sync Inicial: Se o HTML tem prioridade e o Banco ainda é 'Normal', atualiza o banco
    mudou_algo = False
    for row in mapa:
        aula = row['Aula']
        p_html = row['Prioridade_HTML']
        
        # Dados atuais no banco
        d_banco = estado.get(aula, {"feito": False, "prioridade": "Normal", "acertos": 0, "total": 0})
        
        # Se a prioridade no banco for Normal, mas o HTML diz outra coisa, atualizamos
        if d_banco.get("prioridade") == "Normal" and p_html != "Normal":
            d_banco["prioridade"] = p_html
            estado[aula] = d_banco
            mudou_algo = True
            
    if mudou_algo:
        salvar_cronograma_status(u, estado)
        # st.rerun() # Opcional: Recarregar para mostrar já atualizado

    # KPIs
    concluidas = sum(1 for k, v in estado.items() if v.get('feito'))
    total_q = sum(v.get('total', 0) for v in estado.values())
    st.progress(concluidas/len(df), text=f"Progresso Temas: {concluidas}/{len(df)}")
    st.caption(f"Questões Totais no Cronograma: **{total_q}**")
    
    st.divider()

    blocos = df['Bloco'].unique()
    for bl in blocos:
        aulas = df[df['Bloco']==bl]
        feitas = sum(1 for a in aulas['Aula'] if estado.get(a, {}).get('feito'))
        
        with st.expander(f"{bl} ({feitas}/{len(aulas)})"):
            for _, r in aulas.iterrows():
                aula = r['Aula']
                d = estado.get(aula, {"feito": False, "prioridade": "Normal", "acertos": 0, "total": 0})
                
                c1, c2, c3 = st.columns([0.1, 0.6, 0.3])
                
                # 1. Check + Nome
                c1.checkbox(" ", value=d.get('feito', False), key=f"chk_{aula}", on_change=update_row_callback, args=(u, aula, estado), label_visibility="collapsed")
                
                # 2. Detalhes (Nome, Area, Prioridade)
                with c2:
                    prio_key = d.get('prioridade', 'Normal')
                    emoji_prio = PRIORIDADES_VISUAIS.get(prio_key, "⚪")[0] # Pega só o emoji
                    
                    st.markdown(f"**{aula}**")
                    st.caption(f"{emoji_prio} {prio_key} • {r['Area']}")

                # 3. Questões (Visualização)
                with c3:
                    ac = d.get('acertos', 0)
                    tot = d.get('total', 0)
                    perc = int(ac/tot*100) if tot > 0 else 0
                    
                    st.progress(perc/100, text=f"{ac}/{tot} ({perc}%)")