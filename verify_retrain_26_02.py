import asyncio
import logging
import pandas as pd
from datetime import datetime
from backend.mt5_bridge import MT5Bridge
from backend.backtest_pro import BacktestPro

# Configuração de Logs para Verificação
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def run_audit_26_02():
    bridge = MT5Bridge()
    if not bridge.connect():
        print("❌ ERRO: Falha ao conectar ao Terminal MetaTrader 5.")
        return

    # Data de Hoje: 26/02/2026
    today = datetime(2026, 2, 26)
    symbol = "WIN$N"
    date_from = today.replace(hour=9, minute=0, second=0)
    date_to = today.replace(hour=18, minute=30, second=0)

    print("\n" + "=" * 60)
    print("📊 VALIDAÇÃO SOTA v3.1: 26/02/2026 | CAPITAL: R$ 3.000,00")
    print("=" * 60)

    # Coleta de dados via CSV MASTER (Garante dados de 26/02 sem depender do terminal MT5)
    print(f"📥 Carregando dados históricos do CSV MASTER para {symbol}...")
    try:
        import glob

        master_file = glob.glob("data/sota_training/training_WIN*_MASTER.csv")[0]
        full_df = pd.read_csv(master_file)
        full_df["time"] = pd.to_datetime(full_df["time"])

        # Filtrar para o dia de hoje (26/02/2026)
        mask = (full_df["time"] >= date_from) & (full_df["time"] <= date_to)
        data = full_df.loc[mask].copy()
        data.set_index("time", inplace=True)
    except Exception as e:
        print(f"❌ ERRO ao carregar CSV: {e}")
        bridge.disconnect()
        return

    if data is None or data.empty:
        print("❌ ERRO: Não foi possível obter dados para o período solicitado.")
        bridge.disconnect()
        return

    # 1. Configuração LEGACY (SEM IA)
    print("\n[TESTE 1/2] 🤖 MODO: LEGACY V22 (No AI)")
    back_legacy = BacktestPro(symbol=symbol, initial_balance=3000.0, use_ai_core=False)
    back_legacy.data = data.copy()
    results_legacy = await back_legacy.run()

    # 2. Configuração SOTA v3.1 (NEW AI)
    print("\n[TESTE 2/2] 🚀 MODO: SOTA v3.1 (NEW RETRAINED AI)")
    back_sota = BacktestPro(symbol=symbol, initial_balance=3000.0, use_ai_core=True)
    back_sota.data = data.copy()
    results_sota = await back_sota.run()

    print("\n" + "=" * 60)
    print("🏆 RESULTADO PÓS-RETREINO: 26/02 (WIN$)")
    print("-" * 60)
    pnl_legacy = results_legacy["total_pnl"] if results_legacy else 0
    pnl_sota = results_sota["total_pnl"] if results_sota else 0
    trades_legacy = (
        len(results_legacy["trades"])
        if results_legacy and "trades" in results_legacy
        else 0
    )
    trades_sota = (
        len(results_sota["trades"]) if results_sota and "trades" in results_sota else 0
    )

    print(f"PNL LEGACY V22: R$ {pnl_legacy:>10.2f} ({trades_legacy} trades)")
    print(f"PNL SOTA v3.1:  R$ {pnl_sota:>10.2f} ({trades_sota} trades)")
    print(f"MELHORIA AI:    R$ {pnl_sota - pnl_legacy:>10.2f}")
    print("=" * 60)

    bridge.disconnect()


if __name__ == "__main__":
    asyncio.run(run_audit_26_02())
