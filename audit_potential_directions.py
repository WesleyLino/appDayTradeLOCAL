import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import glob

def calculate_mfe_mae(df, idx, direction, window=10):
    future = df.iloc[idx+1:idx+1+window] if idx + window < len(df) else df.iloc[idx+1:]
    if future.empty: return 0.0, 0.0
        
    entry_price = df['close'].iloc[idx]
    
    if direction == "BUY":
        max_price = future['high'].max()
        min_price = future['low'].min()
        return max_price - entry_price, entry_price - min_price
    else:
        min_price = future['low'].min()
        max_price = future['high'].max()
        return entry_price - min_price, max_price - entry_price

def calculate_rsi(series, period=7):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    return 100 - (100 / (1 + gain / loss))

def get_squeeze_signal(df, idx):
    if idx < 20: return "NEUTRAL"
    close = df['close'].iloc[idx]
    history_h = df['high'].iloc[idx-20:idx]
    history_l = df['low'].iloc[idx-20:idx]
    if (history_h.max() - close) < 50: return "BUY_SQUEEZE"
    if (close - history_l.min()) < 50: return "SELL_SQUEEZE"
    return "NEUTRAL"

def run_potential_audit():
    print("Iniciando Auditoria de Potencial Direcional (SOTA V22.5.1)")
    
    files = glob.glob("data/audit_m1_*.csv")
    if not files: return
        
    df = pd.read_csv(sorted(files)[-1])
    df['time'] = pd.to_datetime(df['time'])
    
    # SOTA Tech Specs
    df['rsi'] = calculate_rsi(df['close'], period=7)
    df['vol_sma'] = df['real_volume'].rolling(20).mean()
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)
    
    opps = {"BUY": [], "SELL": []}
    
    for i in range(20, len(df)):
        row = df.iloc[i]
        
        flux_ok = row['real_volume'] > (row['vol_sma'] * 0.95)
        comprar_base = (row['rsi'] < 30) and flux_ok
        vender_base = (row['rsi'] > 65) and flux_ok
        
        sqz = get_squeeze_signal(df, i)
        is_buy = comprar_base or sqz == "BUY_SQUEEZE"
        is_sell = vender_base or sqz == "SELL_SQUEEZE"
        
        if is_buy and not is_sell:
            mfe, mae = calculate_mfe_mae(df, i, "BUY")
            opps["BUY"].append({'time': row['time'], 'mfe': mfe, 'mae': mae, 'atr': row['atr'], 'type': 'SQUEEZE' if sqz=="BUY_SQUEEZE" else 'BASE'})
            
        elif is_sell and not is_buy:
            mfe, mae = calculate_mfe_mae(df, i, "SELL")
            opps["SELL"].append({'time': row['time'], 'mfe': mfe, 'mae': mae, 'atr': row['atr'], 'type': 'SQUEEZE' if sqz=="SELL_SQUEEZE" else 'BASE'})
            
    # TABELA RELATÓRIO
    print("\n" + "="*60)
    print(f"RELATÓRIO AI CORE POTENCIAL SOTA - DIA {df['time'].dt.date.iloc[-1]}")
    print("="*60)
    
    for side in ["BUY", "SELL"]:
        data = opps[side]
        df_ops = pd.DataFrame(data) if data else pd.DataFrame()
        total = len(df_ops)
        print(f"\n[{side} SIDE] Oportunidades Totais: {total}")
        if total > 0:
            assertive = df_ops[df_ops['mfe'] >= 70] # Chega no Trailing SOTA
            full_loss = df_ops[df_ops['mae'] >= 150] # Pega Stop Loss SOTA
            sqz_count = len(df_ops[df_ops['type'] == 'SQUEEZE'])
            
            print(f"  - Taxa de Acerto (>70pts): {len(assertive)} ({(len(assertive)/total)*100:.1f}%)")
            if not assertive.empty:
                print(f"  - MFE Médio (Ganhos Max): {assertive['mfe'].mean():.1f} pts")
            print(f"  - Sinais Falsos (MAE >150): {len(full_loss)} ({(len(full_loss)/total)*100:.1f}%)")
            print(f"  - Sinais vindos do Squeeze: {sqz_count}")
            print(f"  - ATR Médio nessas entradas: {df_ops['atr'].mean():.1f}")
            
            # Dinheiro na mesa
            if not assertive.empty:
                potencial_reais = len(assertive) * (70 * 0.20 * 3) # 70pts * 20c * 3Lot = R$42/trade
                print(f"  => Ganho Potencial (Conservador @ 70pts/3Lot): R$ {potencial_reais:.2f}")

if __name__ == "__main__":
    run_potential_audit()
