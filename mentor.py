import streamlit as st
import time, random

def render_mentor(conn_ignored):
    st.header("🤖 Mentor IA")
    st.caption("Seu assistente clínico 24h.")
    
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [{"role": "assistant", "content": "Olá! Qual dúvida médica posso esclarecer hoje?"}]
        
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
        
    if p := st.chat_input("Pergunte..."):
        st.session_state.chat_history.append({"role": "user", "content": p})
        with st.chat_message("user"): st.markdown(p)
        
        with st.chat_message("assistant"):
            ph = st.empty()
            # Lógica Mockada (Substituir por API real)
            resps = ["Baseado nos guidelines atuais, a conduta é...", "Lembre-se do mnemônico para isso...", "Essa questão exige atenção aos critérios de..."]
            full = f"**Análise:**\n\n{random.choice(resps)}"
            
            # Efeito digitação
            curr = ""
            for ch in full: curr += ch; ph.markdown(curr + "▌"); time.sleep(0.01)
            ph.markdown(full)
            st.session_state.chat_history.append({"role": "assistant", "content": full})
