import streamlit as st
from database import registrar_estudo

def render_simulado_real(conn_ignored):
    st.header("⏱️ Simulado Realista")
    u = st.session_state.username
    
    c1, c2 = st.columns(2)
    qtd = c1.slider("Questões:", 10, 100, 50, 10)
    area = c2.selectbox("Foco:", ["Geral", "Cirurgia", "Clínica", "Pediatria", "G.O.", "Preventiva"])
    
    with st.form("gab"):
        st.subheader("Gabarito")
        cols = st.columns(5)
        for i in range(1, qtd+1):
            cols[(i-1)%5].radio(f"{i}", ["A","B","C","D"], horizontal=True, key=f"q{i}", label_visibility="collapsed")
        if st.form_submit_button("Finalizar"):
            st.session_state.sim_done = True
            
    if st.session_state.get("sim_done"):
        with st.container(border=True):
            ac = st.number_input("Quantas você acertou?", 0, qtd)
            if st.button("Salvar Resultado"):
                msg = registrar_estudo(u, f"Simulado {qtd}q", ac, qtd, area_f=area, srs=False)
                st.success(msg); st.session_state.sim_done = False