import asyncio
import os
import sys

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_sniper_1day_test():
    """
    Executa um backtest de 1 dia (M1) focado na estratégia Sniper auditada.
    Configuração: WIN$, 10:00-12:00, Capital R$ 1000, Limite 3 trades.
    """

    # Parâmetros otimizados para o perfil Sniper Audited
    sniper_params = {
        "rsi_period": 9,
        "vol_spike_mult": 1.5,
        "sl_dist": 150.0,
        "tp_dist": 300.0,
        "start_time": "10:00",
        "end_time": "12:00",
        "daily_trade_limit": 3,
        "use_flux_filter": True,
        "flux_imbalance_threshold": 1.3,
        "aggressive_mode": False,
        "dynamic_lot": False,
    }

    initial_capital = 1000.0
    print(
        f"🚀 Iniciando TESTE SNIPER M1 (MT5 Data) | Range: 5 Dias | Capital: R$ {initial_capital:.2f}"
    )
    print("Propósito: Validar a robustez dos filtros auditados em dados recentes.")

    # 3000 candles em M1 cobrem ~5 dias úteis.
    bt = BacktestPro(
        symbol="WIN$",
        n_candles=3000,
        timeframe="M1",
        initial_balance=initial_capital,
        **sniper_params,
    )

    print("⏳ Coletando dados reais via MT5 Bridge e processando indicadores SOTA...")
    await bt.run()

    print("\n✅ Teste de 1 dia Sniper concluído.")


if __name__ == "__main__":
    asyncio.run(run_sniper_1day_test())
