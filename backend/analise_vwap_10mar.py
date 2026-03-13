import pandas as pd
import numpy as np

df = pd.read_csv("backend/historico_WIN_10mar_warmup.csv")
df['time'] = pd.to_datetime(df['time'])
df.set_index('time', inplace=True)

# Filtramos apenas 10/03 para análise
df_10 = df[df.index.date == pd.to_datetime("2026-03-10").date()].copy()

# Cálculo Simplificado de VWAP para o dia (acumulado desde as 09:00)
df_10['tp'] = (df_10['high'] + df_10['low'] + df_10['close']) / 3
df_10['vp'] = df_10['tp'] * df_10['tick_volume']
df_10['cum_vp'] = df_10['vp'].cumsum()
df_10['cum_vol'] = df_10['tick_volume'].cumsum()
df_10['vwap'] = df_10['cum_vp'] / df_10['cum_vol']

df_10['vwap_dist'] = abs(df_10['close'] - df_10['vwap'])

print(f"Estatísticas de Distância da VWAP em 10/03:")
print(df_10['vwap_dist'].describe())

print(f"\nPercentual de tempo com VWAP Dist > 400 pts: {(len(df_10[df_10['vwap_dist'] > 400]) / len(df_10) * 100):.1f}%")

# Verificando volatilidade M1
df_10['atr'] = (df_10['high'] - df_10['low']).rolling(14).mean()
print(f"\nATR Médio em 10/03: {df_10['atr'].mean():.2f}")
