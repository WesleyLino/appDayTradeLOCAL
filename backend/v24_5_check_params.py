import asyncio
from backend.backtest_pro import BacktestPro


async def check_params():
    bt = BacktestPro(symbol="WIN$", n_candles=3000, use_ai_core=True)
    print(f"DEBUG: Threshold Compra (AICore): {bt.ai.confidence_buy_threshold}")
    print(f"DEBUG: Threshold Venda (AICore): {bt.ai.confidence_sell_threshold}")
    print(f"DEBUG: Uncertainty Threshold: {bt.ai.uncertainty_threshold}")
    print(f"DEBUG: Min ATR Threshold: {bt.opt_params['min_atr_threshold']}")


if __name__ == "__main__":
    asyncio.run(check_params())
