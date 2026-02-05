import streamlit as st
import pandas as pd
import re
from database import get_cronograma_status, salvar_cronograma_status, normalizar_area

# --- CONFIGURAÇÃO VISUAL ---
PRIORIDADES_STYLE = {
    "Diamante": {"icon": "💎", "color": "#9C27B0", "bg": "#F3E5F5", "label": "Diamante"}, # Roxo
    "Vermelho": {"icon": "🔴", "color": "#D32F2F", "bg": "#FFEBEE", "label": "Alta"},     # Vermelho
    "Amarelo":  {"icon": "🟡", "color": "#FBC02D", "bg": "#FFFDE7", "label": "Média"},    # Amarelo
    "Verde":    {"icon": "🟢", "color": "#388E3C", "bg": "#E8F5E9", "label": "Baixa"},    # Verde
    "Normal":   {"icon": "⚪", "color": "#757575", "bg": "#F5F5F5", "label": "Normal"}
}

def update_row_callback(u, aula_nome, full_state):
    """Callback para salvar alterações imediatamente."""
    check = st.session_state.get(f"chk_{aula_nome}", False)
    # Mantém os valores numéricos se existirem na sessão, senão pega do banco
    ac = st.session_state.get(f"ac_{aula_nome}", full_state.get(aula_nome, {}).get("acertos", 0))
    tt = st.session_state.get(f"tt_{aula_nome}", full_state.get(aula_nome, {}).get("total", 0))
    # A prioridade agora é estática (vem do arquivo), mas salvamos no estado para persistência se necessário
    prio = full_state.get(aula_nome, {}).get("prioridade", "Normal")

    full_state[aula_nome] = {
        "feito": check,
        "prioridade": prio,
        "acertos": ac,
        "total": tt
    }
    salvar_cronograma_status(u, full_state)
    st.toast("Progresso salvo!", icon="✅")

def ler_dados_nativos():
    """
    Lê o arquivo aulas_medcof.py e monta a estrutura com Blocos e Prioridades.
    """
    mapa = []
    try:
        import aulas_medcof
        dados_brutos = getattr(aulas_medcof, 'DADOS_LIMPOS', [])
        
        # Lê o arquivo como texto para identificar os comentários dos blocos
        with open('aulas_medcof.py', 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        idx = 0
        bloco_atual = "Geral"
        
        for line in lines:
            # Detecta mudança de bloco
            match_bloco = re.search(r'#\s*-+\s*(BLOCO\s*.*)\s*-+', line, re.IGNORECASE)
            if match_bloco:
                bloco_atual = match_bloco.group(1).strip()
            
            # Tenta associar linha com o dado estruturado
            if idx < len(dados_brutos):
                item = dados_brutos[idx]
                # O item pode ser (Aula, Area) ou (Aula, Area, Prioridade)
                nome_aula = item[0]
                
                # Verificação simples se a linha contém a aula atual
                if nome_aula in line:
                    area = item[1]
                    # Se tiver prioridade na tupla (3 itens), usa. Senão "Normal".
                    prio = item[2] if len(item) > 2 else "Normal"
                    
                    mapa.append({
                        "Bloco": bloco_atual,
                        "Aula": nome_aula,
                        "Area": normalizar_area(area),
                        "Prioridade": prio
                    })
                    idx += 1
                    
        return mapa
    except Exception as e:
        print(f"Erro ao ler arquivo nativo: {e}")
        return []

def render_cronograma(conn_ignored):
    st.header("🗂️ Cronograma Extensivo")
    st.caption("Acompanhe sua jornada rumo à aprovação.")
    
    u = st.session_state.username
    
    # 1. Carregar Dados
    dados_mapa = ler_dados_nativos()
    if not dados_mapa:
        st.warning("Nenhum dado encontrado em aulas_medcof.py")
        return
        
    df = pd.DataFrame(dados_mapa)
    
    # 2. Carregar Estado do Banco
    estado_banco = get_cronograma_status(u)
    
    # KPIs de Progresso
    total_aulas = len(df)
    concluidas = sum(1 for k, v in estado_banco.items() if v.get('feito'))
    total_questoes = sum(v.get('total', 0) for v in estado_banco.values())
    
    # Barra de Progresso Estilizada
    st.progress(concluidas/total_aulas, text=f"**Progresso Geral:** {concluidas}/{total_aulas} temas finalizados")
    
    c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
    c_kpi1.metric("Questões Totais", total_questoes)
    c_kpi2.metric("Pendentes", total_aulas - concluidas)
    c_kpi3.caption("Priorize os temas Diamante 💎")
    
    st.divider()

    # 3. Renderização por Blocos
    blocos = df['Bloco'].unique()
    
    for bloco in blocos:
        df_bloco = df[df['Bloco'] == bloco]
        feitas_bloco = sum(1 for a in df_bloco['Aula'] if estado_banco.get(a, {}).get('feito'))
        
        # Expander do Bloco
        with st.expander(f"📚 {bloco} ({feitas_bloco}/{len(df_bloco)})", expanded=False):
            
            # Iterar Aulas
            for _, row in df_bloco.iterrows():
                aula = row['Aula']
                area = row['Area']
                prio_arquivo = row['Prioridade'] # Prioridade oficial do arquivo
                
                # Recupera estado do usuário ou cria padrão
                d_user = estado_banco.get(aula, {})
                feito = d_user.get('feito', False)
                acertos = d_user.get('acertos', 0)
                total = d_user.get('total', 0)
                
                # --- LAYOUT DA LINHA ---
                # Checkbox | Badge Prioridade | Nome Aula + Area | Barra Progresso
                c1, c2, c3, c4 = st.columns([0.05, 0.2, 0.45, 0.3])
                
                # 1. Checkbox
                c1.checkbox(
                    " ", 
                    value=feito, 
                    key=f"chk_{aula}", 
                    on_change=update_row_callback, 
                    args=(u, aula, estado_banco),
                    label_visibility="collapsed"
                )
                
                # 2. Badge de Prioridade (Visual Bonito)
                with c2:
                    style = PRIORIDADES_STYLE.get(prio_arquivo, PRIORIDADES_STYLE["Normal"])
                    st.markdown(
                        f"""
                        <div style="
                            background-color: {style['bg']}; 
                            color: {style['color']}; 
                            padding: 4px 8px; 
                            border-radius: 6px; 
                            text-align: center; 
                            font-size: 0.8rem; 
                            font-weight: bold;
                            border: 1px solid {style['color']}40;">
                            {style['icon']} {style['label']}
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )

                # 3. Nome da Aula e Área
                with c3:
                    st.markdown(f"**{aula}**")
                    st.caption(f"{area}")

                # 4. Barra de Questões (Visualização)
                with c4:
                    if total > 0:
                        perc = int(acertos / total * 100)
                        st.progress(perc / 100, text=f"{acertos}/{total} ({perc}%)")
                    else:
                        st.caption("Sem questões registradas")
                
                st.markdown("<hr style='margin: 5px 0; border-top: 1px solid #f0f2f6;'>", unsafe_allow_html=True)