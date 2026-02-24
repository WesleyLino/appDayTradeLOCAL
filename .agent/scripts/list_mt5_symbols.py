import MetaTrader5 as mt5

def list_symbols():
    if not mt5.initialize():
        print("Falha ao inicializar MT5")
        return

    symbols = mt5.symbols_get()
    print(f"Total de símbolos encontrados: {len(symbols)}")
    
    # Filtra os que contêm WIN
    win_symbols = [s.name for s in symbols if "WIN" in s.name]
    print(f"Símbolos com 'WIN': {win_symbols[:20]}") # Mostra os 20 primeiros
    
    # Verifica Market Watch
    selected = mt5.symbols_get(group="*,!*") # Todos os selecionados? Não, isso é filtro.
    # A melhor forma de saber o que está no Market Watch é tentar symbol_select
    print("Verificando símbolos no Market Watch (selecionados):")
    for s in symbols:
        if s.select:
            print(f"- {s.name}")

    mt5.shutdown()

if __name__ == "__main__":
    list_symbols()
