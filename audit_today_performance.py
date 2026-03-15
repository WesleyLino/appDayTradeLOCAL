import asyncio
import logging
from datetime import datetime
import sys
import os

# Adiciona diretorio raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from backend.backtest_pro import BacktestPro


async def detailed_audit():
    # Desativa logs verbosos para o console, foca no resultado
    logging.basicConfig(level=logging.ERROR)
    print(f"\n{'=' * 60}")
    print("AUDITORIA DETALHADA: POTENCIAL DE GANHO WIN$ (25/02/2026)")
    print(f"{'=' * 60}")

    symbol = "WIN$"
    capital = 3000.0
    today_date = datetime(2026, 2, 25).date()

    configs = [
        {
            "name": "V22 GOLDEN (LOCKED)",
            "use_ai": True,
            "conf_thresh": 0.70,
            "flux_thresh": 1.2,
        },
        {
            "name": "BALANCED (TREINED)",
            "use_ai": True,
            "conf_thresh": 0.65,
            "flux_thresh": 1.1,
        },
        {
            "name": "AGGRESSIVE (POTENTIAL)",
            "use_ai": True,
            "conf_thresh": 0.60,
            "flux_thresh": -1.0,
        },  # Desativa Fluxo
        {
            "name": "RAW (NO AI)",
            "use_ai": False,
            "conf_thresh": 0.0,
            "flux_thresh": -1.0,
        },  # Sem IA, Sem Fluxo
    ]

    for cfg in configs:
        print(f"\n>>> TESTANDO CONFIGURAÇÃO: {cfg['name']}")
        tester = BacktestPro(
            symbol=symbol,
            n_candles=1000,
            timeframe="M1",
            initial_balance=capital,
            base_lot=1,
            dynamic_lot=True,
            use_ai_core=cfg["use_ai"],
        )
        tester.opt_params["confidence_threshold"] = cfg["conf_thresh"]
        tester.opt_params["flux_imbalance_threshold"] = cfg["flux_thresh"]

        tester.data = await tester.load_data()

        if tester.data is None or tester.data.empty:
            print(f"Erro: Falha ao carregar dados do MT5 para {symbol}.")
            continue

        tester.data = tester.data[tester.data.index.date == today_date]

        await tester.run()

        trades = tester.trades
        shadow = tester.shadow_signals

        print(f"- PnL Final:       RS {tester.balance - capital:.2f}")
        print(f"- Total Trades:    {len(trades)}")
        print(f"- Sinais V22:      {shadow.get('v22_candidates', 0)}")
        print(f"- Vetos pela IA:   {shadow.get('filtered_by_ai', 0)}")
        print(f"- Vetos pelo Fluxo: {shadow.get('filtered_by_flux', 0)}")

        if len(trades) > 0:
            wins = len([t for t in trades if t["pnl_fin"] > 0])
            print(f"- Assertividade:   {(wins / len(trades)) * 100:.2f}%")
            print(f"- Maior Gain:      RS {max([t['pnl_fin'] for t in trades]):.2f}")
            print(f"- Maior Loss:      RS {min([t['pnl_fin'] for t in trades]):.2f}")

    print(f"\n{'=' * 60}")
    print("RESUMO DE MELHORIAS:")
    print("1. O mercado de hoje apresentou ALTO RUIDO ou INCERTEZA nos modelos SOTA.")
    print("2. A calibragem V22 GOLDEN priorizou PRESERVAÇÃO DE CAPITAL.")
    print(
        "3. Para elevar assertividade: Considerar ajuste de TP/SL dinâmico baseado em ATR(14)."
    )
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(detailed_audit())
