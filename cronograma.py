import streamlit as st
import pandas as pd
import re
from database import get_cronograma_status, salvar_cronograma_status, normalizar_area

def auto_save_callback(u, dados_brutos):
    """
    Função chamada automaticamente toda vez que um checkbox é alterado.
    Lê o estado atual da sessão e salva no banco imediatamente.
    """
    novo_estado = {}
    # dados_brutos aqui é a lista completa de tuplas, garantindo que salvamos tudo
    for item in dados_brutos:
        nome_aula = item[0] if isinstance(item, tuple) else item
        key = f"chk_{nome_aula}"
        if st.session_state.get(key, False):
            novo_estado[nome_aula] = True
            
    salvar_cronograma_status(u, novo_estado)
    st.toast("Salvo automaticamente!", icon="✅")

def ler_blocos_do_arquivo():
    """
    Lê o arquivo aulas_medcof.py como texto para identificar os comentários de 'BLOCO'.
    Retorna uma lista de dicionários: [{'Bloco': 'BLOCO 1', 'Aula': 'Nome...', 'Area': 'Area...'}, ...]
    """
    items_mapeados = []
    try:
        # Importamos os dados reais para garantir integridade
        import aulas_medcof
        dados_reais = getattr(aulas_medcof, 'DADOS_LIMPOS', [])
        
        # Lemos o arquivo para pegar os metadados (Blocos)
        with open('aulas_medcof.py', 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        current_block = "Geral"
        data_index = 0
        
        # Regex para encontrar '# --- BLOCO X ---'
        block_pattern = re.compile(r'#\s*-+\s*(BLOCO\s*.*)\s*-+')
        
        for line in lines:
            line = line.strip()
            
            # 1. Detecta mudança de Bloco
            match = block_pattern.search(line)
            if match:
                current_block = match.group(1).strip() # Ex: "BLOCO 1"
            
            # 2. Sincroniza com a lista de dados
            # Se a linha parece uma tupla e ainda temos dados para mapear
            if data_index < len(dados_reais):
                aula_real, area_real = dados_reais[data_index]
                
                # Verifica se o nome da aula está nesta linha (confirmação frouxa)
                # Usamos ' in ' para evitar problemas com aspas simples/duplas
                if aula_real in line:
                    items_mapeados.append({
                        "Bloco": current_block,
                        "Aula": aula_real,
                        "Area": normalizar_area(area_real)
                    })
                    data_index += 1
                    
        return items_mapeados, dados_reais

    except Exception as e:
        print(f"Erro ao ler blocos: {e}")
        # Retorna vazio em caso de erro para cair no fallback
        return [], []

def render_cronograma(conn_ignored):
    st.header("🗂️ Cronograma Extensivo")
    st.caption("Seu progresso é salvo automaticamente ao marcar os itens.")

    u = st.session_state.username
    
    # 1. Carregar dados com estrutura de Blocos
    df_blocos = pd.DataFrame()
    items_mapeados, dados_brutos = ler_blocos_do_arquivo()
    
    # Fallback: Se não conseguir ler o arquivo, usa importação padrão
    if not items_mapeados:
        try:
            import aulas_medcof
            dados_brutos = getattr(aulas_medcof, 'DADOS_LIMPOS', [])
            # Cria DataFrame sem blocos (tudo Geral)
            df_blocos = pd.DataFrame(dados_brutos, columns=['Aula', 'Area'])
            df_blocos['Bloco'] = 'Lista Completa'
            df_blocos['Area'] = df_blocos['Area'].apply(normalizar_area)
        except ImportError:
            st.error("Arquivo aulas_medcof.py não encontrado.")
            return
    else:
        df_blocos = pd.DataFrame(items_mapeados)

    if df_blocos.empty:
        st.warning("Lista de aulas vazia.")
        return

    # 2. Carregar estado salvo
    estado_salvo = get_cronograma_status(u)
    
    # Barra de Progresso Geral
    total_aulas = len(df_blocos)
    concluidas = sum(1 for k in estado_salvo if estado_salvo.get(k))
    progresso = concluidas / total_aulas if total_aulas > 0 else 0
    st.progress(progresso, text=f"Progresso Geral: {concluidas}/{total_aulas} ({progresso:.1%})")

    # 3. Renderizar por Blocos (Mantendo a ordem original)
    # .unique() preserva a ordem de aparição no pandas
    blocos = df_blocos['Bloco'].unique()
    
    for bloco in blocos:
        # Filtra aulas deste bloco
        df_b = df_blocos[df_blocos['Bloco'] == bloco]
        aulas_bloco = df_b['Aula'].tolist()
        
        # Conta concluidas neste bloco
        concluidas_bloco = sum(1 for a in aulas_bloco if estado_salvo.get(a))
        
        # Expander do Bloco
        with st.expander(f"📚 {bloco} ({concluidas_bloco}/{len(aulas_bloco)})"):
            for idx, row in df_b.iterrows():
                aula = row['Aula']
                area = row['Area']
                is_checked = estado_salvo.get(aula, False)
                
                # Layout: Checkbox + Badge da Área
                col_check, col_badge = st.columns([0.8, 0.2])
                
                with col_check:
                    st.checkbox(
                        aula, 
                        value=is_checked, 
                        key=f"chk_{aula}",
                        on_change=auto_save_callback,
                        args=(u, dados_brutos)
                    )
                with col_badge:
                    # Pequena badge visual para a área
                    st.caption(f"_{area}_")