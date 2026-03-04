import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

dates = [
    '2026-02-19', '2026-02-23', '2026-02-24', 
    '2026-02-25', '2026-02-26', '2026-02-27', 
    '2026-03-03'
]

if not mt5.initialize():
    print("MT5 init failed")
    exit()

for d in dates:
    date_obj = datetime.strptime(d, '%Y-%m-%d')
    date_from = datetime(date_obj.year, date_obj.month, date_obj.day, 9, 0, 0)
    date_to = datetime(date_obj.year, date_obj.month, date_obj.day, 17, 30, 0)
    
    rates = mt5.copy_rates_range('WIN$', mt5.TIMEFRAME_M1, date_from, date_to)
    if rates is None or len(rates) == 0:
        continue
        
    df = pd.DataFrame(rates)
    df['hl'] = df['high'] - df['low']
    
    # Se for 03/03, pega os 10 primeiros; os de 09h podem nao existir.
    # Mas como o df está cortado para o dia, iloc[:10] pega os primeiros
    # 10 minutos *disponíveis* no dia.
    hl_mean = df['hl'].iloc[:10].mean()
    print(f"{d} (Primeiro M1 às {pd.to_datetime(df['time'].iloc[0], unit='s').strftime('%H:%M')}): H-L médio = {hl_mean:.1f} pts")

mt5.shutdown()
