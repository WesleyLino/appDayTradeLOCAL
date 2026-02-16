"""
Helper: Verificador de Símbolos MT5
====================================

Este script lista todos os símbolos disponíveis no MetaTrader 5
para ajudar a identificar o símbolo S&P500 correto.

Uso:
    python check_mt5_symbols.py
"""

import MetaTrader5 as mt5
import sys

def check_symbols():
    """Lista todos os símbolos disponíveis no MT5."""
    # Conectar ao MT5
    if not mt5.initialize():
        print("❌ Erro ao inicializar MT5")
        print(f"Erro: {mt5.last_error()}")
        sys.exit(1)
    
    print("✅ Conectado ao MT5\n")
    
    # Buscar símbolos relacionados ao S&P500
    sp500_keywords = ["SP", "WSP", "US500", "SPX", "ISP", "S&P"]
    
    print("=== Símbolos S&P500 Potenciais ===")
    all_symbols = mt5.symbols_get()
    
    found = False
    for symbol in all_symbols:
        symbol_name = symbol.name
        # Verificar se contém alguma keyword
        if any(kw in symbol_name.upper() for kw in sp500_keywords):
            print(f"  • {symbol_name} - {symbol.description}")
            found = True
    
    if not found:
        print("  ⚠️ Nenhum símbolo S&P500 encontrado no Market Watch")
        print("     Adicione manualmente via Ctrl+U no MT5\n")
    
    # Listar TODOS os símbolos (resumo)
    print(f"\n=== Total de Símbolos Disponíveis: {len(all_symbols)} ===")
    print("Primeiros 20 símbolos:")
    for i, symbol in enumerate(all_symbols[:20]):
        print(f"  {i+1}. {symbol.name} - {symbol.description}")
    
    print("\n💡 Para ver todos os símbolos, descomente a linha abaixo no código.")
    
    # Desconectar
    mt5.shutdown()

if __name__ == "__main__":
    check_symbols()
