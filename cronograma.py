import streamlit as st
import pandas as pd
import re
import unicodedata
import difflib
from database import get_cronograma_status, salvar_cronograma_status, normalizar_area

# --- CONFIGURAÇÃO DE PRIORIDADES (ESCALA CORRETA) ---
# Ordem: Vermelho (Base) -> Amarelo -> Verde -> Diamante (Topo)
MAPA_PRIORIDADES = {
    "red": "Vermelho",      # Alta Prioridade
    "yellow": "Amarelo",    # Médio
    "green": "Verde",       # Baixa Prioridade / Fácil
    "purple": "Diamante",   # Muito Importante
    # Mapeamentos de fallback
    "orange": "Vermelho",
    "blue": "Verde",
    "gray": "Verde"         # Cinza assume Verde (menos urgente)
}

PRIORIDADES_VISUAIS = {
    "Diamante": "💎 Diamante",
    "Vermelho": "🔴 Vermelho",
    "Amarelo": "🟡 Amarelo",
    "Verde": "🟢 Verde"
}

def normalizar_texto_match(texto):
    """
    Normalização agressiva para comparação.
    Ex: "Anemias Hipoproliferativas I" -> "anemiashipoproliferativasi"
    """
    if not isinstance(texto, str): return ""
    nfkd = unicodedata.normalize('NFKD', texto)
    sem_acento = u"".join([c for c in nfkd if not unicodedata.combining(c)])
    # Mantém apenas letras e números
    return re.sub(r'[^a-z0-9]', '', sem_acento.lower())

