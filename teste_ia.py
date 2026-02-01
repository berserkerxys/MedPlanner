import google.generativeai as genai

# COLE SUA API KEY AQUI
API_KEY = "AIzaSyAfrZkELdk-SGPk6Ir7Om4owWZlFQq5uSo"
genai.configure(api_key=API_KEY)

print("Listando modelos disponíveis para você...")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"Erro na chave de API: {e}")