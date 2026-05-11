import json

with open('.tmp/proposed_schedule.json', encoding='utf-8') as f:
    data = json.load(f)

print("--- Primeras 15 asignaciones ---")
for g in data[:15]:
    status = "OK" 
    print(f"{g['date']} {g['start_time']} - {g['room']} : {g['group_name']} ({status})")

print("...")
print("--- Últimas 5 asignaciones ---")
for g in data[-5:]:
    print(f"{g['date']} {g['start_time']} - {g['room']} : {g['group_name']}")
