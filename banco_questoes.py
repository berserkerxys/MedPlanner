import streamlit as st
import streamlit.components.v1 as components

def render_banco_questoes(conn_ignored):
    st.header("🏦 Banco de Questões - Hardworq")
    st.caption("Acesse diretamente a plataforma de questões.")
    
    # URL do seu site externo
    # Certifique-se de que o site permite ser incorporado (X-Frame-Options)
    url_externa = "https://app.hardworq.com.br/hardworq/home-questoes/banco-questoes" 

    # Renderiza o site dentro do Streamlit
    # height=1000 garante uma boa área vertical para resolver questões sem scroll duplo excessivo
    components.iframe(url_externa, height=1000, scrolling=True)