import streamlit as st
import time
import google.generativeai as genai

# Tenta importar Groq de forma segura
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# --- GERENCIAMENTO DE CHAVES ---
def get_secret(key):
    # Tenta pegar na raiz
    val = st.secrets.get(key, None)
    # Se não achar, procura dentro do bloco supabase (caso o toml esteja mal formatado)
    if not val and "supabase" in st.secrets:
        if isinstance(st.secrets["supabase"], dict):
            val = st.secrets["supabase"].get(key, None)
        elif hasattr(st.secrets["supabase"], key):
            val = getattr(st.secrets["supabase"], key)
    return val

GEMINI_KEY = get_secret("GEMINI_KEY")
GROQ_KEY = get_secret("GROQ_API_KEY")

# --- MOTOR DE INTELIGÊNCIA ---
def configurar_cliente():
    """
    Decide qual IA usar baseada nas chaves disponíveis.
    Prioridade: Groq (Mais rápida/Llama 3) > Gemini (Google)
    """
    # 1. Tenta Groq (Llama 3)
    if GROQ_AVAILABLE and GROQ_KEY:
        try:
            client = Groq(api_key=GROQ_KEY)
            # Retorna: (provider_name, client_object, model_name)
            return "groq", client, "llama3-70b-8192"
        except Exception as e:
            print(f"Erro ao iniciar Groq: {e}")
    
    # 2. Tenta Gemini (Google)
    if GEMINI_KEY:
        try:
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel('gemini-2.0-flash')
            return "gemini", model, "gemini-2.0-flash"
        except Exception as e:
            print(f"Erro ao iniciar Gemini: {e}")

    return None, None, None

def render_mentor(conn_ignored):
    st.header("🤖 Mentor IA - MedPlanner")
    
    # Inicializa o motor
    provider, client, model_name = configurar_cliente()
    
    # Indicador de Status
    if provider == "groq":
        st.caption(f"🟢 **Conectado:** Llama 3 (via Groq) | ⚡ Alta Velocidade")
    elif provider == "gemini":
        st.caption(f"🔵 **Conectado:** Gemini Flash (via Google) | 🧠 Alta Precisão")
    else:
        st.warning("⚠️ Modo Offline (Sem chaves configuradas).")
        st.caption("Adicione `GROQ_API_KEY` ou `GEMINI_KEY` aos segredos.")

    # Histórico do Chat
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
        # Mensagem de Boas-Vindas
        welcome_msg = "Olá, Doutor(a)! Sou seu preceptor virtual. Posso criar mnemônicos, explicar fisiopatologia ou discutir casos clínicos. Qual o foco de hoje?"
        st.session_state.chat_history.append({"role": "assistant", "content": welcome_msg})

    # Renderiza Histórico
    for msg in st.session_state.chat_history:
        # Normaliza ícones
        avatar = "🤖" if msg["role"] == "assistant" else "👨‍⚕️"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # Input do Usuário
    if prompt := st.chat_input("Ex: Diferença entre Síndrome Nefrítica e Nefrótica..."):
        
        # 1. Adiciona e exibe pergunta do usuário
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👨‍⚕️"):
            st.markdown(prompt)

        # 2. Processa resposta da IA
        with st.chat_message("assistant", avatar="🤖"):
            message_placeholder = st.empty()
            full_response = ""
            
            if client:
                try:
                    # --- ESTRATÉGIA GROQ ---
                    if provider == "groq":
                        # Prepara mensagens no formato OpenAI
                        messages = [
                            {"role": "system", "content": "Você é um mentor experiente de residência médica no Brasil. Responda de forma didática, direta e focada em provas (R1/R3). Use negrito para conceitos chave e cite guidelines recentes (SBC, SBP, FEBRASGO)."},
                        ]
                        for m in st.session_state.chat_history:
                            # Filtra histórico para evitar erros de role
                            role = "assistant" if m["role"] == "assistant" else "user"
                            messages.append({"role": role, "content": m["content"]})
                        
                        stream = client.chat.completions.create(
                            model=model_name,
                            messages=messages,
                            stream=True,
                            temperature=0.6 # Equilíbrio entre criatividade e precisão
                        )
                        
                        for chunk in stream:
                            if chunk.choices[0].delta.content:
                                content = chunk.choices[0].delta.content
                                full_response += content
                                message_placeholder.markdown(full_response + "▌")

                    # --- ESTRATÉGIA GEMINI ---
                    elif provider == "gemini":
                        # Prepara histórico no formato Google
                        gemini_history = []
                        for m in st.session_state.chat_history[:-1]: # Ignora a última (que é o prompt atual)
                            role = "model" if m["role"] == "assistant" else "user"
                            gemini_history.append({"role": role, "parts": [m["content"]]})
                        
                        chat = client.start_chat(history=gemini_history)
                        response = chat.send_message(prompt, stream=True)
                        
                        for chunk in response:
                            if chunk.text:
                                full_response += chunk.text
                                message_placeholder.markdown(full_response + "▌")

                    # Finaliza visualização
                    message_placeholder.markdown(full_response)

                except Exception as e:
                    # Tratamento de Erro Unificado
                    error_msg = str(e).lower()
                    if "429" in error_msg or "quota" in error_msg or "rate limit" in error_msg:
                        full_response = "⚠️ **Mentor Sobrecarregado.**\nAtingimos o limite de velocidade da IA momentaneamente. Aguarde 30 segundos e tente novamente."
                        message_placeholder.warning(full_response)
                    else:
                        full_response = f"Erro técnico na conexão: {e}"
                        message_placeholder.error(full_response)
            else:
                # Fallback Offline
                time.sleep(1)
                full_response = "**[Modo Demo]** Configure uma API Key (Groq ou Gemini) para respostas reais.\n\n"
                full_response += f"Sua pergunta sobre *'{prompt}'* é relevante. Foque nos critérios diagnósticos e tratamento inicial."
                message_placeholder.markdown(full_response)

        # 3. Salva no histórico se não for erro
        if full_response and "Erro técnico" not in full_response:
            st.session_state.chat_history.append({"role": "assistant", "content": full_response})