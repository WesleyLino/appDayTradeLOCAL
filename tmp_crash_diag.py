import os

log_files = [
    'backend/bot_sniper.log',
    'backend/app.log',
    'backend/main.log',
    'backend/error.log',
]

for lf in log_files:
    if os.path.exists(lf):
        with open(lf, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        # Procurar por erros críticos nas últimas 100 linhas
        recent = lines[-100:]
        errors = [l.rstrip() for l in recent if any(
            k in l for k in ['ERROR', 'CRITICAL', 'Traceback', 'Exception', 'raise ', 'Error:']
        )]
        print(f"\n=== {lf} ({len(lines)} linhas) ===")
        print(f"Erros encontrados nas ultimas 100 linhas: {len(errors)}")
        for e in errors[-20:]:
            safe = e.encode('ascii', errors='replace').decode('ascii')
            print(safe)
    else:
        print(f"[NAO ENCONTRADO] {lf}")
