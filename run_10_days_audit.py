import sys
import asyncio
from datetime import datetime
import pandas as pd
import logging

sys.path.append(".")
# Suprimindo logs excessivos
logging.getLogger().setLevel(logging.ERROR)

from backend.mt5_bridge import MT5Bridge
from backend.backtest_pro import BacktestPro


async def run_audit():
    bridge = MT5Bridge()
    if not bridge.connect():
        print("Erro ao conectar no MT5")
        return

    # Formato: (Ano, Mês, Dia)
    target_dates = [
        (2026, 2, 19),
        (2026, 2, 20),
        (2026, 2, 23),
        (2026, 2, 24),
        (2026, 2, 25),
        (2026, 2, 26),
        (2026, 2, 27),
        (2026, 2, 28),
        (2026, 3, 2),
        (2026, 3, 3),
    ]

    print("=== AUDITORIA DE 10 DIAS (M1) - R$ 3000 INICIAIS | CALIBRAGEM v52.4 ===")
    print(
        f"{'Data':<12} | {'Win Rate':<8} | {'Trades':<6} | {'(C/V)':<7} | {'PnL BRL':<10} | {'Missed':<6}"
    )
    print("-" * 65)

    total_pnl = 0.0
    total_trades = 0
    total_wins = 0

    for year, month, day in target_dates:
        start_dt = datetime(year, month, day, 8, 55, 0)
        end_dt = datetime(year, month, day, 18, 5, 0)

        rates = bridge.mt5.copy_rates_range(
            "WINJ26", bridge.mt5.TIMEFRAME_M1, start_dt, end_dt
        )

        if rates is None or len(rates) == 0:
            print(
                f"{day:02d}/{month:02d}/{year}   | SEM DADOS (Final de Semana/Feriado/Missing)"
            )
            continue

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)

        bt = BacktestPro(symbol="WINJ26", initial_balance=3000.0)
        bt.data_file = None
        bt._bias_day = None  # reset diário rigoroso
        bt.data = df

        try:
            await bt.run()
        except Exception as e:
            print(f"{day:02d}/{month:02d}/{year}   | ERRO DE EXECUÇÃO: {e}")
            continue

        # Resultados
        trades_count = len(bt.trades)
        wins = sum(1 for t in bt.trades if t.get("profit", 0) > 0)
        wr = (wins / trades_count * 100) if trades_count > 0 else 0.0

        buys = sum(1 for t in bt.trades if t.get("side") == "buy")
        sells = sum(1 for t in bt.trades if t.get("side") == "sell")

        missed = bt.shadow_signals.get("total_missed", 0)

        pnl = bt.balance - 3000.0

        total_pnl += pnl
        total_trades += trades_count
        total_wins += wins

        c_pnl = f"R$ {pnl:+.2f}"
        cv_str = f"{buys}/{sells}"

        print(
            f"{day:02d}/{month:02d}/{year}   | {wr:>5.1f}%   | {trades_count:<6} | {cv_str:<7} | {c_pnl:<10} | {missed:<6}"
        )

    print("-" * 65)
    global_wr = (total_wins / total_trades * 100) if total_trades > 0 else 0.0
    print(
        f"RESULTADO FINAL: {total_trades} trades | WinRate: {global_wr:.1f}% | PnL Total: R$ {total_pnl:+.2f}"
    )

    bridge.disconnect()


if __name__ == "__main__":
    asyncio.run(run_audit())
