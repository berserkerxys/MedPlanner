import telebot
import time
from datetime import datetime
from database import ler_config, get_progresso_hoje

# Variável para garantir que ele não mande 50 mensagens no mesmo minuto
ultimo_dia_envio = None

print("🤖 Bot MedPlanner: MODO VIGILANTE ATIVADO!")
print("👀 Estou verificando o banco de dados a cada 10 segundos...")

def enviar_mensagem():
    global ultimo_dia_envio
    
    # 1. Carrega dados frescos do banco
    token = ler_config("telegram_token")
    chat_id = ler_config("telegram_chat_id")
    meta_str = ler_config("meta_diaria")
    
    if not token or not chat_id:
        print("⚠️ Bot sem Token/ID configurado.")
        return

    try:
        bot = telebot.TeleBot(token)
        meta = int(meta_str) if meta_str else 50
        feitas = get_progresso_hoje()
        faltam = meta - feitas
        
        # Monta a mensagem
        if feitas >= meta:
            msg = f"🏆 **Meta Batida!**\n\nVocê fez {feitas}/{meta} questões hoje.\nParabéns pela constância! 🚀"
        elif feitas > 0:
            msg = f"⚠️ **Falta Pouco!**\n\nVocê fez {feitas} questões.\nFaltam **{faltam}** para a meta de {meta}. Vamos lá! 💪"
        else:
            msg = f"🚨 **ALERTA ZERO**\n\nVocê não fez questões hoje!\nSua meta é {meta}. Abra o app agora! 😡"

        # Envia
        bot.send_message(chat_id, msg, parse_mode="Markdown")
        print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Mensagem enviada com sucesso!")
        
        # Marca que hoje já enviamos
        ultimo_dia_envio = datetime.now().date()
        
    except Exception as e:
        print(f"❌ Erro ao enviar: {e}")

# --- LOOP INFINITO (O CORAÇÃO DO ROBÔ) ---
while True:
    try:
        # 1. Que horas são agora?
        agora = datetime.now()
        hora_atual = agora.strftime("%H:%M")
        
        # 2. Que horas o usuário quer? (Lê do banco AGORA)
        hora_alvo_str = ler_config("hora_lembrete") # Vem como "19:00:00" ou "19:00"
        
        if hora_alvo_str:
            # Pega só os 5 primeiros caracteres (HH:MM) para garantir a comparação
            hora_alvo = hora_alvo_str[:5] 
            
            # 3. É a hora certa?
            if hora_atual == hora_alvo:
                # Já mandei mensagem hoje?
                if ultimo_dia_envio != agora.date():
                    print(f"⏰ Hora batida ({hora_atual})! Enviando lembrete...")
                    enviar_mensagem()
                else:
                    # Já enviou hoje, só espera o minuto passar para não flodar
                    pass
            else:
                # Opcional: Mostra no terminal que está vivo (pode comentar se quiser)
                # print(f"⏳ Aguardando... Agora: {hora_atual} | Alvo: {hora_alvo}")
                pass
        
        # Dorme 10 segundos e verifica de novo
        time.sleep(10)

    except KeyboardInterrupt:
        print("\n🛑 Bot desligado pelo usuário.")
        break
    except Exception as e:
        print(f"❌ Erro no loop: {e}")
        time.sleep(10)