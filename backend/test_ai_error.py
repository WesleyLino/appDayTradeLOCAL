import asyncio
from backend.ai_core import AICore
import pandas as pd
import numpy as np

async def test_ai_core():
    ai = AICore()
    # Mock data
    row = {
        'tick_volume': 1000,
        'vol_sma': 500,
        'close': 120000,
        'vwap': 120100,
        'obi': 2.5,
        'sentiment': 0.1,
        'regime': 1
    }
    
    # Test calculate_decision with scalars
    print("Testing calculate_decision...")
    decision = ai.calculate_decision(
        obi=row['obi'],
        sentiment=row['sentiment'],
        patchtst_score={'score': 0.9, 'confidence': 0.95},
        regime=row['regime'],
        hour=10,
        minute=15,
        current_vol=row['tick_volume'],
        avg_vol_20=row['vol_sma'],
        current_price=row['close'],
        vwap=row['vwap']
    )
    print(f"Decision: {decision}")
    print("Success!")

if __name__ == "__main__":
    asyncio.run(test_ai_core())
