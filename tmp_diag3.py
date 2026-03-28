import json, os
from datetime import datetime, time, timedelta

today_str = datetime.today().strftime("%Y-%m-%d")
now = datetime.now().time()
print(f"Hora: {now} | Hoje: {today_str}")

cal_path = os.path.join(os.getcwd(), "data", "economic_calendar.json")
with open(cal_path) as f:
    data = json.load(f)

# Replicar exatamente a lógica do _load_economic_calendar
calendar_events = []
for item in data:
    if item.get("impact", 0) < 3:
        continue
    event_date = item.get("date")
    if event_date and event_date != today_str:
        continue
    # Evento sem data OU data == hoje
    window = int(item.get("window_minutes", 3))
    evt_time = datetime.strptime(item["time"], "%H:%M").time()
    evt_dt = datetime.combine(datetime.today(), evt_time)
    start = (evt_dt - timedelta(minutes=window)).time()
    end = (evt_dt + timedelta(minutes=window)).time()
    momentum_end = (evt_dt + timedelta(minutes=window + 10)).time()
    calendar_events.append({
        "start": start,
        "end": end,
        "momentum_end": momentum_end,
        "event": item.get("event", "?"),
        "time": item["time"],
        "date": event_date or "TODOS OS DIAS",
        "impact": item.get("impact", 0),
    })

print(f"\nEventos carregados em memory (impacto>=3, hoje ou sem data): {len(calendar_events)}")
for ev in calendar_events:
    bloqueado = ev["start"] <= now <= ev["end"]
    momentum = ev["end"] < now <= ev["momentum_end"]
    status = "🔴 BLOQUEADO" if bloqueado else ("⚡ MOMENTUM" if momentum else "✅ livre")
    print(f"  {status} | {ev['impact']}* {ev['event']} [{ev['date']}] @ {ev['time']} | {ev['start']}-{ev['end']}")

# Simula is_time_allowed
print("\n=== Simulação is_time_allowed ===")
for ev in calendar_events:
    if ev["start"] <= now <= ev["end"]:
        print(f"VETO CALENDÁRIO: {ev['event']}")
        break
else:
    print("Nenhum veto de calendário ativo")
