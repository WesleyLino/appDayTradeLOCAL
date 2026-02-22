import pandas as pd
import numpy as np

def apply_triple_barrier_method(df, pt_points=100.0, sl_points=50.0, time_limit_minutes=15):
    """
    [VECTORIZED] Aplica o Método das Três Barreiras de forma otimizada.
    """
    if df is None or len(df) < 2: return df
    
    df = df.copy()
    if not np.issubdtype(df['time'].dtype, np.datetime64):
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
    prices = df['close'].values
    highs = df['high'].values
    lows = df['low'].values
    times = df['time'].values
    n = len(df)
    
    labels = np.zeros(n)
    
    # Pré-calcular limites
    upper_barriers = prices + pt_points
    lower_barriers = prices - sl_points
    vertical_barriers = times + np.timedelta64(time_limit_minutes, 'm')
    
    for i in range(n - 1):
        # Janela de busca (limitada pelo time_limit)
        # Assumindo 1 min por candle, a busca dura cerca de time_limit_minutes + buffer
        search_end = min(i + time_limit_minutes + 2, n)
        
        future_highs = highs[i+1 : search_end]
        future_lows = lows[i+1 : search_end]
        future_times = times[i+1 : search_end]
        
        # Encontrar primeira barreira atingida
        # 1. SL (Prioridade)
        sl_hits = np.where(future_lows <= lower_barriers[i])[0]
        # 2. TP
        tp_hits = np.where(future_highs >= upper_barriers[i])[0]
        # 3. Time
        time_hits = np.where(future_times > vertical_barriers[i])[0]
        
        # Determinar qual ocorreu primeiro
        first_sl = sl_hits[0] if len(sl_hits) > 0 else n
        first_tp = tp_hits[0] if len(tp_hits) > 0 else n
        first_time = time_hits[0] if len(time_hits) > 0 else n
        
        first_hit = min(first_sl, first_tp, first_time)
        
        if first_hit == n:
            labels[i] = 0
        elif first_hit == first_sl:
            labels[i] = -1
        elif first_hit == first_tp:
            labels[i] = 1
        else:
            labels[i] = 0
            
    df['label'] = labels.astype(int)
    return df
