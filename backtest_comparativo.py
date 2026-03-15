import asyncio
import MetaTrader5 as mt5
from datetime import datetime
import os
import sys

sys.path.insert(0, os.getcwd())
from backend.mt5_bridge import MT5Bridge
from backend.backtest_pro import BacktestPro


async def run_comparison():
    bridge = MT5Bridge()
    if not bridge.connect():
        return

    symbol = "WIN$N"
    dias = [
        datetime(2026, 2, 19),
        datetime(2026, 2, 20),
        datetime(2026, 2, 23),
        datetime(2026, 2, 24),
        datetime(2026, 2, 25),
        datetime(2026, 2, 26),
        datetime(2026, 2, 27),
        datetime(2026, 3, 2),
    ]

    print("=" * 85)
    print("  RELATÓRIO DE POTENCIAL E SENSIBILIDADE SOTA (v30/v40)")
    print("=" * 85)

    for dia in dias:
        date_str = dia.strftime("%d/%m/%Y")
        data = bridge.get_market_data_range(
            symbol,
            mt5.TIMEFRAME_M1,
            dia.replace(hour=7, minute=0),
            dia.replace(hour=17, minute=45),
        )
        if data is None or data.empty:
            continue

        # Teste 1: Rigor Institucional (93%)
        bt_93 = BacktestPro(symbol=symbol, confidence_threshold=0.93, base_lot=2)
        bt_93.data = data.copy()
        bt_93.ai.latest_sentiment_score = 0.4  # Simula um viés leve
        res_93 = await bt_93.run()

        # Teste 2: Alpha Agressivo (82%) - Calibração para ver "Potencial"
        bt_82 = BacktestPro(symbol=symbol, confidence_threshold=0.82, base_lot=2)
        bt_82.data = data.copy()
        bt_82.ai.latest_sentiment_score = 0.4
        res_82 = await bt_82.run()

        pnl_93 = res_93.get("total_pnl", 0)
        pnl_82 = res_82.get("total_pnl", 0)

        cands = res_82.get("shadow_signals", {}).get("v22_candidates", 0)

        print(
            f"  [{date_str}] Cands: {cands:>2} | Trades (93%): {len(res_93.get('trades', []))} [PnL: R${pnl_93:>7.2f}] | Trades (82%): {len(res_82.get('trades', []))} [PnL: R${pnl_82:>7.2f}]"
        )

    bridge.disconnect()


if __name__ == "__main__":
    asyncio.run(run_comparison())
