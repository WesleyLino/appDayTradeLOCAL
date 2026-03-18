with open('backend/main.py', encoding='utf-8') as f:
    lines = f.readlines()

# Procura o bloco do packet principal do WebSocket (heartbeat)
for i, l in enumerate(lines, 1):
    if '"ai_score"' in l or '"ai_direction"' in l or '"direction"' in l and 'packet' in lines[max(0,i-10):i+1].__repr__():
        print(str(i).rjust(5), ':', l.rstrip().strip())

print()
print("=== Bloco hb_packet principal ===")
in_block = False
for i, l in enumerate(lines, 1):
    if 'hb_packet' in l and 'latest_market_packet' not in l and '= {' in l:
        in_block = True
    if in_block:
        print(str(i).rjust(5), ':', l.rstrip())
        if in_block and l.strip() == '}':
            in_block = False
            break
