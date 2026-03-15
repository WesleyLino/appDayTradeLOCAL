import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

model = genai.GenerativeModel("gemini-1.5-flash")

try:
    print("Testando conexão com Gemini...")
    response = model.generate_content("Diga OK em português se estiver funcionando.")
    print(f"Resposta: {response.text}")
except Exception as e:
    print(f"Erro: {e}")
