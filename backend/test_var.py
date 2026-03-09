import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

def test_variation():
    if not mt5.initialize():
        print("Falha ao inicializar")
        return

    ticker = "PETR4"
    # Pegar 2 dias: index 0 (hoje), index 1 (ontem)
    rates = mt5.copy_rates_from_pos(ticker, mt5.TIMEFRAME_D1, 0, 2)
    
    if rates is not None and len(rates) >= 2:
        prev_close = rates[0]['close']
        today_open = rates[1]['open']
        
        # Nota: no MT5 copy_rates_from_pos, o index 0 é o mais antigo na lista retornada 
        # se usarmos a lógica de array, mas copy_rates_from_pos(..., start_pos, count)
        # retorna candles do passado.
        # Na verdade, rates[0] é o candle de 'start_pos'. Se start_pos=0, rates[0] é o atual.
        # Se count=2, rates[0] é o atual e rates[1] é o anterior?? 
        # NÃO. No MT5 Python, a ordem retornada é cronológica: rates[0] é o mais antigo, rates[-1] é o mais novo.
        
        # Vamos conferir:
        for i, r in enumerate(rates):
            t = datetime.fromtimestamp(r['time'])
            print(f"Index {i}: {t} | Open: {r['open']} | Close: {r['close']}")
            
        print("-" * 30)
        
        # Se rates[0] é o mais antigo (ontem) e rates[1] é o mais novo (hoje/atual):
        yesterday_close = rates[0]['close']
        current_tick = mt5.symbol_info_tick(ticker)
        current_price = current_tick.last if current_tick and current_tick.last > 0 else yesterday_close
        
        var_b3 = ((current_price - yesterday_close) / yesterday_close) * 100
        print(f"Variação Padrão B3 (vs Ontem): {var_b3:+.2f}%")
        
        today_open = rates[1]['open']
        var_intra = ((current_price - today_open) / today_open) * 100
        print(f"Variação Robô Atual (vs Abertura): {var_intra:+.2f}%")
    else:
        print("Dados insuficientes")

    mt5.shutdown()

if __name__ == "__main__":
    test_variation()
