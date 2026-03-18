import re, os

main = open("backend/main.py", encoding="utf-8").read()
routes = re.findall(r'@app\.(get|post|put|delete|websocket)\("([^"]+)"', main)

print("=== ROTAS BACKEND ===")
for method, path in sorted(routes, key=lambda x: x[1]):
    print(f"  [{method.upper():9}] {path}")

print()
print("=== CHAMADAS FETCH NO FRONTEND (todas) ===")

for root, dirs, files in os.walk("frontend/src"):
    for f in sorted(files):
        if f.endswith((".ts", ".tsx")):
            fpath = os.path.join(root, f)
            content = open(fpath, encoding="utf-8").read()
            # Captura fetch com template literal ou string normal
            m1 = re.findall(r'fetch\(`[^`]*API_CONFIG\.http[^`]*`', content)
            m2 = re.findall(r'fetch\(`[^`]*:8000[^`]*`', content)
            for hit in m1 + m2:
                print(f"  {f}: {hit[:100]}")

print()

# Procura por performance endpoint
print("=== ENDPOINT /performance ===")
for root, dirs, files in os.walk("frontend/src"):
    for f in sorted(files):
        if f.endswith((".ts", ".tsx")):
            fpath = os.path.join(root, f)
            content = open(fpath, encoding="utf-8").read()
            if "performance" in content.lower():
                lines = content.split("\n")
                for i, l in enumerate(lines, 1):
                    if "performance" in l.lower() and "fetch" in l.lower():
                        print(f"  {f}:{i}: {l.strip()}")

print()
print("=== ROTAS DO /config CHAMADAS ===")
for root, dirs, files in os.walk("frontend/src"):
    for f in sorted(files):
        if f.endswith((".ts", ".tsx")):
            fpath = os.path.join(root, f)
            content = open(fpath, encoding="utf-8").read()
            lines = content.split("\n")
            for i, l in enumerate(lines, 1):
                if "fetch(" in l and ("/config" in l or "/order" in l or "/performance" in l):
                    print(f"  {f}:{i}: {l.strip()}")
