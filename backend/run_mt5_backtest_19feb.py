import asyncio
import logging
import pandas as pd
from datetime import datetime
import sys
import os
import MetaTrader5 as mt5

# Adiciona diretorio raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_mt5_analysis_19feb():
    # Configuracao de Logs
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.info("INICIANDO ANALISE HISTORICA MT5 (19/02/2026)")

    symbol = "WIN$"
    capital = 3000.0

    # 1. Configurar Backtest
    tester = BacktestPro(
        symbol=symbol,
        n_candles=10000,  # Aumentado significativamente
        timeframe="M1",
        initial_balance=capital,
        base_lot=1,
        dynamic_lot=True,
        use_ai_core=False,
    )

    # Parametros otimizados
    tester.opt_params["vol_spike_mult"] = 1.0
    tester.opt_params["use_flux_filter"] = True
    tester.opt_params["confidence_threshold"] = 0.70

    # 2. Carregar dados do MT5 especificamente para o dia 19
    if not mt5.initialize():
        logging.error("Falha ao inicializar MT5")
        return

    target_date = datetime(2026, 2, 19)
    # Definindo range do pregão (09:00 as 18:00)
    utc_from = datetime(2026, 2, 19, 8, 0)  # Buffer inicio
    utc_to = datetime(2026, 2, 19, 18, 30)  # Buffer fim

    logging.info(f"Solicitando dados historicos para {target_date.date()}...")
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, utc_from, utc_to)

    if rates is None or len(rates) == 0:
        logging.error(
            f"Nao foi possivel obter dados para {target_date.date()}. Verifique se o ativo {symbol} esta no Market Watch."
        )
        mt5.shutdown()
        return

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)

    tester.data = df
    logging.info(f"Dados carregados: {len(df)} candles.")
    logging.info(f"Range de Datas: {df.index[0]} ate {df.index[-1]}")

    # 3. Executar Simulacao
    await tester.run()

    # 4. Relatorio de Performance e Oportunidades
    shadow = tester.shadow_signals
    trades = tester.trades

    print("\n" + "=" * 50)
    print(f"RELATORIO DE PERFORMANCE (MT5 DATA - {target_date.date()})")
    print("=" * 50)
    print(f"Saldo Inicial:   RS {capital:.2f}")
    print(f"Saldo Final:     RS {tester.balance:.2f}")
    print(f"PnL Total:       RS {tester.balance - capital:.2f}")
    print(f"Numero de Trades: {len(trades)}")

    if len(trades) > 0:
        win_rate = (len([t for t in trades if t["pnl_fin"] > 0]) / len(trades)) * 100
        print(f"Assertividade:   {win_rate:.2f}%")

    print("\nANALISE DE OPORTUNIDADES (SHADOW):")
    print(f"- Sinais V22 Detectados:      {shadow.get('v22_candidates', 0)}")
    print(
        f"- Sinais Enviados p/ Filtro:  {shadow.get('total_missed', 0) + len(trades)}"
    )
    print(f"- Negados pela IA:            {shadow.get('filtered_by_ai', 0)}")
    print(f"- Negados pelo Fluxo:         {shadow.get('filtered_by_flux', 0)}")
    print(f"- Falhas Componentes:         {shadow.get('component_fail', {})}")

    print("\n" + "=" * 50)
    mt5.shutdown()


if __name__ == "__main__":
    asyncio.run(run_mt5_analysis_19feb())
