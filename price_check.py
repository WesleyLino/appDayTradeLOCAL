import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

def check_prices():
    if not mt5.initialize():
        print("Erro ao inicializar MT5")
        return

    dates = ['2026-02-23', '2026-02-24', '2026-02-25']
    for d_str in dates:
        dt = datetime.strptime(d_str, '%Y-%m-%d')
        # Busca 20.000 velas para garantir cobertura
        rates = mt5.copy_rates_from_pos('WIN$', mt5.TIMEFRAME_M1, 0, 20000)
        if rates is None:
            print(f"{d_str}: Falha ao copiar rates")
            continue
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        target = df[df['time'].dt.date == dt.date()]
        
        if not target.empty:
            print(f"{d_str}: Avg Price {target['close'].mean():.2f}, Count {len(target)}")
            print(f"Exemp: {target[['time', 'close']].head(2)}")
        else:
            print(f"{d_str}: No data in buffer")
            
    mt5.shutdown()

if __name__ == "__main__":
    check_prices()
