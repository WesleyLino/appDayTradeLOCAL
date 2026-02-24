"""Script de teste funcional de todos os endpoints do backend HFT."""
import urllib.request
import urllib.error
import json
import sys

BASE = "http://localhost:8000"
FRONTEND = "http://localhost:3000"

results = []

def run_http_test(name, url, method="GET", body=None, expected_status=200):
    try:
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            content = r.read().decode("utf-8", errors="replace")
            status = r.status
            ok = status == expected_status
            snippet = content[:120].replace("\n", " ")
            results.append((ok, name, status, snippet))
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")[:120]
        results.append((False, name, e.code, body_err))
    except Exception as ex:
        results.append((False, name, 0, str(ex)[:120]))

if __name__ == "__main__":
    # --- Testes ---
    run_http_test("Frontend /",             FRONTEND,                                   "GET")
    run_http_test("Backend /docs",          f"{BASE}/docs",                             "GET")
    run_http_test("GET /performance",       f"{BASE}/performance",                      "GET")
    run_http_test("POST /config/sniper/stop",f"{BASE}/config/sniper/stop",              "POST", {})
    run_http_test("POST /toggle-autonomous", f"{BASE}/config/autonomous?enabled=false", "POST", {})

    # Verifica se /performance retorna campos esperados
    try:
        with urllib.request.urlopen(f"{BASE}/performance", timeout=5) as r:
            d = json.loads(r.read())
            has_status = d.get("status") == "success"
            has_data   = "data" in d
            has_dryrun = "dry_run" in d.get("data", {})
            results.append((has_status and has_data and has_dryrun,
                            "performance JSON schema", 200,
                            f"status={d.get('status')}, dry_run={d.get('data',{}).get('dry_run')}"))
    except Exception as ex:
        results.append((False, "performance JSON schema", 0, str(ex)[:120]))

    # --- Relatório ---
    print("\n" + "="*70)
    print("  RELATÓRIO DE TESTES — QuantumTrade HFT Backend")
    print("="*70)
    for ok, name, status, snippet in results:
        icon = "✅" if ok else "❌"
        print(f"{icon}  [{status}] {name}")
        if not ok:
            print(f"   └─ {snippet}")

    total = len(results)
    passed = sum(1 for ok, *_ in results if ok)
    print("="*70)
    print(f"  RESULTADO: {passed}/{total} testes passaram")
    print("="*70)

    sys.exit(0 if passed == total else 1)
