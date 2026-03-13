import pandas as pd
import numpy as np
import os
import json
import asyncio
from datetime import datetime, timedelta
import logging

# Adiciona diretório raiz ao path para importar backend
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

# Configuração de Logs - Silencioso para não poluir
logging.basicConfig(level=logging.WARNING, format='%(message)s')

async def run_final_audit_expert():
    # Datas solicitadas para auditoria V36 Expert
    dias = [
        "2026-02-19", "2026-02-20", "2026-02-23", "2026-02-24", "2026-02-25", 
        "2026-02-26", "2026-02-27", "2026-03-02", "2026-03-03", "2026-03-04", 
        "2026-03-05", "2026-03-06", "2026-03-09", "2026-03-10", "2026-03-11"
    ]

    # Configuração V36 EXPERT CONSOLIDADA (SOTA-CALIBRATED)
    expert_config = {
        'confidence_threshold': 0.55,     # Threshold base (ajustado por rigor direcional)
        'confidence_buy_threshold': 55.0,  # Legado
        'confidence_sell_threshold': 52.0, # Calibragem Estrita de Venda
        'daily_trade_limit': 15,          
        'base_lot': 1,                    # Modo Conservador Expert (Conforme Recomendação)
        'use_ai_core': True,
        'aggressive_mode': False,         # Desativa agressividade para foco em qualidade
        'sl_dist': 150.0,                 # Base (Será multiplicado pelo RegimeExpert)
        'tp_dist': 400.0                  # Base (Será multiplicado pelo RegimeExpert)
    }

    print("📥 Sincronizando dados históricos WIN$ para Auditoria Expert...")
    bt_loader = BacktestPro(symbol="WIN$", n_candles=15000)
    data_full = await bt_loader.load_data()
    
    if data_full is None or data_full.empty:
        print("❌ Falha na coleta de dados. Verifique o MT5.")
        return

    resultados = []
    totais = {"pnl": 0.0, "compra": 0.0, "venda": 0.0, "trades": 0, "drawdown_max": 0.0}
    current_peak = 3000.0

    print("\n🏆 VALIDAÇÃO FINAL V36 EXPERT - 15 DIAS")
    print(f"{'Data':<12} | {'Símbolo':<7} | {'PnL Total':<10} | {'Trades':<6} | {'Regime Med':<10} | {'Status'}")
    print("-" * 80)

    for dia_str in dias:
        dia_dt = datetime.strptime(dia_str, "%Y-%m-%d").date()
        
        mask = (data_full.index.date <= dia_dt)
        data_slice = data_full.loc[mask]
        
        if data_slice.empty: continue
            
        bt = BacktestPro(symbol="WIN$")
        bt.initial_balance = 3000.0
        bt.balance = 3000.0
        bt.opt_params.update(expert_config)
        bt.data = data_slice
        
        res = await bt.run()
        
        day_trades = []
        for t in res['trades']:
            t_date = t['entry_time'].date() if hasattr(t['entry_time'], 'date') else datetime.strptime(str(t['entry_time']), "%Y-%m-%d %H:%M:%S").date()
            if t_date == dia_dt:
                day_trades.append(t)
        
        p_dia = sum(t['pnl_fin'] for t in day_trades)
        c_dia = sum(t['pnl_fin'] for t in day_trades if t['side'] == 'buy')
        v_dia = sum(t['pnl_fin'] for t in day_trades if t['side'] == 'sell')
        
        # Detecta regime médio do dia (proxy)
        regimes_dia = data_slice.loc[data_slice.index.date == dia_dt, 'regime']
        avg_regime = regimes_dia.mode()[0] if not regimes_dia.empty else "N/A"
        regime_map = {0: "LATERAL", 1: "TEND", 2: "RUIDO"}
        regime_desc = regime_map.get(avg_regime, "N/A")

        status = "✅ GAIN" if p_dia > 0 else "🛑 LOSS" if p_dia < 0 else "─"
        print(f"{dia_str:<12} | {'WIN$':<7} | R$ {p_dia:>8.2f} | {len(day_trades):^6} | {regime_desc:^10} | {status}")
        
        resultados.append({
            "data": dia_str,
            "pnl": p_dia,
            "trades": len(day_trades),
            "regime": regime_desc
        })
        
        totais["pnl"] += p_dia
        totais["compra"] += c_dia
        totais["venda"] += v_dia
        totais["trades"] += len(day_trades)

    print("-" * 80)
    print("📊 CONSOLIDADO V36 EXPERT (1 Lote):")
    print(f"   >>> Capital Final Estimado: R$ {3000 + totais['pnl']:.2f}")
    print(f"   >>> PnL Acumulado: R$ {totais['pnl']:.2f}")
    print(f"   >>> Profit Factor Estimado: { (totais['compra'] + totais['venda']) / abs(min(-1, (totais['compra'] if totais['compra']<0 else 0) + (totais['venda'] if totais['venda']<0 else 0) )) :.2f}")
    print(f"   >>> Total de Trades: {totais['trades']}")

    with open("backend/audit_v36_expert_final.json", "w") as f:
        json.dump({"totais": totais, "detalhes": resultados}, f, indent=4)

if __name__ == "__main__":
    asyncio.run(run_final_audit_expert())
