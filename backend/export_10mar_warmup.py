import asyncio
import logging
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ExportadorHistoricoWarmup")

async def export_data():
    if not mt5.initialize():
        return

    symbol = "WIN$"
    timeframe = mt5.TIMEFRAME_M1
    
    # Coletamos 6000 candles para garantir 09/03 e 10/03 inteiros
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 6000)
    
    if rates is None or len(rates) == 0:
        mt5.shutdown()
        return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Pegamos do início do dia 09/03 até o fim do dia 10/03
    mask = (df['time'] >= '2026-03-09 09:00:00') & (df['time'] <= '2026-03-10 18:30:00')
    df_history = df[mask].copy()
    
    output_file = "backend/historico_WIN_10mar_warmup.csv"
    df_history.to_csv(output_file, index=False)
    
    logger.info(f"✅ Arquivo gerado com sucesso: {output_file} ({len(df_history)} linhas)")
    mt5.shutdown()

if __name__ == "__main__":
    asyncio.run(export_data())
