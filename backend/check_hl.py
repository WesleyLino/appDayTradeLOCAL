import pandas as pd
import joblib

df = joblib.load('data/mt5_WIN$_M1.pkl')
df['hl_amplitude'] = df['high'] - df['low']
import datetime

dates = pd.Series(df.index.date).unique()

print("Média Amplitude (H-L) das 10 primeiras velas de cada dia:")
for date in dates:
    df_day = df[df.index.date == date]
    if len(df_day) >= 10:
        hl_mean = df_day['hl_amplitude'].iloc[:10].mean()
        print(f"{date}: {hl_mean:.1f} pts")
