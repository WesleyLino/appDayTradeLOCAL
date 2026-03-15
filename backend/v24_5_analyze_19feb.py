import asyncio
import logging
from backend.backtest_pro import BacktestPro


async def analyze_19feb_deep():
    # Desativa logging para limpar a saida
    logging.getLogger().setLevel(logging.ERROR)

    bt = BacktestPro(
        symbol="WIN$",
        n_candles=3000,
        data_file="data/audit_m1_20260219.csv",
        use_ai_core=True,
    )

    # Testar com o threshold planejado da v24.5 (58.0)
    bt.ai.confidence_buy_threshold = 58.0
    bt.ai.confidence_sell_threshold = 42.0

    await bt.load_data()
    summary = await bt.run()

    print("\n--- ANALISE 19/02 ---")
    print(f"PnL: {summary.get('net_profit')}")
    print(f"Trades: {summary.get('total_trades')}")
    print("Veto Reasons:")
    for reason, count in summary.get("veto_reasons", {}).items():
        print(f" - {reason}: {count}")

    # Se houver trades, imprimir detalhes
    if summary.get("trades"):
        print("\nLista de Trades:")
        for t in summary["trades"]:
            # Ajuste de chaves conforme a estrutura real do BacktestPro
            exit_time = t.get("exit_time", "N/A")
            print(
                f" - {t.get('entry_time')} -> {exit_time} | {t.get('side')} | PnL: {t.get('pnl')}"
            )


if __name__ == "__main__":
    asyncio.run(analyze_19feb_deep())
