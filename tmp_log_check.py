import sys

# Forçar saída sem emojis para compatibilidade com PowerShell cp1252
keywords = ['BYPASS', 'VETO', 'SIMULAC', 'GATILHO', 'bloqueado', 'WARNING', 'Ativado', 'macro', 'cooldown', 'pyramid', 'Score']

with open('backend/bot_sniper.log', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

recent = lines[-300:]
filtered = [l.rstrip() for l in recent if any(k.lower() in l.lower() for k in keywords)]

# Remover caracteres não-ASCII para compatibilidade com Windows terminal
def safe(s):
    return s.encode('ascii', errors='replace').decode('ascii')

output_lines = [
    f"Total linhas no log: {len(lines)}",
    f"Ocorrencias criticas (ultimas 300 linhas): {len(filtered)}",
    "---",
]
for l in filtered[-40:]:
    output_lines.append(safe(l))

result = "\n".join(output_lines)

with open('tmp_log_result.txt', 'w', encoding='utf-8') as out:
    out.write(result)

print("OK - resultado salvo em tmp_log_result.txt")
print(f"Total: {len(lines)} linhas | Criticos: {len(filtered)}")
