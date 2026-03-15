import asyncio
import logging
from datetime import datetime
from backend.mt5_bridge import MT5Bridge
from backend.backtest_pro import BacktestPro
import MetaTrader5 as mt5
import os
import json

# Configuração de Logs
logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")


async def run_audit():
    bridge = MT5Bridge()
    if not bridge.connect():
        print("❌ ERRO: Falha ao conectar ao Terminal MetaTrader 5.")
        return

    # Período de Teste: 25/02/2026 (Hoje na simulação)
    today = datetime(2026, 2, 25)
    symbol = "WIN$N"
    date_from = today.replace(hour=8, minute=0, second=0)
    date_to = today.replace(hour=18, minute=30, second=0)

    print("\n" + "=" * 60)
    print("🚀 VALIDAÇÃO FINAL SOTA V3: 25/02/2026 | CAPITAL: R$ 3.000,00")
    print("🔧 Melhorias: High Gain Params + Dynamic Regime Targets")
    print("=" * 60)

    # Coleta de dados
    print(f"📥 Coletando dados históricos M1 para {symbol}...")
    data = bridge.get_market_data_range(symbol, mt5.TIMEFRAME_M1, date_from, date_to)

    if data is None or data.empty:
        print("❌ ERRO: Não foi possível obter dados.")
        bridge.disconnect()
        return

    # 1. Carregar Parâmetros High Gain
    hp_path = os.path.join("backend", "high_gain_parameters.json")
    hp = {}
    if os.path.exists(hp_path):
        with open(hp_path, "r") as f:
            hp = json.load(f)

    # 2. Configuração SOTA V3 (PRO-MAX)
    print("\n[TESTE] 💎 MODO: SOTA V3 (GOLDEN CALIBRATION)")
    back_sota = BacktestPro(symbol=symbol, initial_balance=3000.0, use_ai_core=True)
    # Aplicar calibração de elite
    back_sota.ai.uncertainty_threshold_base = hp.get("threshold", 0.15)
    back_sota.ai.lot_multiplier_partial = hp.get("multiplier", 0.25)

    back_sota.data = data.copy()
    results = await back_sota.run()

    # RESULTADOS
    print("\n" + "=" * 60)
    print("📊 RESULTADO FINAL SOTA V3")
    print("-" * 60)
    print(f"LUCRO LÍQUIDO: R$ {results['total_pnl']:>10.2f}")
    print(f"WIN RATE:      {results['win_rate']:>10.1f}%")
    print(f"PROFIT FACTOR: {results['profit_factor']:>10.2f}")
    print(f"MAX DRAWDOWN:  {results['max_drawdown']:>10.2f}%")
    print(f"TOTAL TRADES:  {len(results['trades']):>10}")
    print("=" * 60)

    bridge.disconnect()


if __name__ == "__main__":
    asyncio.run(run_audit())
