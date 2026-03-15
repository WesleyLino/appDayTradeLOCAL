import asyncio
import logging
import pandas as pd
from datetime import datetime
import sys
import os

# Adiciona diretório raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro
import MetaTrader5 as mt5


async def run_analysis():
    logging.info("🚀 Iniciando Simulação de Alta Fidelidade (Feb 23) - Mini Índice")

    # Configurações do Teste
    symbol = "WIN$"
    capital = 3000.0

    # 1. Coleta de Dados Históricos M1 para o dia 23/02
    if not mt5.initialize():
        logging.error("❌ Falha ao inicializar MT5")
        return

    # Definir range do dia 23/02
    utc_from = datetime(2026, 2, 23, 0, 0)
    utc_to = datetime(2026, 2, 23, 23, 59)

    logging.info(f"📥 Coletando dados M1 para {symbol} em {utc_from.date()}")
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, utc_from, utc_to)

    if rates is None or len(rates) == 0:
        logging.error("❌ Nenhum dado encontrado para o período.")
        mt5.shutdown()
        return

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)

    # Salvar temporariamente para o BacktestPro ler
    data_path = "backend/data_23feb_m1.csv"
    df.to_csv(data_path)
    logging.info(f"✅ {len(df)} velas salvas em {data_path}")

    # 2. Configurar BacktestPro
    tester = BacktestPro(
        symbol=symbol,
        data_file=data_path,
        initial_balance=capital,
        base_lot=1,
        dynamic_lot=False,
        use_ai_core=True,
    )

    # 3. Executar Simulação
    report = await tester.run()

    if report:
        # 4. Exibir Resultados no Console
        print("\n" + "=" * 50)
        print(f"📊 RELATÓRIO FINAL - {symbol} (23/02/2026)")
        print("=" * 50)
        print(f"Capital Inicial: R$ {capital:.2f}")
        print(f"Saldo Final:     R$ {report['final_balance']:.2f}")
        print(f"PnL Total:       R$ {report['total_pnl']:.2f}")
        print(f"Profit Factor:   {report['profit_factor']:.2f}")
        print(f"Win Rate:        {report['win_rate']:.1f}%")
        print(f"Trades Totais:   {len(report.get('trades', []))}")
        print(f"Max Drawdown:    {report['max_drawdown']:.2f}%")
        print("=" * 50)

        # Sugestões de Melhoria
        print("\n🔍 ANÁLISE DE OPORTUNIDADES:")
        shadow = report.get("shadow_signals", {})
        print(f"- Sinais Ignorados (Filtros): {shadow.get('total_missed', 0)}")
        print(f"  - Filtrados por IA (<85%): {shadow.get('filtered_by_ai', 0)}")
        print(f"  - Filtrados por Fluxo:      {shadow.get('filtered_by_flux', 0)}")
        print(f"  - Tiers de Confiança (70-85%): {shadow.get('tiers', {})}")

    mt5.shutdown()


if __name__ == "__main__":
    asyncio.run(run_analysis())
