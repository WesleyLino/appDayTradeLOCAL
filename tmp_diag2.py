import sys
import os
import json
from datetime import datetime, time, timedelta

today_str = datetime.today().strftime("%Y-%m-%d")
now = datetime.now().time()
cwd = os.getcwd()
print("CWD:", cwd)
print("Hora actual:", now)

cal_path = os.path.join(cwd, "data", "economic_calendar.json")
print("Calendário path:", cal_path, "| Existe:", os.path.exists(cal_path))

if os.path.exists(cal_path):
    with open(cal_path) as f:
        data = json.load(f)
    print(f"Total eventos: {len(data)}")
    bloqueios = []
    for item in data:
        if item.get("impact", 0) < 3:
            continue
        event_date = item.get("date", "")
        if event_date and event_date != today_str:
            continue
        window = int(item.get("window_minutes", 3))
        evt_time_str = item["time"]
        evt_time = datetime.strptime(evt_time_str, "%H:%M").time()
        evt_dt = datetime.combine(datetime.today(), evt_time)
        start = (evt_dt - timedelta(minutes=window)).time()
        end = (evt_dt + timedelta(minutes=window)).time()
        bloqueado = start <= now <= end
        nome = item.get("event", "?")
        print(f"  [{item['impact']}*] {nome} | {start}->{end} | BLOQUEADO: {bloqueado}")
        if bloqueado:
            bloqueios.append(nome)
    if bloqueios:
        print(f"\n!!! BLOQUEIO ATIVO por: {bloqueios}")
    else:
        print("\nNenhum bloqueio de calendário ativo.")
else:
    print("Calendário não encontrado.")

# Verificar forbidden_hours
print("\n=== Forbidden Hours ===")
forbidden = [
    (time(8, 55), time(9, 15)),
    (time(12, 0), time(13, 0)),
    (time(17, 15), time(18, 0)),
]
for s, e in forbidden:
    ok = s <= now <= e
    print(f"  {s}-{e}: {'BLOQUEADO' if ok else 'livre'}")
