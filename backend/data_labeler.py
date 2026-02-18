import pandas as pd
import numpy as np

def apply_triple_barrier_method(df, pt_points=100.0, sl_points=50.0, time_limit_minutes=10):
    """
    [SOTA] Aplica o Método das Três Barreiras (Triple Barrier Method) para rotulagem de dados.
    Evita que a IA aprenda a operar em lateralidade.
    
    Args:
        df: DataFrame com OHLCV e timestamp
        pt_points: Take Profit em pontos (Barreira Superior)
        sl_points: Stop Loss em pontos (Barreira Inferior)
        time_limit_minutes: Limite de tempo (Barreira Vertical)
        
    Returns:
        DataFrame com coluna 'label' (1=Gain, -1=Loss, 0=Zero/TimeOut)
    """
    labels = []
    
    # Converter para datetime se necessário
    if not np.issubdtype(df['time'].dtype, np.datetime64):
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
    for i in range(len(df)):
        entry_price = df.iloc[i]['close']
        entry_time = df.iloc[i]['time']
        
        # Barreiras Dinâmicas
        upper_barrier = entry_price + pt_points
        lower_barrier = entry_price - sl_points
        vertical_barrier = entry_time + pd.Timedelta(minutes=time_limit_minutes)
        
        outcome = 0 # Default: TimeOut (0)
        
        # Olhar para o futuro
        # Janela de busca limitada pela barreira vertical para eficiência
        future_window = df.iloc[i+1 : i+1+time_limit_minutes+5] # buffer
        
        for j in range(len(future_window)):
            row = future_window.iloc[j]
            curr_high = row['high']
            curr_low = row['low']
            curr_time = row['time']
            
            # 1. Barreira Vertical (Tempo)
            if curr_time > vertical_barrier:
                outcome = 0
                break
                
            # 2. Barreira Inferior (Stop Loss) - Prioridade defensiva
            if curr_low <= lower_barrier:
                outcome = -1
                break
                
            # 3. Barreira Superior (Take Profit)
            if curr_high >= upper_barrier:
                outcome = 1
                break
                
        labels.append(outcome)
        
    df['label'] = labels
    return df
