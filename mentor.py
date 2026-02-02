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
    val = st.secrets.get(key, None)
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
    Decide qual IA usar.
    Prioridade: Groq (Llama 3.3) > Gemini 2.0 Flash
    """
    # 1. Tenta Groq (Modelo Atualizado: llama-3.3-70b-versatile)
    if GROQ_AVAILABLE and GROQ_KEY:
        try:
            client = Groq(api_key=GROQ_KEY)
            # Modelo mais recente e estável da Groq (Fev/2026)
            return "groq", client, "llama-3.3-70b-versatile"
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
    
    provider, client, model_name = configurar_cliente()
    
    # Status
    if provider == "groq":
        st.caption(f"🟢 **Conectado:** Llama 3.3 (Groq) | ⚡ Ultra Rápido")
    elif provider == "gemini":
        st.caption(f"🔵 **Conectado:** Gemini 2.0 (Google) | 🧠 Alta Precisão")
    else:
        st.warning("⚠️ Modo Offline (Sem chaves configuradas).")
        st.caption("Adicione `GROQ_API_KEY` ou `GEMINI_KEY` aos segredos.")

    # Histórico
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
        welcome_msg = "Olá, Doutor(a)! Sou seu preceptor virtual. Posso criar mnemônicos, explicar fisiopatologia ou discutir casos clínicos. Qual o foco de hoje?"
        st.session_state.chat_history.append({"role": "assistant", "content": welcome_msg})

    for msg in st.session_state.chat_history:
        avatar = "🤖" if msg["role"] == "assistant" else "👨‍⚕️"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # Input
    if prompt := st.chat_input("Ex: Diferença entre Síndrome Nefrítica e Nefrótica..."):
        
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👨‍⚕️"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🤖"):
            message_placeholder = st.empty()
            full_response = ""
            
            if client:
                try:
                    # --- LÓGICA GROQ (Llama 3.3) ---
                    if provider == "groq":
                        messages = [
                            {"role": "system", "content": "Você é um mentor experiente de residência médica no Brasil. Responda de forma didática, direta e focada em provas (R1/R3). Use negrito para conceitos chave e cite guidelines recentes (SBC, SBP, FEBRASGO)."},
                        ]
                        for m in st.session_state.chat_history:
                            role = "assistant" if m["role"] == "assistant" else "user"
                            messages.append({"role": role, "content": m["content"]})
                        
                        stream = client.chat.completions.create(
                            model=model_name,
                            messages=messages,
                            stream=True,
                            temperature=0.6
                        )
                        
                        for chunk in stream:
                            if chunk.choices[0].delta.content:
                                content = chunk.choices[0].delta.content
                                full_response += content
                                message_placeholder.markdown(full_response + "▌")

                    # --- LÓGICA GEMINI ---
                    elif provider == "gemini":
                        gemini_history = []
                        for m in st.session_state.chat_history[:-1]:
                            role = "model" if m["role"] == "assistant" else "user"
                            gemini_history.append({"role": role, "parts": [m["content"]]})
                        
                        chat = client.start_chat(history=gemini_history)
                        response = chat.send_message(prompt, stream=True)
                        
                        for chunk in response:
                            if chunk.text:
                                full_response += chunk.text
                                message_placeholder.markdown(full_response + "▌")

                    message_placeholder.markdown(full_response)

                except Exception as e:
                    # Tratamento de Erro Robusto
                    error_msg = str(e).lower()
                    
                    # Erro de Cota ou Modelo Inválido (como o 400 que você recebeu)
                    if "400" in error_msg or "429" in error_msg or "model" in error_msg:
                        
                        # Tenta Fallback IMEDIATO para o Gemini se a Groq falhou
                        if provider == "groq" and GEMINI_KEY:
                            try:
                                genai.configure(api_key=GEMINI_KEY)
                                model_gemini = genai.GenerativeModel('gemini-2.0-flash')
                                # Recria contexto para Gemini
                                g_hist = []
                                for m in st.session_state.chat_history[:-1]:
                                    r = "model" if m["role"] == "assistant" else "user"
                                    g_hist.append({"role": r, "parts": [m["content"]]})
                                
                                chat = model_gemini.start_chat(history=g_hist)
                                res = chat.send_message(prompt)
                                full_response = f"*(Fallback para Gemini)*\n\n{res.text}"
                                message_placeholder.markdown(full_response)
                            except:
                                full_response = "⚠️ **Erro nos Provedores de IA.**\nAmbos os modelos (Groq e Gemini) estão indisponíveis no momento. Tente mais tarde."
                                message_placeholder.error(full_response)
                        else:
                            full_response = f"⚠️ **Erro na IA ({provider}):**\n{e}\n\nTente recarregar a página ou verifique as chaves."
                            message_placeholder.error(full_response)
                    else:
                        full_response = f"Erro técnico: {e}"
                        message_placeholder.error(full_response)
            else:
                time.sleep(1)
                full_response = "**[Modo Demo]** Configure uma API Key para respostas reais."
                message_placeholder.markdown(full_response)

        if full_response and "Erro técnico" not in full_response:
            st.session_state.chat_history.append({"role": "assistant", "content": full_response})