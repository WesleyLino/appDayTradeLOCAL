"""
Detecta o símbolo correto do mini-índice no Market Watch atual e lista contratos disponíveis.
"""
import MetaTrader5 as mt5
from datetime import datetime

if not mt5.initialize():
    print("ERRO: MT5 nao iniciou.")
    exit(1)

print("Simbolos de INDICE disponiveis no Market Watch:")
symbols = mt5.symbols_get()
candidatos = []
for s in symbols:
    name = s.name
    if any(k in name.upper() for k in ["WIN", "WDO", "IND"]):
        info = mt5.symbol_info(name)
        last_bar = mt5.copy_rates_from_pos(name, mt5.TIMEFRAME_M1, 0, 1)
        has_data = last_bar is not None and len(last_bar) > 0
        print(f"  {name:15s}  visible={s.visible}  dados_recentes={has_data}")
        if has_data:
            candidatos.append(name)

mt5.shutdown()
print()
print("Simbolos com dados disponiveis:", candidatos)
