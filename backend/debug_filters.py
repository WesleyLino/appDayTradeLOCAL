import asyncio
import logging
from datetime import datetime
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.backtest_pro import BacktestPro


async def run_detailed_audit():
    logging.basicConfig(level=logging.ERROR)  # Silenciar avisos menores

    symbol = "WIN$"
    capital_inicial = 3000.0
    timeframe = "M1"

    # 19/02 é o dia que sabemos que tem 385 candidatos
    target_date = datetime(2026, 2, 19).date()

    logging.error(f"🔍 DEBUG: ANALISANDO BLOQUEIOS EM {target_date}")

    tester = BacktestPro(
        symbol=symbol,
        n_candles=10000,
        timeframe=timeframe,
        initial_balance=capital_inicial,
        use_ai_core=True,
    )
    full_data = await tester.load_data()

    if full_data is None or full_data.empty:
        return

    mask = full_data.index.date <= target_date
    tester.data = full_data[mask].tail(2000)

    # Parâmetros Relaxados para Auditoria
    tester.opt_params["confidence_threshold"] = 0.50
    tester.opt_params["use_flux_filter"] = False
    tester.opt_params["start_time"] = "09:00"
    tester.opt_params["end_time"] = "18:00"

    await tester.run()

    shadow = tester.shadow_signals
    print("\n" + "=" * 50)
    print(f"DIAGNÓSTICO DE SINAIS - {target_date}")
    print(f"Candidatos V22: {shadow.get('v22_candidates', 0)}")
    print(f"Trades Efetuados: {len(tester.trades)}")
    print(f"Bloqueios por Componente: {shadow.get('component_fail', {})}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    asyncio.run(run_detailed_audit())
