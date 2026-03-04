"""Script de revisao final completa da implementacao."""
import sys, json, os
sys.path.insert(0, '.')

import logging
logging.basicConfig(level=logging.WARNING)

PASS = "OK"
FAIL = "FALHA"
resultados = []

def check(nome, condicao, detalhe=""):
    status = PASS if condicao else FAIL
    resultados.append((status, nome, detalhe))
    return condicao

# ─── 1. VERIFICAÇÃO DO JSON ───────────────────────────────────────
try:
    with open('data/economic_calendar.json', encoding='utf-8') as f:
        data = json.load(f)
    check("JSON valido e parseavel", True)
except Exception as e:
    check("JSON valido e parseavel", False, str(e))
    data = []

eventos = [x for x in data if x.get('impact', 0) >= 3]
fomc = [x for x in eventos if 'FOMC' in x.get('event', '')]
nfp  = [x for x in eventos if 'NFP'  in x.get('event', '')]

check("Total eventos (impact>=3) = 100", len(eventos) == 100, f"Encontrado: {len(eventos)}")
check("FOMC: 40 eventos cadastrados", len(fomc) == 40, f"Encontrado: {len(fomc)}")
check("NFP: 60 eventos cadastrados", len(nfp) == 60, f"Encontrado: {len(nfp)}")
check("Todos com campo 'date'", all('date' in x for x in eventos))
check("Todos com campo 'time'", all('time' in x for x in eventos))
check("Todos com campo 'window_minutes'", all('window_minutes' in x for x in eventos))

if eventos:
    primeiro = min(x['date'] for x in eventos)
    ultimo   = max(x['date'] for x in eventos)
    check("Primeiro evento a partir de 2026", primeiro >= "2026-01-01", f"Primeiro: {primeiro}")
    check("Ultimo evento ate 2030", ultimo <= "2030-12-31", f"Ultimo: {ultimo}")
    print(f"  Periodo: {primeiro} -> {ultimo}")

# ─── 2. VERIFICAÇÃO DO RISK_MANAGER ──────────────────────────────
from backend.risk_manager import RiskManager
r = RiskManager()

check("RiskManager importa sem erro", True)
check("Atributo calendar_events existe", hasattr(r, 'calendar_events'))
check("Atributo post_event_momentum existe", hasattr(r, 'post_event_momentum'))
check("Atributo post_event_momentum_until existe", hasattr(r, 'post_event_momentum_until'))
check("Atributo post_event_name existe", hasattr(r, 'post_event_name'))
check("post_event_momentum inicia False", r.post_event_momentum == False)
check("Metodo is_direction_allowed existe", hasattr(r, 'is_direction_allowed') and callable(r.is_direction_allowed))
check("Metodo is_time_allowed existe", hasattr(r, 'is_time_allowed') and callable(r.is_time_allowed))

# Hoje nenhum evento deve carregar (todos sao futuros a partir de 06/03 ou ja passados)
check("Eventos carregados hoje em 04/03 = 0 (todos sao futuros)", len(r.calendar_events) == 0, f"Carregados: {len(r.calendar_events)}")

# Veto Direcional: logica completa
check("VetoDir: BUY permitido com sentimento +0.8", r.is_direction_allowed("BUY",  0.8) == True)
check("VetoDir: SELL bloqueado com sentimento +0.8", r.is_direction_allowed("SELL", 0.8) == False)
check("VetoDir: SELL permitido com sentimento -0.8", r.is_direction_allowed("SELL",-0.8) == True)
check("VetoDir: BUY bloqueado com sentimento -0.8",  r.is_direction_allowed("BUY", -0.8) == False)
check("VetoDir: BUY bloqueado com sentimento neutro", r.is_direction_allowed("BUY",  0.2) == False)
check("VetoDir: SELL bloqueado com sentimento neutro",r.is_direction_allowed("SELL", 0.2) == False)

# Alerta de expiracao: deve existir no codigo
with open('backend/risk_manager.py', encoding='utf-8') as f:
    rm_code = f.read()
check("Alerta de expiracao no codigo", "CALENDÁRIO EXPIRADO" in rm_code)
check("momentum_end calculado com +10 min", "window + 10" in rm_code)

# ─── 3. VERIFICAÇÃO DO MAIN.PY ───────────────────────────────────
with open('backend/main.py', encoding='utf-8') as f:
    main_code = f.read()

check("Threshold dinamico 65 presente no main.py", "_threshold_buy  = 65" in main_code)
check("Threshold padrao 85 presente no main.py", "_threshold_buy  = 85" in main_code)
check("post_event_momentum consultado no main.py", "post_event_momentum" in main_code)
check("Mensagem MOMENTUM no log do main.py", "[MOMENTUM] Threshold relaxado" in main_code)

# ─── RELATÓRIO ───────────────────────────────────────────────────
print()
print("=" * 65)
print("REVISÃO COMPLETA — CALENDÁRIO 2026-2030 + 4 MELHORIAS")
print("=" * 65)
falhas = 0
for status, nome, detalhe in resultados:
    icone = "✅" if status == PASS else "❌"
    msg = f"  {icone}  {nome}"
    if detalhe:
        msg += f"  » {detalhe}"
    print(msg)
    if status == FAIL:
        falhas += 1
print("=" * 65)
if falhas:
    print(f"\n⚠️  {falhas} FALHA(S). Revisar itens marcados com ❌")
    sys.exit(1)
else:
    print(f"\n🎉 TODOS OS {len(resultados)} CHECKS PASSARAM. Implementação validada.")
    sys.exit(0)
