import asyncio
import logging
import os
import sys

# Adiciona diretório raiz
sys.path.append(os.getcwd())

from backend.backtest_pro import BacktestPro

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def run_diagnostic():
    # Testa o dia 24/02 que teve alto potencial bruto
    filepath = "backend/data_24_02_2026.csv"
    if not os.path.exists(filepath):
        print("❌ Arquivo 24/02 não encontrado.")
        return

    print(f"🧪 Iniciando Diagnóstico v50.1 para {filepath}...")
    # Configuração Relaxada para ver onde para
    tester = BacktestPro(
        symbol="WIN$",
        data_file=filepath,
        initial_balance=3000.0,
        use_ai_core=True,
        confidence_threshold=0.45,
        vwap_dist_threshold=500,
        vol_spike_mult=1.0,
        rsi_buy_level=40,
        rsi_sell_level=60,
    )

    await tester.run()
    shadow = tester.shadow_signals

    print("\n" + "=" * 80)
    print("🔬 RELATÓRIO DE DIAGNÓSTICO (POR QUE NÃO HÁ TRADES?)")
    print("=" * 80)
    print(f"Candidatos Técnicos (RSI/BB/Vol): {shadow.get('v22_candidates', 0)}")
    import json

    v_reasons = shadow.get("veto_reasons", {})
    c_fail = shadow.get("component_fail", {})
    print(f"Component Fail: {json.dumps(c_fail, indent=2)}")
    print(f"Motivos de Veto Detalhados: {json.dumps(v_reasons, indent=2)}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_diagnostic())
