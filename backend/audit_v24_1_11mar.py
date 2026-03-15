import asyncio
import logging
import pandas as pd
import numpy as np
from backend.backtest_pro import BacktestPro

# Configuração de Idioma e Logging (OBRIGAÇÃO PT-BR)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AuditoriaV24_2")


async def run_final_audit():
    logger.info("🤖 Executando Simulação SOTA v24.2 - Dados 11/03")

    capital = 3000.0
    csv_path = "backend/historico_WIN_11mar.csv"

    try:
        df = pd.read_csv(csv_path)
        df["time"] = pd.to_datetime(df["time"])
        df.set_index("time", inplace=True)
        df.sort_index(inplace=True)

        bt = BacktestPro(symbol="WIN$", capital=capital)

        # Limpar NaNs de forma compatível com pandas modernos
        df = df.replace([np.inf, -np.inf], np.nan).ffill().fillna(0)

        bt.data = df

        logger.info(f"📊 Iniciando simulação com {len(df)} candles...")
        await bt.run()

        total_pnl = bt.balance - bt.initial_balance
        total_trades = len(bt.trades)

        print(f"RESULTADO_FINAL_PNL: R$ {total_pnl:.2f}")
        print(f"TRADES_EXECUTADOS: {total_trades}")
        print("VETOS_AI:", bt.shadow_signals.get("veto_reasons", {}))
        print("STATUS_PAUSE_ATR:", getattr(bt, "_dia_pausado_atr", False))

    except Exception as e:
        logger.error(f"❌ Erro na auditoria: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_final_audit())
