from mt5_bridge import MT5Bridge
import MetaTrader5 as mt5

def main():
    bridge = MT5Bridge()
    if not bridge.connect():
        print("Erro ao conectar")
        return

    print("--- DIAGNÓSTICO BLUE CHIPS (PADRÃO B3) ---")
    data = bridge.get_bluechips_data()
    
    for symbol, var in data.items():
        # Validar manualmente pegando rates
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 2)
        if rates is not None and len(rates) >= 2:
            prev_close = rates[0]['close']
            tick = mt5.symbol_info_tick(symbol)
            curr = tick.last if tick and tick.last > 0 else rates[1]['close']
            calc_expected = ((curr - prev_close) / prev_close) * 100
            
            status = "OK" if abs(var - calc_expected) < 0.05 else "DIVERGENTE"
            print(f"{symbol}: Dashboard={var:+.2f}% | Esperado={calc_expected:+.2f}% | Status: {status}")
        else:
            print(f"{symbol}: Dados insuficientes no MT5")

    bridge.disconnect()

if __name__ == "__main__":
    main()
