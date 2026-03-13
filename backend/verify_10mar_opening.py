import pandas as pd
import numpy as np

df = pd.read_csv("backend/historico_WIN_10mar_warmup.csv")
df['time'] = pd.to_datetime(df['time'])
df.set_index('time', inplace=True)

df_10 = df[df.index.date == pd.to_datetime("2026-03-10").date()].copy()

if len(df_10) >= 10:
    hl_abertura = (df_10['high'].iloc[:10] - df_10['low'].iloc[:10]).mean()
    print(f"H-L Médio das primeiras 10 velas de 10/03: {hl_abertura:.2f} pts")
    print(f"Limiar de Pausa (HL_EXTREMO): 250.0 pts")
    if hl_abertura > 250.0:
        print(">>> PAUSA DE VOLATILIDADE ATIVADA")
    
    # Verificar quando o ATR cai abaixo de 80 (normalização)
    df_10['atr'] = (df_10['high'] - df_10['low']).rolling(14).mean()
    recovery = df_10[df_10['atr'] < 80.0]
    if not recovery.empty:
        print(f"O ATR normalizou (< 80) às: {recovery.index[0]}")
    else:
        print("O ATR NUNCA normalizou abaixo de 80.0 em 10/03.")
else:
    print("Dados insuficientes para calcular abertura de 10/03.")
