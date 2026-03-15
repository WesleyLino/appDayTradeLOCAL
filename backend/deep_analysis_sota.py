import asyncio
import json
import os
import sys
from datetime import datetime, timedelta

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


class DeepAnalyzer(BacktestPro):
    async def run_with_diagnostics(self):
        data = await self.load_data()
        if data is None:
            return

        # Pre-calculations (copied from BacktestPro.run for consistency)
        rsi_p = self.opt_params["rsi_period"]
        delta = data["close"].diff().fillna(0)
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_p).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_p).mean()
        rs = gain / (loss + 1e-6)
        data["rsi"] = 100 - (100 / (1 + rs))
        data["sma_20"] = data["close"].rolling(window=20).mean()
        data["vol_sma"] = data["tick_volume"].rolling(window=20).mean()
        data["upper_bb"] = (
            data["sma_20"]
            + self.opt_params["bb_dev"] * data["close"].rolling(window=20).std()
        )
        data["lower_bb"] = (
            data["sma_20"]
            - self.opt_params["bb_dev"] * data["close"].rolling(window=20).std()
        )

        # Simplified signals for diagnostics
        lookback = 60
        diagnostics = []

        for i in range(lookback, len(data)):
            row = data.iloc[i]

            # Reset diário
            current_date = row.name.date()
            if self.last_day and current_date != self.last_day:
                self.daily_pnl = 0.0
                self.daily_trade_count = 0
            self.last_day = current_date

            if self.position:
                exit_type, exit_price = self.simulate_oco(row, self.position)
                if exit_type:
                    self._close_trade(exit_price, exit_type, row.name)
                    self.last_trade_time = row.name
                elif i - self.position["index"] > 25:
                    self._close_trade(row["close"], "TIME", row.name)
                    self.last_trade_time = row.name

            if not self.position:
                # Basic Signal (RSI + Vol)
                v_mult = self.opt_params["vol_spike_mult"]
                vol_spike = row["tick_volume"] > (row["vol_sma"] * v_mult)
                rsi_buy = row["rsi"] < 30
                rsi_sell = row["rsi"] > 70

                technical_signal = (rsi_buy or rsi_sell) and vol_spike

                if technical_signal:
                    side = "buy" if rsi_buy else "sell"
                    # Check Filters
                    t_start = datetime.strptime(
                        self.opt_params["start_time"], "%H:%M"
                    ).time()
                    t_end = datetime.strptime(
                        self.opt_params["end_time"], "%H:%M"
                    ).time()
                    time_ok = t_start <= row.name.time() <= t_end

                    cooldown_ok = (row.name - self.last_trade_time) >= timedelta(
                        minutes=15
                    )
                    limit_ok = (
                        self.daily_trade_count < self.opt_params["daily_trade_limit"]
                    )

                    rejection_reason = None
                    if not time_ok:
                        rejection_reason = "FORA DA JANELA"
                    elif not limit_ok:
                        rejection_reason = "LIMITE DIARIO EXCEDIDO"
                    elif not cooldown_ok:
                        rejection_reason = "COOLDOWN"

                    if rejection_reason:
                        diagnostics.append(
                            {
                                "time": row.name,
                                "event": f"SINAL VETADO: {rejection_reason}",
                                "side": side,
                                "rsi": row["rsi"],
                                "vol_mult": row["tick_volume"] / row["vol_sma"],
                            }
                        )
                    else:
                        # Executed Trade
                        sl_dist = self.opt_params["sl_dist"]
                        tp_dist = self.opt_params["tp_dist"]
                        sl = (
                            row["close"] - sl_dist
                            if side == "buy"
                            else row["close"] + sl_dist
                        )
                        tp = (
                            row["close"] + tp_dist
                            if side == "buy"
                            else row["close"] - tp_dist
                        )

                        self.position = {
                            "side": side,
                            "entry_price": row["close"],
                            "sl": sl,
                            "tp": tp,
                            "lots": 1,
                            "index": i,
                            "time": row.name,
                        }
                        side_pt = "COMPRA" if side == "buy" else "VENDA"
                        self.daily_trade_count += 1
                        diagnostics.append(
                            {
                                "time": row.name,
                                "event": f"EXECUÇÃO: {side_pt}",
                                "side": side,
                                "rsi": row["rsi"],
                                "vol_mult": row["tick_volume"] / row["vol_sma"],
                            }
                        )

        return diagnostics


async def analyze():
    params_path = "best_params_WIN.json"
    with open(params_path, "r") as f:
        config = json.load(f)
    params = config["params"]

    analyzer = DeepAnalyzer(
        symbol="WIN$",
        n_candles=600,
        initial_balance=1000.0,
        use_trailing_stop=True,
        **params,
    )
    logs = await analyzer.run_with_diagnostics()

    print("\n--- ANALISE PROFUNDA DE SINAIS (FILTROS) ---")
    for log in logs:
        print(
            f"[{log['time']}] {log['event']} | {log['side'].upper()} | RSI: {log['rsi']:.1f} | Vol: {log['vol_mult']:.1f}x"
        )


if __name__ == "__main__":
    asyncio.run(analyze())
