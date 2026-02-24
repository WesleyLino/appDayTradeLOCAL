import asyncio
import logging
import os
from backend.ai_core import AICore

import pytest

@pytest.mark.anyio
async def test_integration():
    logging.basicConfig(level=logging.INFO)
    print("Testing AICore Integration with Sentiment Feed...")
    
    ai = AICore()
    
    # Test reading from the newly generated JSON
    score = await ai.update_sentiment()
    print(f"✅ Score lido pelo AICore: {score}")
    
    if score != 0.0:
        print("🚀 Integração confirmada!")
    else:
        print("❌ Score ainda é 0.0. Verifique se o arquivo data/news_sentiment.json está correto.")

if __name__ == "__main__":
    asyncio.run(test_integration())
