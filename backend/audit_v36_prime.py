import asyncio
import logging
import json
import os
import sys
import pandas as pd
from datetime import datetime, timedelta

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro
from backend.ai_core import AICore

async def run_audit_prime():
    logging.info("🚀 INICIANDO AUDITORIA V36 PRIME (Alta Performance)")
    
    # 1. Configurar AI Core com Toggles de Expert Mode Ligados
    ai = AICore()
    ai.use_confidence_filter = True
    ai.use_anti_exhaustion = True
    ai.use_anti_trap = True
    
    # 2. Configurar Backtest (Periodo Fev-Mar 2026 - ~15 Dias)
    # 3 Contratos (Agressivo)
    bt = BacktestPro(
        symbol="WIN$",
        n_candles=15000, 
        ai_core=ai,
        base_lot=3,
        confidence_threshold=0.52, # Calibragem V36
        use_ai_core=True
    )

    logging.info("📥 Carregando dados via MT5/Cache...")
    await bt.run()

    # 3. Processar Resultados
    results = {
        "v36_prime_results": {
            "total_pnl": bt.balance - bt.initial_balance,
            "total_trades": len(bt.trades),
            "win_rate": sum(1 for t in bt.trades if t['pnl_fin'] > 0) / len(bt.trades) if bt.trades else 0,
            "max_drawdown": bt.max_drawdown,
            "shadow_stats": bt.shadow_signals
        }
    }

    output_path = "backend/audit_v36_prime_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)

    logging.info(f"✅ Auditoria Concluída! Resultado: R$ {results['v36_prime_results']['total_pnl']:.2f}")
    logging.info(f"📊 Relatório salvo em: {output_path}")

if __name__ == "__main__":
    asyncio.run(run_audit_prime())
