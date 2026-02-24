"""
Test Script: Gemini 2.5 Flash Determinism Verification
Verifica se o modelo Gemini 2.5 Flash retorna sempre a mesma resposta.
"""

import asyncio
import logging
from backend.ai_core import AICore
import os

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def test_determinism():
    """Executa 3 consultas idênticas e verifica se os scores são iguais."""
    
    print("=" * 60)
    print("🧪 TESTE: Determinismo Gemini 2.5 Flash")
    print("=" * 60)
    
    # Criar notícia de teste
    news_file = "backend/news_feed.txt"
    test_headline = "Petrobras anuncia aumento de 15% nos dividendos. Ibovespa sobe 2%."
    
    with open(news_file, "w", encoding="utf-8") as f:
        f.write(test_headline)
    
    print(f"\n📰 Manchete de teste: {test_headline}")
    print("-" * 60)
    
    # Inicializar AICore (Gemini 2.5 Flash com temperature=0.0)
    ai = AICore()
    
    if not ai.model:
        print("❌ ERRO: GOOGLE_API_KEY não configurada no .env")
        return
    
    scores = []
    reasons = []
    
    # Executar 3 consultas
    for i in range(1, 4):
        print(f"\n🔄 Execução {i}/3...")
        ai.last_news_update = 0  # Forçar atualização
        score = await ai.update_sentiment()
        
        # Capturar razão (se disponível)
        reason = "N/A"  # Por enquanto, só logamos o score
        
        scores.append(score)
        reasons.append(reason)
        
        print(f"   Score: {score:.4f}")
        await asyncio.sleep(1)  # Pequena pausa entre chamadas
    
    # Verificar determinismo
    print("\n" + "=" * 60)
    print("📊 RESULTADOS")
    print("=" * 60)
    
    for i, (score, reason) in enumerate(zip(scores, reasons), 1):
        print(f"Execução {i}: Score = {score:.4f}")
    
    # Checar se todos os scores são idênticos
    if scores[0] == scores[1] == scores[2]:
        print("\n✅ TESTE PASSOU: Respostas são DETERMINÍSTICAS!")
        print(f"   (Todas as execuções retornaram: {scores[0]:.4f})")
    else:
        print("\n❌ TESTE FALHOU: Respostas NÃO são DETERMINÍSTICAS!")
        print(f"   Variação detectada: {scores}")
        print("   ⚠️ Verifique se temperature=0.0 está configurado corretamente.")
    
    # Limpar arquivo de teste
    if os.path.exists(news_file):
        os.remove(news_file)
        print("\n🧹 Arquivo de teste removido.")

if __name__ == "__main__":
    asyncio.run(test_determinism())
