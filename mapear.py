import asyncio
from telethon import TelegramClient
from database import registrar_topico_do_sumario
import re

# --- SEUS DADOS ---
api_id = 34900101
api_hash = 'f29c772956f0b148c4a654a66952e5ff'
session_name = 'sessao_medplanner'
chat_target = -1003727607215

# FORMATADOR DE NOME (CamelCase -> Espaços)
def formatar_nome(texto):
    texto = texto.replace("#", "").replace("_", " ").replace("🔹", "").strip()
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', texto).strip()

async def main():
    print("🗺️  MAPEADOR DE EDITAL TELEGRAM")
    print("Este script lê a mensagem de índice e cria a estrutura no banco.")
    
    msg_id = input("\nDigite o ID da mensagem que contém o Índice (Sumário): ")
    
    if not msg_id.isdigit():
        print("❌ ID inválido.")
        return

    async with TelegramClient(session_name, api_id, api_hash) as client:
        print("🔄 Lendo mensagem...")
        try:
            message = await client.get_messages(chat_target, ids=int(msg_id))
            texto = message.text
            
            if not texto:
                print("❌ Mensagem sem texto ou não encontrada.")
                return

            print("\n--- Processando Texto ---")
            
            # 1. Tenta identificar a GRANDE ÁREA no texto (ex: "ÁREA: PREVENTIVA")
            area_detectada = "Geral"
            match_area = re.search(r'ÁREA:\s*([A-ZÀ-Ú\s]+)', texto, re.IGNORECASE)
            
            if match_area:
                # Limpa o nome da área (pega a primeira palavra chave)
                raw_area = match_area.group(1).upper()
                if "CIRURGIA" in raw_area: area_detectada = "Cirurgia"
                elif "CLINICA" in raw_area or "CLÍNICA" in raw_area: area_detectada = "Clínica Médica"
                elif "PEDIATRIA" in raw_area: area_detectada = "Pediatria"
                elif "PREVENTIVA" in raw_area: area_detectada = "Preventiva"
                elif "GO" in raw_area or "GINECO" in raw_area: area_detectada = "G.O."
                elif "NEURO" in raw_area: area_detectada = "NeuroPed"
                
                print(f"📍 Área Identificada: {area_detectada}")
            else:
                # Se não achar no texto, pergunta pro usuário
                print(f"⚠️ Não achei 'ÁREA: X' no texto.")
                opcoes = ["Cirurgia", "Clínica Médica", "Pediatria", "G.O.", "Preventiva", "NeuroPed"]
                print(f"Opções: {opcoes}")
                idx = int(input("Digite o índice da área (0 a 5): "))
                area_detectada = opcoes[idx]

            # 2. Extrai as Hashtags (Tópicos)
            # Procura linhas com 🔹 e #
            linhas = texto.split('\n')
            count = 0
            
            for linha in linhas:
                # Regex para pegar a hashtag
                match_tag = re.search(r'#(\w+)', linha)
                if match_tag:
                    raw_tag = match_tag.group(1)
                    
                    # Ignora a hashtag da própria área (ex: #Preventiva)
                    if raw_tag.lower() in area_detectada.lower().replace(" ","").replace(".",""):
                        continue
                        
                    nome_bonito = formatar_nome(raw_tag)
                    
                    # Salva no Banco
                    res = registrar_topico_do_sumario(area_detectada, nome_bonito)
                    print(res)
                    count += 1
            
            print(f"\n✅ Concluído! {count} tópicos mapeados em {area_detectada}.")
            
        except Exception as e:
            print(f"❌ Erro: {e}")

if __name__ == '__main__':
    asyncio.run(main())