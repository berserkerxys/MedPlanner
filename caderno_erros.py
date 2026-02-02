import streamlit as st
from database import get_caderno_erros, salvar_caderno_erros

def render_caderno_erros(conn_ignored):
    st.header("🧠 Caderno de Erros Inteligente")
    st.caption("Registre seus erros e o conceito correto para fixação.")

    u = st.session_state.username
    areas = ["Cirurgia", "Clínica Médica", "Ginecologia e Obstetrícia", "Pediatria", "Preventiva"]
    
    # Navegação por abas
    tab_areas = st.tabs(areas)
    
    for i, area in enumerate(areas):
        with tab_areas[i]:
            # Chave única para o session_state desta área
            key_texto = f"txt_erro_{area}"
            
            # Se não houver texto na sessão, carrega do banco
            if key_texto not in st.session_state:
                conteudo_banco = get_caderno_erros(u, area)
                st.session_state[key_texto] = conteudo_banco if conteudo_banco else ""
            
            c1, c2 = st.columns([2, 1])
            
            with c1:
                # O text_area agora está ligado diretamente ao session_state
                st.text_area(
                    f"Anotações de {area}:", 
                    height=500,
                    key=key_texto, # Vincula ao estado persistente
                    placeholder="Ex: Errei questão sobre Trauma Abdominal.\nConceito Correto: Lavado Peritoneal Positivo requer laparotomia se...",
                    help="O texto é mantido enquanto você navega entre as abas."
                )
            
            with c2:
                st.info("💡 **Dica de Ouro:**\nNão copie o livro. Escreva com suas palavras o motivo do erro (Falta de atenção? Lacuna teórica?).")
                
                # Botão de Salvar
                if st.button(f"💾 Salvar {area}", key=f"btn_erro_{area}", type="primary", use_container_width=True):
                    # Pega o valor mais atual do session_state
                    texto_para_salvar = st.session_state[key_texto]
                    
                    # Tenta salvar e captura retorno
                    sucesso = salvar_caderno_erros(u, area, texto_para_salvar)
                    
                    if sucesso:
                        st.toast("Anotação salva com sucesso!", icon="✅")
                    else:
                        st.error("Erro ao salvar. Verifique se o banco de dados foi inicializado corretamente.")