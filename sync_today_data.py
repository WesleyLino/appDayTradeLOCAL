import MetaTrader5 as mt5
from backend.data_collector_historical import HistoricalDataCollector
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def sync_today():
    collector = HistoricalDataCollector()
    if not collector.connect():
        return

    today = datetime(2026, 3, 6)
    tomorrow = today + dt.timedelta(days=1)
    
    symbols = {
        "PRINCIPAL": ["WIN$", "WDO$"],
        "BLUE_CHIPS": ["VALE3", "PETR4", "ITUB4"],
        "CORRELATION": [] 
    }
    
    all_symbols = symbols["PRINCIPAL"] + symbols["BLUE_CHIPS"]
    
    for symbol in all_symbols:
        logging.info(f"--- Sincronizando Hoje: {symbol} ---")
        
        # Candles M1
        df_c = collector.get_historical_candles(symbol, mt5.TIMEFRAME_M1, today, tomorrow)
        
        # Ticks for principal symbols
        df_t = None
        if symbol in symbols["PRINCIPAL"]:
            df_t = collector.get_historical_ticks(symbol, today, tomorrow)
        
        if df_c is not None and not df_c.empty:
            collector.process_and_save(symbol, df_c, df_t)
        else:
            logging.warning(f"Sem dados para {symbol} hoje.")

    mt5.shutdown()

if __name__ == "__main__":
    import datetime as dt # Fix for timedelta access
    sync_today()
