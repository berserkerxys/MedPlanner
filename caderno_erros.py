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
            key_texto = f"txt_erro_{area}"
            
            # Carrega inicial se não existir na sessão
            if key_texto not in st.session_state:
                conteudo_banco = get_caderno_erros(u, area)
                st.session_state[key_texto] = conteudo_banco if conteudo_banco else ""
            
            c1, c2 = st.columns([2, 1])
            
            with c1:
                # Text Area vinculada ao session_state
                st.text_area(
                    f"Anotações de {area}:", 
                    height=500,
                    key=key_texto, 
                    placeholder="Ex: Errei questão sobre Trauma. Conceito correto: ..."
                )
            
            with c2:
                st.info("💡 **Dica:** Escreva o *motivo* do erro, não só a resposta.")
                
                if st.button(f"💾 Salvar {area}", key=f"btn_{area}", type="primary", use_container_width=True):
                    texto = st.session_state[key_texto]
                    if salvar_caderno_erros(u, area, texto):
                        st.toast("Salvo com sucesso!", icon="✅")
                    else:
                        st.error("Erro ao salvar. Verifique conexão.")