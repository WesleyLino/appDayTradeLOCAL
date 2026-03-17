import sys
import os

# Adiciona o diretório atual ao sys.path para garantir que o backend seja importado corretamente
sys.path.append(os.getcwd())

from backend.ai_core import AICore

def verify():
    print("Iniciando verificação de AICore...")
    ai = AICore()
    
    methods = ["analyze", "calculate_wen_ofi", "calculate_decision"]
    for m in methods:
        if hasattr(ai, m):
            print(f"✅ Método '{m}' encontrado.")
        else:
            print(f"❌ Método '{m}' NÃO encontrado!")

    if hasattr(ai, "micro_analyzer"):
        print(f"✅ Atributo 'micro_analyzer' encontrado: {type(ai.micro_analyzer)}")
        if hasattr(ai.micro_analyzer, "analyze"):
            print("  ✅ micro_analyzer.analyze encontrado.")
        else:
            print("  ❌ micro_analyzer.analyze NÃO encontrado!")
    else:
        print("❌ Atributo 'micro_analyzer' NÃO encontrado!")

if __name__ == "__main__":
    verify()
