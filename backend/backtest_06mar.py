import asyncio
import pandas as pd
import numpy as np
import logging
import json
import os
import sys
from datetime import datetime, time

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro
from backend.ai_core import AICore

async def run_audit():
    # 1. Carregar Parâmetros Atuais (Revertidos)
    params_path = "backend/v22_locked_params.json"
    if not os.path.exists(params_path):
        print(f"❌ Erro: Arquivo de parâmetros {params_path} not found.")
        return

    with open(params_path, "r") as f:
        config = json.load(f)
        strategy_params = config.get("strategy_params", {})
    
    # 2. Configurar Simulação
    target_date = "2026-03-06"
    initial_balance = 3000.0
    symbol = "WIN$"
    
    print(f"\n🚀 AUDITORIA SOTA: {target_date} | Capital: R$ {initial_balance}")
    print(f"⚙️ Configuração Ativa: RSI={strategy_params.get('rsi_period')} | OCO={strategy_params.get('sl_dist')}/{strategy_params.get('tp_dist')}")
    
    # Precisamos de candles suficientes
    n_candles = 3000 
    
    bt_prod = BacktestPro(
        symbol=symbol,
        n_candles=n_candles,
        initial_balance=initial_balance,
        **strategy_params
    )
    
    # Carregar dados do MT5
    print("📥 Coletando dados do MT5...")
    df_full = await bt_prod.load_data()
    if df_full is None or df_full.empty:
        print("❌ Erro ao carregar dados.")
        return

    # Filtrar o dia específico
    df_filtered = df_full[df_full.index.strftime('%Y-%m-%d') == target_date].copy()
    if df_filtered.empty:
        print(f"❌ Dados de {target_date} não encontrados no histórico.")
        return

    print(f"✅ {len(df_filtered)} candles carregados.")

    # --- PASS A: PRODUÇÃO ---
    print("\n[A] Simulação PRODUÇÃO (Com todos os filtros)...")
    bt_prod.data = df_filtered
    await bt_prod.run()
    
    # --- PASS B: SHADOW (Sem Filtro de ATR/Abertura) ---
    print("\n[B] Simulação SHADOW (Sem Trava de Volatilidade)...")
    # Resetamos o bot para rodar sem a flag de ATR pausado
    bt_shadow_no_atr = BacktestPro(
        symbol=symbol,
        n_candles=n_candles,
        initial_balance=initial_balance,
        **strategy_params
    )
    bt_shadow_no_atr.data = df_filtered
    # Desabilita o cálculo de ATR_PAUSADO forçando o valor cacheado para baixo
    bt_shadow_no_atr.hl_abertura_cache = 10.0 
    await bt_shadow_no_atr.run()

    # --- PASS C: BRUTE FORCE (Sem AI Veto e Sem ATR) ---
    print("\n[C] Simulação BRUTE FORCE (Sinais Técnicos Puros)...")
    strategy_no_ai = strategy_params.copy()
    strategy_no_ai['use_ai_core'] = False
    bt_brute = BacktestPro(
        symbol=symbol,
        n_candles=n_candles,
        initial_balance=initial_balance,
        **strategy_no_ai
    )
    bt_brute.data = df_filtered
    bt_brute.hl_abertura_cache = 10.0
    await bt_brute.run()
    
    # Relatório Consolidado
    results = {
        "date": target_date,
        "config": strategy_params,
        "production": {
            "pnl": bt_prod.daily_pnl,
            "trades": len(bt_prod.trades),
            "status": "PAUSADO" if bt_prod._dia_pausado_atr else "OPERATIVO"
        },
        "shadow_no_atr": {
            "pnl": sum(t['pnl_fin'] for t in bt_shadow_no_atr.trades),
            "trades": len(bt_shadow_no_atr.trades),
            "buy_pnl": sum(t['pnl_fin'] for t in bt_shadow_no_atr.trades if t['side'] == 'buy'),
            "sell_pnl": sum(t['pnl_fin'] for t in bt_shadow_no_atr.trades if t['side'] == 'sell')
        },
        "brute_force": {
            "pnl": sum(t['pnl_fin'] for t in bt_brute.trades),
            "trades": len(bt_brute.trades),
            "candidates": bt_prod.shadow_signals.get('v22_candidates', 0)
        }
    }
    
    with open("backend/audit_06mar_final.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📊 AUDITORIA CONCLUÍDA")
    print(f"Produção: PnL R$ {bt_prod.daily_pnl:.2f} ({len(bt_prod.trades)} trades)")
    print(f"Shadow (No ATR): PnL R$ {results['shadow_no_atr']['pnl']:.2f}")
    print(f"Brute Force: PnL R$ {results['brute_force']['pnl']:.2f} ({results['brute_force']['trades']} trades)")

if __name__ == "__main__":
    asyncio.run(run_audit())
