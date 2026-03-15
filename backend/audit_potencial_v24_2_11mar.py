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

        total_pnl = bt.balance - capital
        total_trades = len(bt.trades)

        print("\n" + "=" * 80)
        print(f"{'RELATÓRIO DE DESEMPENHO SOTA v24.2 - 11/03':^80}")
        print("=" * 80)
        print(
            f"Capital: R$ {capital:.2f} | PnL: R$ {total_pnl:.2f} ({(total_pnl / capital * 100):+.2f}%)"
        )
        print(f"Trades Totais: {total_trades}")

        if total_trades > 0:
            print(
                f"{'HORA':<8} | {'LADO':<8} | {'PNL':<10} | {'JANELA':<10} | {'MOTIVO':<20}"
            )
            print("-" * 80)
            for t in bt.trades:
                exit_t = t["exit_time"]
                hora_str = (
                    exit_t.strftime("%H:%M")
                    if hasattr(exit_t, "strftime")
                    else str(exit_t)
                )
                janela = "NORMAL"
                # Heurística para Janela de Ouro
                if exit_t.hour == 10 or exit_t.hour == 11:
                    janela = "GOLDEN"

                print(
                    f"{hora_str:<8} | {t['side']:<8} | R$ {t['pnl']:<8.2f} | {janela:<10} | {t.get('exit_reason', 'N/A'):<20}"
                )
        else:
            print("Nenhum trade executado no período filtrado de 11/03.")

        print("=" * 80)

    except Exception as e:
        logger.error(f"❌ Erro na auditoria: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_final_audit())
