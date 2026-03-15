import MetaTrader5 as mt5
import json
from datetime import datetime


def inspect():
    if not mt5.initialize():
        print("Failed")
        return

    data = {}

    # 1. Terminal Info
    t_info = mt5.terminal_info()
    if t_info:
        data["terminal_info"] = t_info._asdict()

    # 2. Account Info
    a_info = mt5.account_info()
    if a_info:
        data["account_info"] = a_info._asdict()

    # 3. Symbol Info
    symbols = mt5.symbols_get(group="*WIN*")
    if symbols:
        # Pega o WIN mais líquido ou o primeiro
        sym = symbols[0].name
        for s in symbols:
            if "WIN" in s.name and len(s.name) == 6:  # Ex: WINJ24
                sym = s.name
                break

        symbol_data = mt5.symbol_info(sym)
        if symbol_data:
            data["symbol_info_example"] = symbol_data._asdict()

        # Ticks
        ticks = mt5.copy_ticks_from(sym, datetime.utcnow(), 10, mt5.COPY_TICKS_ALL)
        if ticks is not None and len(ticks) > 0:
            data["ticks_example"] = [
                {
                    "time": int(t["time"]),
                    "bid": float(t["bid"]),
                    "ask": float(t["ask"]),
                    "last": float(t["last"]),
                    "volume": float(t["volume"]),
                    "time_msc": int(t["time_msc"]),
                    "flags": int(t["flags"]),
                    "volume_real": float(t["volume_real"]),
                }
                for t in ticks
            ]

    mt5.shutdown()

    with open("mt5_inspection_result.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print("DONE")


if __name__ == "__main__":
    inspect()
