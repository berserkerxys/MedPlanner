import streamlit as st
import pandas as pd
import re
import os
import unicodedata
from database import get_cronograma_status, salvar_cronograma_status, normalizar_area

# --- CONFIGURAÇÃO DE PRIORIDADES (ESCALA CORRETA) ---
# Ordem: Vermelho (Base) -> Amarelo -> Verde -> Diamante (Topo)
MAPA_PRIORIDADES = {
    "red": "Vermelho",      # Alta Prioridade / Atrasado
    "yellow": "Amarelo",    # Médio
    "green": "Verde",       # Ok / Fácil
    "purple": "Diamante",   # Muito Importante (Reta Final)
    # Mapeamentos de fallback para cores não oficiais
    "orange": "Vermelho",   # Laranja vira Vermelho (Alta prioridade)
    "blue": "Verde",        # Azul vira Verde (Baixa prioridade)
    "gray": "Normal"
}

PRIORIDADES_VISUAIS = {
    "Diamante": "💎 Diamante",
    "Vermelho": "🔴 Vermelho",
    "Amarelo": "🟡 Amarelo",
    "Verde": "🟢 Verde",
    "Normal": "⚪ Normal"
}

def normalizar_texto_match(texto):
    """
    Remove acentos, converte para minúsculo e remove caracteres não alfanuméricos
    para comparação robusta de strings.
    Ex: "Anemias Hipoproliferativas I" -> "anemiashipoproliferativasi"
    """
    if not isinstance(texto, str): return ""
    # Normaliza unicode (remove acentos)
    nfkd = unicodedata.normalize('NFKD', texto)
    sem_acento = u"".join([c for c in nfkd if not unicodedata.combining(c)])
    # Mantém apenas letras e números, tudo minúsculo
    return re.sub(r'[^a-z0-9]', '', sem_acento.lower())

def importar_prioridades_html():
    """
    Lê o ficheiro HTML enviado e extrai: {Nome Normalizado da Aula: Prioridade}
    """
    mapa_prioridades = {}
    try:
        # Tenta encontrar o arquivo HTML no diretório
        arquivos = [f for f in os.listdir('.') if f.endswith('.html') and 'MEDCOF' in f]
        if not arquivos:
            return {}
            
        with open(arquivos[0], 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Regex ajustado para capturar a estrutura da tabela do Notion
        # Procura: <span class="...color-COR">TEXTO</span> ... <a ...>NOME DA AULA</a>
        # O re.DOTALL permite que o .*? atravesse quebras de linha
        padrao = re.compile(r'select-value-color-(\w+)">([^<]+)</span>.*?<td class="cell-title"><a href="[^"]+">([^<]+)</a>', re.DOTALL)
        matches = padrao.findall(content)
        
        for cor_ingles, nome_cor_html, titulo_aula_html in matches:
            # Normaliza a chave para garantir o match
            chave_normalizada = normalizar_texto_match(titulo_aula_html)
            
            # Determina a prioridade
            prio = "Normal"
            
            # 1. Checa explicitamente se é Diamante pelo texto da etiqueta
            if "Diamante" in nome_cor_html or "purple" in cor_ingles:
                prio = "Diamante"
            # 2. Senão, usa o mapeamento de cores
            else:
                prio = MAPA_PRIORIDADES.get(cor_ingles, "Normal")
            
            # Salva no mapa usando a chave 'limpa'
            if chave_normalizada:
                mapa_prioridades[chave_normalizada] = prio
                
    except Exception as e:
        print(f"Erro ao importar HTML: {e}")
        
    return mapa_prioridades

def update_row_callback(u, aula_nome, full_state):
    check = st.session_state.get(f"chk_{aula_nome}", False)
    # Tenta pegar a prioridade do selectbox, senão mantém a atual
    prio = st.session_state.get(f"prio_{aula_nome}", full_state.get(aula_nome, {}).get("prioridade", "Normal"))
    
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
    except: return [], {}, {}

    # 2. Carrega prioridades do HTML
    prio_html_map = importar_prioridades_html()
    
    mapa, idx, curr = [], 0, "Geral"
    for l in lines:
        m = re.search(r'#\s*-+\s*(BLOCO\s*.*)\s*-+', l)
        if m: curr = m.group(1).strip()
        if idx < len(dados):
            item = dados[idx]
            aula = item[0] if isinstance(item, tuple) else item
            area = item[1] if isinstance(item, tuple) and len(item)>1 else "Geral"
            
            if aula in l:
                # Normaliza o nome da aula vindo do Python para buscar no mapa do HTML
                chave_busca = normalizar_texto_match(aula)
                
                # Busca exata pela chave normalizada
                prio_detectada = prio_html_map.get(chave_busca, "Normal")
                
                # Debug: Se for Anemia Hipoproliferativa I e não achou, força log (opcional)
                # if "anemiashipoproliferativasi" in chave_busca:
                #     print(f"DEBUG: {aula} -> {prio_detectada}")

                mapa.append({
                    "Bloco": curr, 
                    "Aula": aula, 
                    "Area": normalizar_area(area),
                    "Prioridade_HTML": prio_detectada
                })
                idx += 1
    return mapa, dados, prio_html_map

def render_cronograma(conn_ignored):
    st.header("🗂️ Cronograma & Prioridades")
    
    import os
    if os.path.exists("MEDCOF 2026 2fd60e4aba71806496a9d52180699c35.html"):
        st.success("Prioridades sincronizadas com o plano oficial.", icon="💎")
    
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
        
        # Só atualiza se o banco estiver "virgem" (Normal) e o HTML tiver algo relevante
        # E garante que não sobrescrevemos uma definição manual do usuário se ele já mudou
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
        
        with st.expander(f"{bl} ({feitas}/{len(aulas)})", expanded=False):
            for _, r in aulas.iterrows():
                aula = r['Aula']
                d = estado.get(aula, {"feito": False, "prioridade": "Normal", "acertos": 0, "total": 0})
                
                c1, c2, c3 = st.columns([0.1, 0.6, 0.3])
                
                # 1. Check + Nome
                c1.checkbox(" ", value=d.get('feito', False), key=f"chk_{aula}", on_change=update_row_callback, args=(u, aula, estado), label_visibility="collapsed")
                
                # 2. Detalhes (Nome, Area, Prioridade)
                with c2:
                    prio_key = d.get('prioridade', 'Normal')
                    # Garante que temos um emoji mesmo se a chave for estranha
                    emoji_prio = PRIORIDADES_VISUAIS.get(prio_key, PRIORIDADES_VISUAIS["Normal"])[0]
                    
                    st.markdown(f"**{aula}**")
                    # Badge colorido manualmente para destaque
                    cor_texto = "gray"
                    if prio_key == "Diamante": cor_texto = "purple"
                    elif prio_key == "Vermelho": cor_texto = "red"
                    elif prio_key == "Verde": cor_texto = "green"
                    elif prio_key == "Amarelo": cor_texto = "#DAA520" # Goldenrod
                    
                    st.markdown(f"<span style='color:{cor_texto}'>{emoji_prio} {prio_key}</span> • <small>{r['Area']}</small>", unsafe_allow_html=True)

                # 3. Questões (Visualização)
                with c3:
                    ac = d.get('acertos', 0)
                    tot = d.get('total', 0)
                    perc = int(ac/tot*100) if tot > 0 else 0
                    
                    st.progress(perc/100, text=f"{ac}/{tot} ({perc}%)")