import streamlit as st
import pandas as pd
import re
from database import (
    atualizar_nome_assunto, deletar_assunto, resetar_progresso, 
    salvar_config, ler_config, registrar_topico_do_sumario, get_connection
)

# Função para separar CamelCase (ex: #AdenomegaliasFebrisi -> Adenomegalias Febris)
def limpar_nome_hashtag(texto):
    texto = texto.replace("#", "").replace("_", " ").strip()
    # Insere espaço antes de letras maiúsculas
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', texto).strip()

def render_configuracoes(conn):
    st.header("⚙️ Ajustes & Importação")

    # ==========================================
    # 1. IMPORTADOR DE SUMÁRIO (GABARITO)
    # ==========================================
    st.subheader("📑 1. Criar Gabarito (Importar Sumários)")
    st.info("Aqui você ensina ao sistema quais aulas pertencem a qual área.")

    with st.container(border=True):
        # 1. Selecionar a Área
        areas = ["Cirurgia", "Clínica Médica", "G.O.", "Pediatria", "Preventiva", "NeuroPed"]
        area_alvo = st.selectbox("Para qual Área você vai colar o sumário?", areas)
        
        # 2. Colar o texto
        texto_sumario = st.text_area(
            f"Cole o sumário de {area_alvo} aqui (copie do Telegram):", 
            height=200,
            placeholder="Ex:\n🔹 #Crescimento (4 aulas)\n🔹 #Desenvolvimento..."
        )

        if st.button(f"🚀 Cadastrar Aulas em {area_alvo}"):
            if not texto_sumario:
                st.warning("Cole o texto primeiro.")
            else:
                # Extrai tudo que tem #Hashtag
                hashtags = re.findall(r"#(\w+)", texto_sumario)
                
                if not hashtags:
                    st.error("Não achei nenhuma hashtag (#) no texto.")
                else:
                    count = 0
                    lista_criada = []
                    
                    progress_text = "Cadastrando..."
                    my_bar = st.progress(0, text=progress_text)
                    
                    total = len(hashtags)
                    for i, tag in enumerate(hashtags):
                        # Ignora se for a tag da própria área (ex: #Pediatria)
                        if tag.lower() in area_alvo.lower().replace(".",""):
                            continue
                            
                        nome_limpo = limpar_nome_hashtag(tag)
                        
                        # Manda pro banco (database.py)
                        registrar_topico_do_sumario(area_alvo, nome_limpo)
                        lista_criada.append(nome_limpo)
                        count += 1
                        my_bar.progress((i + 1) / total)
                    
                    my_bar.empty()
                    st.success(f"✅ Sucesso! {count} aulas cadastradas em **{area_alvo}**.")
                    with st.expander("Ver lista cadastrada"):
                        st.write(", ".join(lista_criada))

    st.divider()

    # ==========================================
    # 2. CONFIGURAÇÃO DO ROBÔ (Mantido)
    # ==========================================
    with st.expander("🤖 Configurações do Bot"):
        db_meta = ler_config("meta_diaria")
        with st.form("form_bot"):
            meta = st.number_input("Meta Diária", value=int(db_meta) if db_meta else 50)
            if st.form_submit_button("Salvar Meta"):
                salvar_config("meta_diaria", meta)
                st.success("Salvo!")

    st.divider()

    # ==========================================
    # 3. GESTÃO MANUAL (CORREÇÕES)
    # ==========================================
    st.subheader("🛠️ Correção Manual")
    
    # Busca aulas existentes
    try:
        df = pd.read_sql("SELECT id, nome, grande_area FROM assuntos ORDER BY nome", conn)
        opcoes = {f"{row['nome']} ({row['grande_area']})": row['id'] for _, row in df.iterrows()}
    except: opcoes = {}

    c1, c2 = st.columns([3, 1])
    with c1:
        sel = st.selectbox("Editar aula:", list(opcoes.keys()) if opcoes else [])
    
    with c2:
        st.write("")
        st.write("")
        if st.button("🗑️ Apagar Aula"):
            if sel:
                deletar_assunto(opcoes[sel])
                st.rerun()

    st.divider()
    
    # ZONA DE PERIGO
    if st.button("🔥 Resetar Tudo (Começar do Zero)", type="primary"):
        resetar_progresso()
        st.toast("Tudo limpo!")
        st.rerun()