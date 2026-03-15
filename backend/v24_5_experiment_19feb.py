import asyncio
import logging
from backend.backtest_pro import BacktestPro


async def run_experiment():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("\n🧪 EXPERIMENTO COMPARATIVO: 19/02/2026")

    # 1. Teste com Threshold 58.0 (v24.5 Planejado)
    print("\n--- Testando Threshold 58.0 (v24.5 Baseline) ---")
    bt_v24_5 = BacktestPro(
        symbol="WIN$",
        n_candles=3000,
        data_file="data/audit_m1_20260219.csv",
        use_ai_core=True,
    )
    bt_v24_5.ai.confidence_buy_threshold = 58.0
    bt_v24_5.ai.confidence_sell_threshold = 42.0
    await bt_v24_5.load_data()
    res_58 = await bt_v24_5.run()
    print(
        f"Resultado 58.0: R$ {res_58.get('net_profit', 0):.2f} | Trades: {res_58.get('total_trades', 0)}"
    )

    # 2. Teste com Threshold 52.0 (Legacy v24.4.1)
    print("\n--- Testando Threshold 52.0 (Legacy v24.4.1) ---")
    bt_legacy = BacktestPro(
        symbol="WIN$",
        n_candles=3000,
        data_file="data/audit_m1_20260219.csv",
        use_ai_core=True,
    )
    bt_legacy.ai.confidence_buy_threshold = 52.0
    bt_legacy.ai.confidence_sell_threshold = 48.0
    await bt_legacy.load_data()
    res_52 = await bt_legacy.run()
    print(
        f"Resultado 52.0: R$ {res_52.get('net_profit', 0):.2f} | Trades: {res_52.get('total_trades', 0)}"
    )


if __name__ == "__main__":
    asyncio.run(run_experiment())
