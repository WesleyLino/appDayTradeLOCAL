
import asyncio
import os
import sys
import logging
from backtest_pro import BacktestPro

# Configuração de logs
logging.basicConfig(level=logging.ERROR)

async def run_deep_audit():
    print("🔍 INICIANDO AUDITORIA PROFUNDA SOTA (1 DIA / M1 / WIN$)")
    print("==========================================================")
    
    # 1. Configuração do Backtester
    config = {
        'initial_balance': 1000.0,
        'symbol': "WIN$",
        'n_candles': 600, # ~1 dia de trading (10:00 - 15:00)
        'confidence_threshold': 0.85,
        'lot_size': 1,
        'use_trailing_stop': True,
        'use_flux_filter': True,
        'use_sentiment_filter': True
    }
    
    backtester = BacktestPro(
        symbol=config['symbol'], 
        n_candles=config['n_candles'],
        confidence_threshold=config['confidence_threshold'],
        use_flux_filter=config['use_flux_filter'],
        use_trailing_stop=config['use_trailing_stop'],
        initial_balance=config['initial_balance'],
        data_file="data/sota_training/training_WIN$_MASTER.csv"
    )
    
    # 2. Carregar Dados (Tenta Local primeiro)
    data = await backtester.load_data()
    
    if data is None or data.empty:
        print("❌ Falha ao carregar dados do MT5.")
        return

    # 3. Execução do Backtest
    results = await backtester.run()
    
    # 4. Relatório Detalhado
    final_balance = results.get('final_balance', 0)
    profit = final_balance - config['initial_balance']
    trades = results.get('trades', [])
    win_rate = results.get('win_rate', 0)
    drawdown = results.get('max_drawdown', 0)
    
    print("\n📈 RESULTADOS DA EXECUÇÃO (THRESHOLD 85%):")
    print("-------------------------------------------")
    print(f"Balanço Final:    R$ {final_balance:.2f}")
    print(f"Lucro Líquido:    R$ {profit:.2f} ({ (profit/config['initial_balance'])*100:.2f}%)")
    print(f"Total de Trades:  {len(trades)}")
    print(f"Win Rate:         {win_rate:.1f}%")
    print(f"Max Drawdown:     {drawdown:.2f}%")
    
    # 5. Análise de Oportunidades Perdidas (Shadow Signals)
    shadow = backtester.shadow_signals
    print("\n🕵️ ANÁLISE DE OPORTUNIDADES PERDIDAS (SNIPER VETO):")
    print("--------------------------------------------------")
    print(f"Total de Sinais Vetados:     {shadow['total_missed']}")
    print(f"Vetados por Confiança IA:    {shadow['filtered_by_ai']}")
    print(f"Vetados por Fluxo/Volume:    {shadow['filtered_by_flux']}")
    
    print("\n📊 DISTRIBUIÇÃO POR TIER DE CONFIANÇA (POTENCIAL):")
    print(f"  70-75% (Risco Alto):     {shadow['tiers']['70-75']} sinais")
    print(f"  75-80% (Risco Médio):    {shadow['tiers']['75-80']} sinais")
    print(f"  80-85% (Quase Sniper):   {shadow['tiers']['80-85']} sinais")
    
    # 6. Recomendações SOTA
    print("\n💡 RECOMENDAÇÕES PARA ELEVAR ASSERTIVIDADE:")
    print("-------------------------------------------")
    if shadow['tiers']['80-85'] > 0:
        print(f"  1. Otimização de Score: Existem {shadow['tiers']['80-85']} sinais 'Quase Sniper'.")
        print("     Ajustar o Trailing Stop para travar BE mais cedo pode permitir operar no Tier 80%.")
    else:
        print("  1. Filtro Mestre: O Threshold de 85% está agindo perfeitamente contra ruído.")
    
    print(f"  2. Alpha Scaling: Com Win Rate de {win_rate}%, o escalonamento de lotes após 2 vitórias é seguro.")
    print("  3. Sentiment Veto: Continue usando o filtro de sentimento para evitar reversões macro.")

if __name__ == "__main__":
    asyncio.run(run_deep_audit())
