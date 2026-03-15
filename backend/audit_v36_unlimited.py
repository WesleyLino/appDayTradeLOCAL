import os
import json
import asyncio
from datetime import datetime
import logging

# Adiciona diretório raiz ao path para importar backend
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro

# Configuração de Logs - Silencioso para máxima performance
logging.basicConfig(level=logging.ERROR, format="%(message)s")


async def run_audit_unlimited_optimized():
    dias = [
        "2026-02-19",
        "2026-02-20",
        "2026-02-23",
        "2026-02-24",
        "2026-02-25",
        "2026-02-26",
        "2026-02-27",
        "2026-03-02",
        "2026-03-03",
        "2026-03-04",
        "2026-03-05",
        "2026-03-06",
        "2026-03-09",
        "2026-03-10",
        "2026-03-11",
    ]

    # CONFIGURAÇÃO DE FILTROS TOTALMENTE ABERTOS
    v36_open = {
        "confidence_buy_threshold": 50.1,  # Abertura quase absoluta
        "confidence_sell_threshold": 49.9,  # Abertura quase absoluta
        "uncertainty_threshold_base": 0.99,  # Desativa trava de incerteza da IA
        "volatility_pause_threshold": 5000.0,  # Desativa trava de volatilidade (ATR)
        "daily_trade_limit": 100,  # Remove limite prático de trades
        "use_h1_trend_bias": False,  # DESATIVA BIAS H1 (Totalmente aberto)
        "use_anti_exhaustion": False,  # NOVO TOGGLE: DESATIVA ANTI-EXHAUSTION
        "use_anti_trap": False,  # NOVO TOGGLE: DESATIVA ANTI-TRAP
        "use_confidence_filter": False,  # NOVO TOGGLE: DESATIVA FILTRO DE CONFIANÇA
        "use_opening_range_filter": False,  # DESATIVA FILTRO DE ABERTURA
        "base_lot": 3,  # 3 contratos conforme solicitado
        "use_ai_core": True,
        "aggressive_mode": True,
        "sl_dist": 300.0,  # Stop largo para ver o potencial bruto sem ser estopado no ruído
        "tp_dist": 500.0,  # Alvos longos
    }

    print("📥 Coletando e Filtrando dados (Início: 19/02/2026)...")
    bt_loader = BacktestPro(symbol="WIN$", n_candles=10000)
    data_raw = await bt_loader.load_data()

    if data_raw is None or data_raw.empty:
        print("❌ Falha na coleta.")
        return

    # Sincroniza o fuso se necessário e corta o período exato para acelerar
    start_date = datetime(2026, 2, 18)  # Um dia antes para indicadores carregarem
    data_full = data_raw[data_raw.index >= start_date]

    resultados = []
    totais = {"pnl": 0.0, "trades": 0, "win_rate": 0.0}

    print("\n🚀 TESTE ILIMITADO V36 - POTENCIAL BRUTO (19/02 - 11/03)")
    print(f"{'Data':<12} | {'PnL Total':<10} | {'Trades':<6} | {'Status'}")
    print("-" * 50)

    for dia_str in dias:
        dia_dt = datetime.strptime(dia_str, "%Y-%m-%d").date()
        mask = data_full.index.date <= dia_dt
        data_slice = data_full.loc[mask]

        if data_slice.empty:
            continue

        bt = BacktestPro(symbol="WIN$")
        bt.initial_balance = 3000.0
        bt.balance = 3000.0
        bt.opt_params.update(v36_open)
        bt.data = data_slice

        res = await bt.run()

        day_trades = [
            t
            for t in res["trades"]
            if (
                t["entry_time"].date()
                if hasattr(t["entry_time"], "date")
                else datetime.strptime(str(t["entry_time"]), "%Y-%m-%d %H:%M:%S").date()
            )
            == dia_dt
        ]

        p_dia = sum(t["pnl_fin"] for t in day_trades)
        status = (
            "🔥" if p_dia > 100 else "✅" if p_dia > 0 else "🛑" if p_dia < 0 else "─"
        )

        print(f"{dia_str:<12} | R$ {p_dia:>8.2f} | {len(day_trades):^6} | {status}")

        resultados.append({"data": dia_str, "pnl": p_dia, "trades": len(day_trades)})
        totais["pnl"] += p_dia
        totais["trades"] += len(day_trades)

    print("-" * 50)
    print("📊 CONSOLIDADO ILIMITADO:")
    print("   >>> Capital Inicial: R$ 3.000,00")
    print(
        f"   >>> PnL Bruto Total: R$ {totais['pnl']:.2f} ({(totais['pnl'] / 3000) * 100:.1f}%)"
    )
    print(f"   >>> Performance Hoje (11/03): R$ {resultados[-1]['pnl']:.2f}")

    with open("backend/audit_v36_unlimited_results.json", "w") as f:
        json.dump({"totais": totais, "detalhes": resultados}, f, indent=4)


if __name__ == "__main__":
    asyncio.run(run_audit_unlimited_optimized())
