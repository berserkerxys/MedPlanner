import streamlit as st
from database import get_caderno_erros, salvar_caderno_erros

def render_caderno_erros(conn_ignored):
    st.header("🧠 Caderno de Erros")
    st.caption("Registre seus erros para não cometê-los na prova.")
    u = st.session_state.username
    areas = ["Cirurgia", "Clínica Médica", "Ginecologia e Obstetrícia", "Pediatria", "Preventiva"]
    
    t = st.tabs(areas)
    for i, ar in enumerate(areas):
        with t[i]:
            cont = get_caderno_erros(u, ar)
            c1, c2 = st.columns([2, 1])
            txt = c1.text_area(f"Erros em {ar}:", value=cont, height=400, key=f"te_{ar}")
            with c2:
                st.info("Escreva o conceito correto, não apenas a resposta.")
                if st.button(f"Salvar {ar}", key=f"be_{ar}", type="primary"):
                    if salvar_caderno_erros(u, ar, txt): st.toast("Salvo!", icon="✅")