def importar_prioridades_html():
    """
    Lê o HTML e cria um dicionário {NomeAula: Prioridade} usando heurísticas avançadas.
    """
    mapa_prioridades = {}
    lista_nomes_html = [] # Para fuzzy matching
    
    try:
        import os
        arquivos = [f for f in os.listdir('.') if f.endswith('.html') and 'MEDCOF' in f]
        if not arquivos: return {}
            
        with open(arquivos[0], 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Regex para capturar (Cor, TextoCor, TituloAula)
        padrao = re.compile(r'select-value-color-(\w+)">([^<]+)</span>.*?<td class="cell-title"><a href="[^"]+">([^<]+)</a>', re.DOTALL)
        matches = padrao.findall(content)
        
        # 1. Primeira Passada: Match Exato e Construção de Base
        temp_map = {}
        for cor_ing, txt_cor, titulo in matches:
            titulo_limpo = titulo.strip()
            
            # Prioridade
            prio = "Verde" # Default seguro
            if "Diamante" in txt_cor or "purple" in cor_ing: prio = "Diamante"
            else: prio = MAPA_PRIORIDADES.get(cor_ing, "Verde")
            
            temp_map[normalizar_texto_match(titulo_limpo)] = prio
            
            # Guarda tupla (Texto Original, Texto Normalizado, Prioridade) para fuzzy match depois
            lista_nomes_html.append({
                "original": titulo_limpo,
                "norm": normalizar_texto_match(titulo_limpo),
                "prio": prio
            })
            
        return temp_map, lista_nomes_html
                
    except Exception as e:
        print(f"Erro HTML: {e}")
        return {}, []

def encontrar_prioridade_fuzzy(aula_alvo, lista_html):
    """
    Usa difflib para encontrar a melhor correspondência aproximada.
    """
    alvo_norm = normalizar_texto_match(aula_alvo)
    
    # 1. Tenta encontrar a string mais parecida na lista de normalizados
    candidatos = [item['norm'] for item in lista_html]
    matches = difflib.get_close_matches(alvo_norm, candidatos, n=1, cutoff=0.7) # 70% similaridade mínima
    
    if matches:
        match_norm = matches[0]
        # Recupera a prioridade associada
        for item in lista_html:
            if item['norm'] == match_norm:
                return item['prio']
    
    # 2. Se falhar, tenta match parcial (substring)
    for item in lista_html:
        if alvo_norm in item['norm'] or item['norm'] in alvo_norm:
            return item['prio']
            
    return "Verde" # Fallback final (assumimos Verde se não achar, para não ficar sem cor)

def update_row_callback(u, aula_nome, full_state):
    check = st.session_state.get(f"chk_{aula_nome}", False)
    prio = st.session_state.get(f"prio_{aula_nome}", full_state.get(aula_nome, {}).get("prioridade", "Verde"))
    ac = st.session_state.get(f"ac_{aula_nome}", full_state.get(aula_nome, {}).get("acertos", 0))
    tt = st.session_state.get(f"tt_{aula_nome}", full_state.get(aula_nome, {}).get("total", 0))
    
    full_state[aula_nome] = {"feito": check, "prioridade": prio, "acertos": ac, "total": tt}
    salvar_cronograma_status(u, full_state)
    st.toast("Salvo!", icon="✅")

def ler_blocos_e_prioridades():
    try:
        import aulas_medcof; dados = getattr(aulas_medcof, 'DADOS_LIMPOS', [])
        with open('aulas_medcof.py', 'r', encoding='utf-8') as f: lines = f.readlines()
    except: return [], {}, {}, []

    map_exato, lista_html = importar_prioridades_html()
    
    mapa, idx, curr = [], 0, "Geral"
    for l in lines:
        m = re.search(r'#\s*-+\s*(BLOCO\s*.*)\s*-+', l)
        if m: curr = m.group(1).strip()
        if idx < len(dados):
            item = dados[idx]
            aula = item[0] if isinstance(item, tuple) else item
            area = item[1] if isinstance(item, tuple) and len(item)>1 else "Geral"
            
            if aula in l:
                # 1. Tenta Match Exato
                chave = normalizar_texto_match(aula)
                prio = map_exato.get(chave)
                
                # 2. Se falhar, usa Fuzzy Match
                if not prio:
                    prio = encontrar_prioridade_fuzzy(aula, lista_html)
                
                mapa.append({
                    "Bloco": curr, 
                    "Aula": aula, 
                    "Area": normalizar_area(area),
                    "Prioridade_HTML": prio
                })
                idx += 1
    return mapa, dados, map_exato

def render_cronograma(conn_ignored):
    st.header("🗂️ Cronograma & Prioridades")
    
    u = st.session_state.username
    mapa, bruto, _ = ler_blocos_e_prioridades()
    
    if not mapa: st.warning("Sem dados."); return
    df = pd.DataFrame(mapa)
    estado = get_cronograma_status(u)
    
    # Sync Inicial (Prioridade)
    mudou = False
    for row in mapa:
        aula, p_html = row['Aula'], row['Prioridade_HTML']
        d = estado.get(aula, {"feito": False, "prioridade": "Verde", "acertos": 0, "total": 0})
        
        # Se no banco estiver "Normal" (legado) ou vazio, atualiza com HTML
        if d.get("prioridade") in ["Normal", None]:
            d["prioridade"] = p_html
            estado[aula] = d
            mudou = True
    if mudou: salvar_cronograma_status(u, estado)

    # KPIs
    concluidas = sum(1 for k, v in estado.items() if v.get('feito'))
    total_q = sum(v.get('total', 0) for v in estado.values())
    st.progress(concluidas/len(df), text=f"Progresso: {concluidas}/{len(df)} Temas | Questões: {total_q}")
    st.divider()

    blocos = df['Bloco'].unique()
    for bl in blocos:
        aulas = df[df['Bloco']==bl]
        feitas = sum(1 for a in aulas['Aula'] if estado.get(a, {}).get('feito'))
        
        with st.expander(f"{bl} ({feitas}/{len(aulas)})", expanded=False):
            for _, r in aulas.iterrows():
                aula = r['Aula']
                d = estado.get(aula, {"feito": False, "prioridade": "Verde", "acertos": 0, "total": 0})
                
                c1, c2, c3 = st.columns([0.1, 0.6, 0.3])
                c1.checkbox(" ", value=d.get('feito', False), key=f"chk_{aula}", on_change=update_row_callback, args=(u, aula, estado), label_visibility="collapsed")
                
                with c2:
                    prio = d.get('prioridade', 'Verde')
                    # Garante que Normal não apareça, fallback para Verde
                    if prio == "Normal": prio = "Verde"
                    
                    emoji = PRIORIDADES_VISUAIS.get(prio, "🟢")[0]
                    cor = "green"
                    if prio == "Diamante": cor = "purple"
                    elif prio == "Vermelho": cor = "red"
                    elif prio == "Amarelo": cor = "#DAA520"
                    
                    st.markdown(f"**{aula}**")
                    st.markdown(f"<span style='color:{cor}; font-weight:bold'>{emoji} {prio}</span> • <small>{r['Area']}</small>", unsafe_allow_html=True)

                with c3:
                    ac, tot = d.get('acertos', 0), d.get('total', 0)
                    perc = int(ac/tot*100) if tot > 0 else 0
                    st.progress(perc/100, text=f"{ac}/{tot}")