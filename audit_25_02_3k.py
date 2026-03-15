import asyncio
import logging
from datetime import datetime
from backend.mt5_bridge import MT5Bridge
from backend.backtest_pro import BacktestPro
import MetaTrader5 as mt5

# Configuração de Logs reduzida para clareza no terminal
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def run_audit():
    bridge = MT5Bridge()
    if not bridge.connect():
        print("❌ ERRO: Falha ao conectar ao Terminal MetaTrader 5.")
        return

    # Data de Hoje: 25/02/2026
    today = datetime(2026, 2, 25)
    symbol = "WIN$N"
    date_from = today.replace(hour=8, minute=0, second=0)
    date_to = today.replace(hour=18, minute=30, second=0)

    print("\n" + "=" * 60)
    print("📊 AUDITORIA ESPECIAL: 25/02/2026 | CAPITAL: R$ 3.000,00")
    print("=" * 60)

    # Coleta de dados única para ambos os backtests
    print(f"📥 Coletando dados históricos M1 para {symbol}...")
    data = bridge.get_market_data_range(symbol, mt5.TIMEFRAME_M1, date_from, date_to)

    if data is None or data.empty:
        print("❌ ERRO: Não foi possível obter dados para o período solicitado.")
        bridge.disconnect()
        return

    # 1. Configuração LEGACY (RAW)
    print("\n[TESTE 1/2] 🤖 MODO: LEGACY V22 (RAW - No AI)")
    back_legacy = BacktestPro(symbol=symbol, initial_balance=3000.0, use_ai_core=False)
    back_legacy.data = data.copy()
    results_legacy = await back_legacy.run()

    # 2. Configuração SOTA V2 (REFINED AI)
    print("\n[TESTE 2/2] 🚀 MODO: SOTA V2 (REFINED AI - Weighted Uncertainty)")
    back_sota = BacktestPro(symbol=symbol, initial_balance=3000.0, use_ai_core=True)
    back_sota.data = data.copy()
    results_sota = await back_sota.run()

    # COMPARATIVO FINAL
    print("\n" + "=" * 60)
    print("🏆 COMPARATIVO FINAL: 25/02 (WIN$)")
    print("-" * 60)
    pnl_legacy = results_legacy["total_pnl"] if results_legacy else 0
    pnl_sota = results_sota["total_pnl"] if results_sota else 0

    print(f"PNL LEGACY V22: R$ {pnl_legacy:>10.2f}")
    print(f"PNL SOTA V2 AI: R$ {pnl_sota:>10.2f}")
    print(f"DELTA MELHORIA: R$ {pnl_sota - pnl_legacy:>10.2f}")
    print("=" * 60)

    bridge.disconnect()


if __name__ == "__main__":
    asyncio.run(run_audit())
