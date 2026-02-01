import asyncio
from telethon import TelegramClient
from database import salvar_conteudo_exato, exportar_videoteca_para_arquivo
import re

# --- DADOS ---
api_id = 34900101
api_hash = 'f29c772956f0b148c4a654a66952e5ff'
session_name = 'sessao_medplanner'
chat_target = -1003727607215  # CORRIGIDO: Número inteiro direto

hashtag_pattern = re.compile(r"#(\w+)")
album_cache = {}

async def main():
    print(f"🚀 Iniciando Sync...")
    
    async with TelegramClient(session_name, api_id, api_hash) as client:
        print("✅ Conectado! Varrendo...")
        
        count_ok = 0
        
        async for message in client.iter_messages(chat_target, limit=None, reverse=True):
            texto = message.text or ""
            if not texto and message.grouped_id: texto = album_cache.get(message.grouped_id, "")
            if texto and message.grouped_id: album_cache[message.grouped_id] = texto
            
            match = hashtag_pattern.search(texto)
            if not match: continue 
            
            hashtag = match.group(1)
            msg_id = message.id
            clean_id = str(chat_target).replace("-100", "")
            link = f"https://t.me/c/{clean_id}/{msg_id}"
            titulo = texto.replace(f"#{hashtag}", "").strip().split("\n")[0]
            if len(titulo) < 3: titulo = f"Aula {msg_id}"

            tipo = "Video" if message.video else "Material"
            subtipo = ""
            if message.video:
                dur = message.file.duration or 0
                subtipo = "Curto" if dur < 900 else "Longo"
            elif message.document:
                name = (message.file.name or "").lower()
                if "pdf" not in name: continue
                subtipo = "Ficha" if "ficha" in name else "Slide"

            res = salvar_conteudo_exato(msg_id, titulo, link, hashtag, tipo, subtipo)
            if "✅" in res:
                print(f"[{msg_id}] {res}")
                count_ok += 1

        print(f"\n✨ Sincronização Finalizada! {count_ok} novos itens.")
        exportar_videoteca_para_arquivo()

if __name__ == '__main__':
    asyncio.run(main())