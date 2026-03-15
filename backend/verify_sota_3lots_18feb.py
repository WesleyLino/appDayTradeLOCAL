import asyncio
import json
import os
import sys
import pandas as pd
import logging
from datetime import datetime

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


class LeveragedBacktester(BacktestPro):
    async def load_data(self):
        logging.info(f"📥 Coletando dados de 18/02/2026 para {self.symbol}...")
        if not self.bridge.connect():
            return None

        import MetaTrader5 as mt5

        # Definir range para 18/02
        # Use copy_rates_from_range for precision
        utc_from = datetime(2026, 2, 18)
        utc_to = datetime(2026, 2, 18, 23, 59)

        rates = await asyncio.to_thread(
            mt5.copy_rates_range, self.symbol, mt5.TIMEFRAME_M1, utc_from, utc_to
        )
        if rates is None or len(rates) == 0:
            logging.error("❌ Falha na coleta de dados históricas para 18/02.")
            # Fallback para offset se range falhar (algumas corretoras tem delay no sync de range)
            logging.info("Tentando via offset (1200-1800)...")
            rates = await asyncio.to_thread(
                mt5.copy_rates_from_pos, self.symbol, mt5.TIMEFRAME_M1, 1200, 600
            )

        if rates is None or len(rates) == 0:
            return None

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)
        logging.info(
            f"✅ {len(df)} candles carregados (18/02). Primeiros dados: {df.index[0]}"
        )
        return df

    def _close_trade(self, price, reason, exit_time):
        pos = self.position
        pos["lots"] = 3  # Force 3 lots
        pnl_points = (
            (price - pos["entry_price"])
            if pos["side"] == "buy"
            else (pos["entry_price"] - price)
        )
        mult = 0.20  # WIN
        pnl_fin = pnl_points * pos["lots"] * mult
        self.balance += pnl_fin
        self.daily_pnl += pnl_fin
        self.trades.append(
            {
                "entry_time": pos["time"],
                "exit_time": exit_time,
                "side": pos["side"],
                "entry": pos["entry_price"],
                "exit": price,
                "lots": pos["lots"],
                "pnl_points": pnl_points,
                "pnl_fin": pnl_fin,
                "reason": reason,
            }
        )
        self.position = None


async def run_leveraged_18feb():
    print("📈 Iniciando Verificação 18/02: 3 Contratos / Cap R$ 1000")

    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        print(f"❌ Erro: {params_path} não encontrado.")
        return

    with open(params_path, "r") as f:
        config = json.load(f)
    params = config["params"]

    backtester = LeveragedBacktester(
        symbol="WIN$",
        n_candles=600,
        initial_balance=1000.0,
        use_trailing_stop=True,
        use_flux_filter=True,
        **params,
    )

    await backtester.run()

    # Detalhamento para análise
    if backtester.trades:
        print("\n--- DETALHAMENTO DE TRADES (18/02) ---")
        for i, trade in enumerate(backtester.trades):
            print(
                f"Trade {i + 1}: {trade['side'].upper()} em {trade['entry_time']} | Saída: {trade['exit_time']} | Pontos: {trade['pnl_points']:.1f} | R$ {trade['pnl_fin']:.2f} ({trade['reason']})"
            )
    else:
        print("\n⚠️ Nenhum trade realizado em 18/02 com os critérios Sniper.")


if __name__ == "__main__":
    asyncio.run(run_leveraged_18feb())
