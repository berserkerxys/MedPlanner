import telebot
from database import get_status_gamer, ler_config, gerar_missoes_do_dia
import sys

# Força a geração de missões do dia (caso você não tenha aberto o app ainda)
gerar_missoes_do_dia()

def enviar_aviso_telegram():
    print("🤖 Iniciando Bot de Aviso...")
    
    # 1. Recupera Configs
    token = ler_config("telegram_token")
    chat_id = ler_config("telegram_chat_id")
    
    if not token or not chat_id:
        print("❌ Erro: Token ou Chat ID não configurados no App (Aba Ajustes).")
        return

    # 2. Pega Dados do Jogador
    perfil, missoes = get_status_gamer()
    nivel = perfil['nivel']
    titulo = perfil['titulo']
    
    bot = telebot.TeleBot(token)
    
    # 3. Monta a Mensagem Motivacional/Cobrança
    msg = f"🌅 **BOM DIA, {titulo.upper()}!**\n"
    msg += f"🏅 Nível Atual: {nivel}\n"
    msg += f"⚡ XP Acumulado: {perfil['xp_total']}\n\n"
    
    msg += "📋 **SUA MISSÃO DE HOJE:**\n"
    msg += "--------------------------------\n"
    
    total_xp_dia = 0
    for _, row in missoes.iterrows():
        status = "✅" if row['concluida'] else "🔲"
        msg += f"{status} **{row['descricao']}**\n"
        msg += f"   ╚ 🎯 Meta: {row['meta_valor']} | ✨ XP: {row['xp_recompensa']}\n\n"
        total_xp_dia += row['xp_recompensa']
        
    msg += "--------------------------------\n"
    msg += f"💰 XP Total em jogo: {total_xp_dia}\n"
    msg += "Vá estudar. A residência não espera! 🚀"
    
    # 4. Envia
    try:
        bot.send_message(chat_id, msg, parse_mode="Markdown")
        print(f"✅ Mensagem enviada para {titulo}!")
    except Exception as e:
        print(f"❌ Erro ao enviar: {e}")

if __name__ == "__main__":
    enviar_aviso_telegram()