import streamlit as st
import time
import google.generativeai as genai

# Tenta carregar a chave dos segredos
API_KEY = st.secrets.get("GEMINI_KEY", None)

def configurar_ia():
    if API_KEY:
        genai.configure(api_key=API_KEY)
        # Configura o modelo
        model = genai.GenerativeModel(
            model_name='gemini-2.0-flash', # Modelo rápido e inteligente
            system_instruction="""
            Você é um Mentor de Residência Médica experiente e didático.
            Seu objetivo é ajudar estudantes de medicina e médicos recém-formados.
            
            Diretrizes:
            1. Seja direto e focado em provas de residência (R1).
            2. Use termos técnicos corretos, mas explique de forma simples.
            3. Sempre que possível, forneça mnemônicos para memorização.
            4. Se a pergunta for sobre conduta, cite os guidelines mais recentes (ex: AHA, ADA, MS-BR).
            5. Não dê diagnósticos para casos reais de pacientes (aviso legal). Foco acadêmico.
            """
        )
        return model
    return None

def render_mentor(conn_ignored):
    st.header("🤖 Mentor IA - MedPlanner")
    st.caption("Seu assistente clínico 24h para tirar dúvidas e revisar conceitos.")

    # Verifica conexão
    if API_KEY:
        model = configurar_ia()
        st.success("🟢 Conectado ao Google Gemini")
    else:
        st.warning("⚠️ Modo Demonstração (Sem API Key). Adicione 'GEMINI_KEY' ao secrets.toml.")
        model = None

    # Histórico do Chat
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
        # Mensagem inicial
        st.session_state.chat_history.append({
            "role": "assistant", 
            "content": "Olá, Doutor(a)! Qual tema vamos dominar hoje? Posso explicar fisiopatologia, criar mnemônicos ou discutir questões."
        })

    # Renderiza mensagens anteriores
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input do Usuário
    if prompt := st.chat_input("Ex: 'Qual a tríade de Cushing?' ou 'Mnemônico para causas de Pancreatite'"):
        
        # 1. Exibe e salva pergunta
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Gera resposta
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            if model:
                try:
                    # Envia para o Gemini com histórico (contexto)
                    # O Gemini espera histórico no formato: [{'role': 'user'/'model', 'parts': ['text']}]
                    history_gemini = [
                        {"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]}
                        for m in st.session_state.chat_history if m["role"] != "system"
                    ]
                    
                    chat = model.start_chat(history=history_gemini[:-1])
                    response = chat.send_message(prompt, stream=True)
                    
                    for chunk in response:
                        if chunk.text:
                            full_response += chunk.text
                            message_placeholder.markdown(full_response + "▌")
                    
                    message_placeholder.markdown(full_response)
                    
                except Exception as e:
                    st.error(f"Erro na IA: {e}")
                    full_response = "Tive um problema de conexão. Tente novamente em instantes."
            else:
                # Fallback Demo
                time.sleep(1)
                full_response = "**[Modo Demo]** Resposta simulada.\n\n"
                full_response += f"Sobre *{prompt}*, o conceito chave para provas é focar na apresentação clínica típica."
                message_placeholder.markdown(full_response)

        # 3. Salva resposta
        st.session_state.chat_history.append({"role": "assistant", "content": full_response})