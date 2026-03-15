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


class AuditorBacktester(BacktestPro):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rejections = []  # Lista de sinais ignorados por filtros

    async def run(self):
        data = await self.load_data()
        if data is None:
            return

        # Pre-calculos (Copiado do original para manter integridade)
        rsi_p = self.opt_params["rsi_period"]
        delta = data["close"].diff().fillna(0)
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_p).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_p).mean()
        rs = gain / (loss + 1e-6)
        data["rsi"] = 100 - (100 / (1 + rs))
        data["sma_20"] = data["close"].rolling(window=20).mean()
        data["std_20"] = data["close"].rolling(window=20).std()
        data["upper_bb"] = data["sma_20"] + 2.0 * data["std_20"]
        data["lower_bb"] = data["sma_20"] - 2.0 * data["std_20"]
        tr = pd.concat(
            [
                data["high"] - data["low"],
                (data["high"] - data["close"].shift()).abs(),
                (data["low"] - data["close"].shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        data["atr_current"] = tr.rolling(window=14).mean()
        data["vol_sma"] = data["tick_volume"].rolling(window=20).mean()

        # Regime e Prob (Mockados ou Reais)
        data["regime"] = 1  # Assume Trend
        data["dir_prob"] = 0.9  # Assume High Conf

        lookback = 60
        for i in range(lookback, len(data)):
            row = data.iloc[i]

            if self.position:
                exit_type, exit_price = self.simulate_oco(row, self.position)
                if exit_type:
                    self._close_trade(exit_price, exit_type, row.name)
                elif i - self.position["index"] > 25:
                    self._close_trade(row["close"], "TIME", row.name)
                continue

            # Auditoria de Sinais Mentais
            rsi = row["rsi"]
            lower_bb = row["lower_bb"]
            upper_bb = row["upper_bb"]
            mid_bb = data.iloc[i]["sma_20"]

            v22_buy = (row["close"] < lower_bb) and (rsi < 30)
            v22_sell = (row["close"] > upper_bb) and (rsi > 70)

            if v22_buy or v22_sell:
                # Verificar Filtros
                t_start = datetime.strptime(
                    self.opt_params["start_time"], "%H:%M"
                ).time()
                t_end = datetime.strptime(self.opt_params["end_time"], "%H:%M").time()
                time_ok = t_start <= row.name.time() <= t_end

                limit_ok = self.daily_trade_count < self.opt_params["daily_trade_limit"]
                vol_ok = 20 < row["atr_current"] < 400

                # AI Filter Score simulation
                ai_score = 0.8  # Simulado
                ai_ok = ai_score >= self.opt_params["confidence_threshold"]

                if time_ok and limit_ok and vol_ok and ai_ok:
                    side = "buy" if v22_buy else "sell"
                    sl = row["close"] - 150 if side == "buy" else row["close"] + 150
                    tp = row["close"] + 400 if side == "buy" else row["close"] - 400

                    self.position = {
                        "side": side,
                        "entry_price": row["close"],
                        "sl": sl,
                        "tp": tp,
                        "lots": 1,
                        "index": i,
                        "time": row.name,
                    }
                    self.daily_trade_count += 1
                else:
                    reason = ""
                    if not time_ok:
                        reason += "Time "
                    if not limit_ok:
                        reason += "Limit "
                    if not vol_ok:
                        reason += "Vol "
                    if not ai_ok:
                        reason += "AI_Score "
                    self.rejections.append(
                        {
                            "time": row.name,
                            "signal": "BUY" if v22_buy else "SELL",
                            "reason": reason.strip(),
                        }
                    )


async def analyze_full_audit():
    params_path = "best_params_WIN.json"
    with open(params_path, "r") as f:
        config = json.load(f)
    params = config["params"]

    auditor = AuditorBacktester(
        symbol="WIN$",
        n_candles=12000,  # 30 dias
        initial_balance=1000.0,
        use_trailing_stop=True,
        **params,
    )

    await auditor.run()

    # 1. Agregação Diária
    df_trades = pd.DataFrame(auditor.trades)
    if not df_trades.empty:
        df_trades["day"] = df_trades["exit_time"].dt.date
        daily_pnl = df_trades.groupby("day")["pnl_fin"].sum()
        print("\n=== PERFORMANCE DIÁRIA ===")
        print(daily_pnl)

        print(
            f"\nTotal Ganhos: R$ {df_trades[df_trades['pnl_fin'] > 0]['pnl_fin'].sum():.2f}"
        )
        print(
            f"Total Perdas: R$ {df_trades[df_trades['pnl_fin'] < 0]['pnl_fin'].sum():.2f}"
        )

    # 2. Oportunidades Perdidas
    df_rej = pd.DataFrame(auditor.rejections)
    if not df_rej.empty:
        print("\n=== OPORTUNIDADES FILTRADAS (Vetos) ===")
        print(df_rej["reason"].value_counts())

        # Amostra de reajustes
        print("\nExemplo de Vetos:")
        print(df_rej.head(5))

    # 3. Análise de Breakeven vs Trailing
    if not df_trades.empty:
        print("\n=== MOTIVOS DE SAÍDA ===")
        print(df_trades["reason"].value_counts())


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.WARNING)
    asyncio.run(analyze_full_audit())
