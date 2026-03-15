import asyncio
import logging
import pandas as pd
import MetaTrader5 as mt5

# Configuração de Idioma e Logging (OBRIGATÓRIO PT-BR)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ExportadorHistorico10mar")


async def export_data():
    logger.info("📥 Conectando ao MetaTrader 5 para exportar histórico de 10/03...")

    if not mt5.initialize():
        logger.error("❌ Falha ao inicializar o MT5.")
        return

    symbol = "WIN$"
    timeframe = mt5.TIMEFRAME_M1

    # Coletamos amostra suficiente para cobrir o dia 10/03
    # Hoje é 12/03. 10/03 foi há 2 dias.
    # 5000 candles M1 cobrem ~10 dias de pregão (480/dia).
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 5000)

    if rates is None or len(rates) == 0:
        logger.error(f"❌ Não foi possível obter dados para {symbol}.")
        mt5.shutdown()
        return

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")

    # Filtramos apenas o dia 10/03
    mask = (df["time"] >= "2026-03-10 09:00:00") & (df["time"] <= "2026-03-10 18:30:00")
    df_10mar = df[mask].copy()

    if df_10mar.empty:
        logger.warning("⚠️ Nenhum dado encontrado para o dia 10/03 na amostra coletada.")
        mt5.shutdown()
        return

    output_file = "backend/historico_WIN_10mar.csv"
    df_10mar.to_csv(output_file, index=False)

    logger.info(
        f"✅ Arquivo gerado com sucesso: {output_file} ({len(df_10mar)} linhas)"
    )
    mt5.shutdown()


if __name__ == "__main__":
    asyncio.run(export_data())
