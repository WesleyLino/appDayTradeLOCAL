import re

callers = ['backend/main.py', 'backend/backtest_pro.py', 'backend/bot_sniper_win.py']
all_keys = set()
for fp in callers:
    with open(fp, encoding='utf-8') as f:
        content = f.read()
    found = re.findall(r'ai_decision\.get\(["\'](\w+)["\']', content)
    for k in found:
        all_keys.add(k)

print("Chaves lidas pelos callers:")
for k in sorted(all_keys):
    print(f"  - {k}")

print()
# Verifica o ultimo return no calculate_decision
with open('backend/ai_core.py', encoding='utf-8') as f:
    lines = f.readlines()

in_calc = False
in_return = False
brace_depth = 0
return_lines = []
for i, l in enumerate(lines):
    if 'def calculate_decision' in l:
        in_calc = True
    if in_calc and 'return {' in l:
        in_return = True
        brace_depth = 0
        return_lines = [l]
    elif in_return:
        return_lines.append(l)
        brace_depth += l.count('{') - l.count('}')
        if brace_depth <= 0 and '}' in l:
            break

return_block = ''.join(return_lines)
keys_ret = re.findall(r'"(\w+)"\s*:', return_block)
print("Chaves retornadas por calculate_decision:")
for k in sorted(set(keys_ret)):
    print(f"  - {k}")

print()
missing = all_keys - set(keys_ret)
if missing:
    print("FALTANDO no return dict:", missing)
else:
    print("OK: Todas as chaves esperadas estao presentes no return dict.")
