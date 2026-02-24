import sys
import os

# Adiciona o diretório raiz ao sys.path para importar módulos do backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.mt5_bridge import MT5Bridge

def check_symbols():
    bridge = MT5Bridge()
    if bridge.connect():
        win = bridge.get_current_symbol("WIN")
        wdo = bridge.get_current_symbol("WDO")
        print(f"Símbolo WIN Atual Calculado: {win}")
        print(f"Símbolo WDO Atual Calculado: {wdo}")
        bridge.disconnect()
    else:
        print("Falha ao conectar no MT5 para verificar símbolos.")

if __name__ == "__main__":
    check_symbols()
