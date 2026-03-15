import asyncio
import os
import json
import logging
from backend.news_sentiment_worker import NewsSentimentWorker


async def test_worker():
    logging.basicConfig(level=logging.INFO)
    print("Iniciando Teste de Sentimento...")
    worker = NewsSentimentWorker()
    await worker.analyze_sentiment()

    if os.path.exists(worker.output_path):
        with open(worker.output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            print("--- RESULTADO DO TESTE ---")
            print(f"Score: {data.get('score')}")
            print(f"Risco: {data.get('risk_classification')}")
            print(f"Timestamp: {data.get('timestamp')}")
            print("--------------------------")
    else:
        print("ERRO: Arquivo de sentimento não gerado.")


if __name__ == "__main__":
    asyncio.run(test_worker())
