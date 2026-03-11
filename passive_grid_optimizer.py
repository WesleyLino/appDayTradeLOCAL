import pandas as pd
import numpy as np
import itertools
import glob
import os

# Simulador Passivo de Retreinamento SOTA (Grid Search)
# O foco é testar hiperparâmetros contra o histórico (10/03) 
# para achar onde o potencial máximo da Compra (e Venda) se esconde, sem quebrar o bot.

# Lógica reconstruída da V22 SOTA
def calculate_rsi(series, period):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    return 100 - (100 / (1 + gain / loss))

def run_grid_search_optimisation():
    print("Iniciando Retreinamento Passivo (Grid Search Direcional) - SOTA V22.5.1")
    
    files = glob.glob("data/audit_m1_*.csv")
    if not files: 
        print("SEM DADOS MT5")
        return
        
    df = pd.read_csv(sorted(files)[-1])
    df['time'] = pd.to_datetime(df['time'])
    
    # Grid de Parâmetros a testar (Micro-ajustes)
    grid_rsi_periods = [7, 8, 9]
    grid_obi_thresholds = [0.85, 0.90, 0.95, 1.05]
    grid_rsi_buy_levels = [25, 30, 35]
    grid_rsi_sell_levels = [60, 65, 70]
    
    best_buy = {'score': -999, 'params': {}}
    best_sell = {'score': -999, 'params': {}}
    
    total_combs = len(grid_rsi_periods) * len(grid_obi_thresholds) * len(grid_rsi_buy_levels) * len(grid_rsi_sell_levels)
    print(f"Testando {total_combs} combinações para as Agulhas no Palheiro...")
    
    for r_period in grid_rsi_periods:
        df_opt = df.copy()
        df_opt['rsi'] = calculate_rsi(df_opt['close'], period=r_period)
        df_opt['vol_sma'] = df_opt['real_volume'].rolling(20).mean()
        df_opt.dropna(inplace=True)
        df_opt.reset_index(drop=True, inplace=True)
        
        for obi in grid_obi_thresholds:
            for r_buy in grid_rsi_buy_levels:
                for r_sell in grid_rsi_sell_levels:
                    
                    buy_wins, buy_losses = 0, 0
                    sell_wins, sell_losses = 0, 0
                    
                    for i in range(len(df_opt)-10):
                        row = df_opt.iloc[i]
                        flux_ok = row['real_volume'] > (row['vol_sma'] * obi)
                        
                        # SIMULA COMPRA
                        if row['rsi'] < r_buy and flux_ok:
                            mfe = df_opt.iloc[i+1:i+11]['high'].max() - row['close']
                            mae = row['close'] - df_opt.iloc[i+1:i+11]['low'].min()
                            
                            if mfe >= 70: buy_wins += 1
                            if mae >= 150: buy_losses += 1
                            
                        # SIMULA VENDA
                        if row['rsi'] > r_sell and flux_ok:
                            mfe = row['close'] - df_opt.iloc[i+1:i+11]['low'].min()
                            mae = df_opt.iloc[i+1:i+11]['high'].max() - row['close']
                            
                            if mfe >= 70: sell_wins += 1
                            if mae >= 150: sell_losses += 1

                    # Métrica de Score: WinRate * (Wins - Losses)
                    # Queremos o setup que gere os maiores gains enquanto sufoca os falsos alertas.
                    if buy_wins + buy_losses > 0:
                        b_score = (buy_wins / (buy_wins + buy_losses)) * (buy_wins - (buy_losses*0.5))
                        if b_score > best_buy['score']:
                            best_buy = {'score': b_score, 'wins': buy_wins, 'losses': buy_losses, 'params': {'RSI_P': r_period, 'OBI': obi, 'RSI_B': r_buy}}
                            
                    if sell_wins + sell_losses > 0:
                        s_score = (sell_wins / (sell_wins + sell_losses)) * (sell_wins - (sell_losses*0.5))
                        if s_score > best_sell['score']:
                            best_sell = {'score': s_score, 'wins': sell_wins, 'losses': sell_losses, 'params': {'RSI_P': r_period, 'OBI': obi, 'RSI_S': r_sell}}
                            
    print("\n================ RESULTADOS DA OTIMIZAÇÃO (DIRECIONAL) ================")
    print("\n[COMPRA / LONG PATTERN]")
    print(f"Melhor Configuração: RSI Period: {best_buy['params'].get('RSI_P')} | OBI Vol: {best_buy['params'].get('OBI')} | Límite RSI: {best_buy['params'].get('RSI_B')}")
    print(f"Performance: {best_buy.get('wins')} Ganhos (>70pts) vs {best_buy.get('losses')} Perdas Letais (WinRate: {(best_buy.get('wins',0)/(max(1, best_buy.get('wins',0)+best_buy.get('losses',0))))*100:.1f}%)")
    if best_buy.get('wins',0) <= best_buy.get('losses',0): print("[!] ALERTA: Mesmo otimizado, o viés do dia para compra foi matematicamente tóxico.")
    
    print("\n[VENDA / SHORT PATTERN]")
    print(f"Melhor Configuração: RSI Period: {best_sell['params'].get('RSI_P')} | OBI Vol: {best_sell['params'].get('OBI')} | Límite RSI: {best_sell['params'].get('RSI_S')}")
    print(f"Performance: {best_sell.get('wins')} Ganhos (>70pts) vs {best_sell.get('losses')} Perdas Letais (WinRate: {(best_sell.get('wins',0)/(max(1, best_sell.get('wins',0)+best_sell.get('losses',0))))*100:.1f}%)")

if __name__ == "__main__":
    run_grid_search_optimisation()
