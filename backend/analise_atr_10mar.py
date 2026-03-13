import pandas as pd
import numpy as np

df = pd.read_csv("backend/historico_WIN_10mar.csv")
df['time'] = pd.to_datetime(df['time'])
df.set_index('time', inplace=True)

df['atr'] = (df['high'] - df['low']).rolling(14).mean()
print(f"Estatísticas de ATR M1 para 10/03:")
print(df['atr'].describe())

# Verificando momentos onde ATR < 60 (gatilho do relax)
relax_triggers = df[df['atr'] < 60]
print(f"\nNúmero de candles com ATR < 60: {len(relax_triggers)}")

# Verificando se houve signals v22_raw no dia 10/03
# Para isso precisaríamos rodar a lógica completa, mas podemos ver o log do backtest se tivermos salvo.
