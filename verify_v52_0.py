import asyncio
import pandas as pd
import logging
from backend.backtest_pro import BacktestPro

# Configuração de Logs em PT-BR
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def verify_v52_0():
    logging.info("🕵️ INICIANDO AUDITORIA HFT v52.0 - PADRÃO ELITE INSTITUCIONAL")

    # 1. Arquivos de Dados OHLCV Reais
    data_files = [
        "backend/data_19_02_2026.csv",
        "backend/data_20_02_2026.csv",
        "backend/data_23_02_2026.csv",
    ]

    total_pnl = 0
    all_trades = []

    for df_path in data_files:
        logging.info(f"📊 Analisando dia: {df_path}")
        bt = BacktestPro(
            symbol="WIN$", n_candles=10000, data_file=df_path, use_ai_core=True
        )

        results = await bt.run()
        total_pnl += results["total_pnl"]
        all_trades.extend(bt.trades)

    # 4. Gerar Relatório de Comparação
    win_trades = [t for t in all_trades if t["pnl_fin"] > 0]
    win_rate = (len(win_trades) / len(all_trades) * 100) if all_trades else 0

    logging.info("\n" + "=" * 50)
    logging.info("🏆 RESULTADOS AGREGADOS v52.0 (HFT INSTITUCIONAL)")
    logging.info("=" * 50)
    logging.info(f"Lucro Acumulado (3 dias): R$ {total_pnl:.2f}")
    logging.info(f"Taxa de Win Média: {win_rate:.2f}%")
    logging.info(f"Total de Trades: {len(all_trades)}")
    logging.info("=" * 50)

    # Salvar Curva de Equity para Inspeção
    equity_df = pd.DataFrame({"Equity": bt.equity_curve})
    equity_df.to_csv("backend/audit_v52_0_pnl.csv")
    logging.info("💾 Curva de Equity salva em 'backend/audit_v52_0_pnl.csv'")


if __name__ == "__main__":
    asyncio.run(verify_v52_0())
