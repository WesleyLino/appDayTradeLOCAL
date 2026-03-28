import json, os
from datetime import datetime, time, timedelta

today_str = datetime.today().strftime("%Y-%m-%d")
now = datetime.now().time()
print(f"Hora local Python: {datetime.now().strftime('%H:%M:%S')}")

paths = ["data/economic_calendar.json", "backend/data/economic_calendar.json"]
found = False
for p in paths:
    if os.path.exists(p):
        found = True
        with open(p) as f:
            data = json.load(f)

        print(f"\nArquivo: {p} ({len(data)} eventos total)")
        events_today = [e for e in data if e.get("date", "") == today_str or not e.get("date", "")]
        high_impact = [e for e in events_today if e.get("impact", 0) >= 3]
        print(f"Hoje ({today_str}): {len(events_today)} eventos | Alta Relevância (>=3): {len(high_impact)}")

        for e in high_impact:
            try:
                evt_time = datetime.strptime(e["time"], "%H:%M").time()
                window = int(e.get("window_minutes", 3))
                evt_dt = datetime.combine(datetime.today(), evt_time)
                start = (evt_dt - timedelta(minutes=window)).time()
                end = (evt_dt + timedelta(minutes=window)).time()
                momentum_end = (evt_dt + timedelta(minutes=window + 10)).time()
                bloqueado = start <= now <= end
                momentum = end < now <= momentum_end
                nome = e.get("event", "?")
                print(f"  [{e['impact']}★] {nome} @ {e['time']} | Janela: {start}-{end} | BLOQUEADO: {bloqueado} | MOMENTUM: {momentum}")
            except Exception as ex:
                print(f"  Erro ao processar evento: {ex} | {e}")
        break

if not found:
    print("Nenhum economic_calendar.json encontrado")

# Verificar forbidden_hours
print("\n=== Forbidden Hours Check ===")
forbidden = [
    (time(8, 55), time(9, 15)),
    (time(12, 0), time(13, 0)),
    (time(17, 15), time(18, 0)),
]
for start, end in forbidden:
    in_window = start <= now <= end
    print(f"  {start}-{end}: {'🔴 BLOQUEADO' if in_window else '✅ Livre'}")
