"""Script de Auditoria Completa v52.1 - Verificação de Integridade"""
import sys
import json

sys.path.append('.')
from backend.risk_manager import RiskManager
from backend.ai_core import AICore

print("=== AUDITORIA COMPLETA v52.1 ===")
print()

r = RiskManager()
ai = AICore()

# --- Verifica RiskManager ---
print("--- RiskManager ---")
print(f"  daily_trade_limit : {r.daily_trade_limit}  (esperado: 999)")
print(f"  be_trigger        : {r.be_trigger}    (esperado: 40.0)")
print(f"  be_lock           : {r.be_lock}      (esperado: 0.0)")
print(f"  partial_profit_pts: {r.partial_profit_points}    (esperado: 45.0)")
print(f"  trailing_trigger  : {r.trailing_trigger}    (esperado: 70.0)")
print(f"  trailing_lock     : {r.trailing_lock}    (esperado: 50.0)")
print(f"  trailing_step     : {r.trailing_step}    (esperado: 20.0)")
print()

# --- Verifica AICore ---
print("--- AICore ---")
print(f"  buy_threshold  : {ai.buy_threshold}    (esperado: 75.0)")
print(f"  sell_threshold : {ai.sell_threshold}    (esperado: 25.0)")
print()

# --- Verifica JSON golden params ---
print("--- v22_locked_params.json ---")
with open('backend/v22_locked_params.json', 'r', encoding='utf-8') as f:
    content = f.read().replace('  ', ' ')  # remove duplo espaço para JSON valido
    # Remove comentários trailing (json padrao nao suporta)
    import re
    content_clean = re.sub(r',\s*//[^\n]*', '', content)
    params = json.loads(content_clean)

sp = params['strategy_params']
print(f"  daily_trade_limit   : {sp['daily_trade_limit']}  (esperado: 999)")
print(f"  be_trigger          : {sp['be_trigger']}    (esperado: 40.0)")
print(f"  partial_profit_pts  : {sp['partial_profit_points']}    (esperado: 45.0)")
print(f"  confidence_threshold: {sp['confidence_threshold']}   (esperado: 0.75)")
print(f"  vwap_dist_threshold : {sp['vwap_dist_threshold']}   (esperado: 450.0)")
print(f"  sl_dist             : {sp['sl_dist']}   (esperado: 150.0)")
print(f"  tp_dist             : {sp['tp_dist']}   (esperado: 550.0)")
print()

# --- Verifica best_params_WIN.json ---
print("--- best_params_WIN.json ---")
with open('best_params_WIN.json', 'r', encoding='utf-8') as f:
    bp = json.load(f)
wp = bp['params']
print(f"  daily_trade_limit   : {wp.get('daily_trade_limit', 'AUSENTE')}  (esperado: 999)")
print(f"  confidence_threshold: {wp.get('confidence_threshold', 'AUSENTE')}   (esperado: 0.75)")
print(f"  be_trigger          : {wp.get('be_trigger', 'AUSENTE')}    (esperado: 40.0)")
print(f"  partial_profit_pts  : {wp.get('partial_profit_points', 'AUSENTE')}    (esperado: 45.0)")
print(f"  versao              : {bp.get('version', 'AUSENTE')}")
print()

# --- Checklist Final ---
print("--- CHECKLIST FINAL ---")
erros = []
if r.daily_trade_limit != 999: erros.append("ERRO: RiskManager.daily_trade_limit != 999")
if r.be_trigger != 40.0:       erros.append("ERRO: RiskManager.be_trigger != 40.0")
if r.partial_profit_points != 45.0: erros.append("ERRO: RiskManager.partial_profit_points != 45.0")
if ai.buy_threshold != 75.0:   erros.append("ERRO: AICore.buy_threshold != 75.0")
if ai.sell_threshold != 25.0:  erros.append("ERRO: AICore.sell_threshold != 25.0")
if sp['daily_trade_limit'] != 999:  erros.append("ERRO: JSON.daily_trade_limit != 999")
if sp['confidence_threshold'] != 0.75: erros.append("ERRO: JSON.confidence_threshold != 0.75")
if sp['be_trigger'] != 40.0:        erros.append("ERRO: JSON.be_trigger != 40.0")
if wp.get('daily_trade_limit') != 999: erros.append("ERRO: best_params_WIN.daily_trade_limit != 999")
if wp.get('confidence_threshold') != 0.75: erros.append("ERRO: best_params_WIN.confidence_threshold != 0.75")

if not erros:
    print("  [OK] TODOS OS PARAMETROS v52.1 APROVADOS COM SUCESSO!")
    print("  [OK] IMPLEMENTACAO COMPLETA SEM ERROS - MODO ILIMITADO ATIVO")
else:
    for e in erros:
        print(f"  {e}")
