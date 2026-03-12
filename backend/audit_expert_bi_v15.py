import pandas as pd
import numpy as np
import os
import json
import asyncio
from datetime import datetime, timedelta
import logging
import sys

# Adiciona diretório raiz ao path para importar backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

# Configuração de Logs - Silencioso para não poluir
logging.basicConfig(level=logging.WARNING, format='%(message)s')

async def run_expert_bi_audit():
    # Datas solicitadas (em ordem cronológica)
    dias = [
        "2026-02-19", "2026-02-20", "2026-02-23", "2026-02-24", "2026-02-25", 
        "2026-02-26", "2026-02-27", "2026-03-02", "2026-03-03", "2026-03-04", 
        "2026-03-05", "2026-03-06", "2026-03-09", "2026-03-10", "2026-03-11"
    ]

    v36_expert_config = {
        'confidence_buy_threshold': 58.0, 
        'confidence_sell_threshold': 42.0,
        'daily_trade_limit': 20,
        'base_lot': 3,
        'use_ai_core': True,
        'aggressive_mode': True,
        'sl_dist': 220.0,
        'tp_dist': 300.0
    }

    print(f"📥 Sincronizando dados históricos WIN$ (15 dias)...")
    bt_loader = BacktestPro(symbol="WIN$", n_candles=15000)
    data_full = await bt_loader.load_data()
    
    if data_full is None or data_full.empty:
        print("❌ Erro ao carregar dados.")
        return

    resultados_diarios = []
    consolidado = {
        "pnl_total": 0.0,
        "total_compra": 0.0,
        "total_venda": 0.0,
        "total_prejuizo": 0.0,
        "oportunidades_perdidas": 0,
        "vetos_totais": 0
    }

    print(f"\n💎 AUDITORIA EXPERT BI-DIRECIONAL (V22.5.7)")
    print(f"{'Data':<10} | {'PnL':<8} | {'Compra':<8} | {'Venda':<8} | {'Loss':<8} | {'Opt. Perd.'}")
    print("-" * 70)

    for dia_str in dias:
        dia_dt = datetime.strptime(dia_str, "%Y-%m-%d").date()
        
        # Filtra dados até o dia
        mask = (data_full.index.date <= dia_dt)
        data_slice = data_full.loc[mask]
        
        if data_slice.empty or data_full.index.date.max() < dia_dt:
            continue
            
        bt = BacktestPro(symbol="WIN$")
        bt.initial_balance = 3000.0
        bt.opt_params.update(v36_expert_config)
        bt.data = data_slice
        
        res = await bt.run()
        
        # Filtra trades do dia
        day_trades = []
        for t in res['trades']:
            t_date = t['entry_time'].date() if hasattr(t['entry_time'], 'date') else datetime.strptime(str(t['entry_time']), "%Y-%m-%d %H:%M:%S").date()
            if t_date == dia_dt:
                day_trades.append(t)
        
        # Métricas do dia
        pnl_dia = sum(t['pnl_fin'] for t in day_trades)
        lucro_compra = sum(t['pnl_fin'] for t in day_trades if t['side'] == 'buy' and t['pnl_fin'] > 0)
        lucro_venda = sum(t['pnl_fin'] for t in day_trades if t['side'] == 'sell' and t['pnl_fin'] > 0)
        # Prejuízo (Gross Loss)
        loss_dia = sum(t['pnl_fin'] for t in day_trades if t['pnl_fin'] < 0)
        
        # Oportunidades Perdidas (Shadow Trading)
        # Vamos usar a métrica de vetos por confiança como proxy de "Oportunidade Perdida"
        # que o usuário quer saber (quantas vezes a IA barrou algo que poderia ser bom)
        opt_perdidas = bt.shadow_signals.get('total_missed', 0)
        vetos = sum(bt.shadow_signals.get('veto_reasons', {}).values())

        print(f"{dia_str:<10} | {pnl_dia:>8.2f} | {lucro_compra:>8.2f} | {lucro_venda:>8.2f} | {abs(loss_dia):>8.2f} | {opt_perdidas:^10}")
        
        resultados_diarios.append({
            "data": dia_str,
            "pnl": pnl_dia,
            "lucro_compra": lucro_compra,
            "lucro_venda": lucro_venda,
            "prejuizo": loss_dia,
            "oportunidades_perdidas": opt_perdidas,
            "vetos": vetos
        })
        
        consolidado["pnl_total"] += pnl_dia
        consolidado["total_compra"] += lucro_compra
        consolidado["total_venda"] += lucro_venda
        consolidado["total_prejuizo"] += loss_dia
        consolidado["oportunidades_perdidas"] += opt_perdidas
        consolidado["vetos_totais"] += vetos

    print("-" * 70)
    print(f"📊 RESUMO CONSOLIDADO:")
    print(f"   PnL Líquido: R$ {consolidado['pnl_total']:.2f}")
    print(f"   Gross Profit (C+V): R$ {consolidado['total_compra'] + consolidado['total_venda']:.2f}")
    print(f"   Gross Loss: R$ {abs(consolidado['total_prejuizo']):.2f}")
    print(f"   Oportunidades Perdidas (Vetos): {consolidado['oportunidades_perdidas']}")

    # Salva relatório para análise detalhada
    with open("backend/audit_expert_bi_v15_results.json", "w") as f:
        json.dump({"consolidado": consolidado, "detalhes": resultados_diarios}, f, indent=4)

if __name__ == "__main__":
    asyncio.run(run_expert_bi_audit())
