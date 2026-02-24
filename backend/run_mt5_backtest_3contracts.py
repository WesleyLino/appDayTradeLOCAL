import asyncio
import logging
import pandas as pd
import os
import sys
from datetime import datetime, timedelta
import MetaTrader5 as mt5

# Adiciona o diretório atual ao path para garantir que pacotes locais sejam encontrados
sys.path.append(os.getcwd())

from backend.backtest_pro import BacktestPro

# Configuração de Logging
logging.basicConfig(level=logging.ERROR, format='%(message)s')

async def main():
    print("="*60)
    print("🚀 INICIANDO BACKTEST HI-FI (MT5) - 3 CONTRATOS (V22 GOLDEN)")
    print("="*60)
    
    SYMBOL = "WIN$"
    TIMEFRAME = "M1"
    CAPITAL = 3000.0
    BASE_LOT = 3
    
    # Coleta de dados de M1
    backtester = BacktestPro(
        symbol=SYMBOL, 
        n_candles=1500, # Aumentado para garantir dados de pré-abertura
        timeframe=TIMEFRAME,
        initial_balance=CAPITAL,
        base_lot=BASE_LOT
    )
    
    print(f"📥 Coletando dados reais de {SYMBOL} via MT5...")
    df = await backtester.load_data()
    
    if df is not None:
        # Filtra para o dia especifico (23/02/2026)
        target_day = "2026-02-23"
        df_filtered = df[df.index.strftime('%Y-%m-%d') == target_day].copy()
        
        if len(df_filtered) == 0:
            print(f"❌ Nenhum dado encontrado para o dia {target_day} no buffer carregado.")
            print(f"Data Range Disponível: {df.index.min()} a {df.index.max()}")
            return

        print(f"📊 Processando {len(df_filtered)} candles do dia {target_day}...")
        backtester.data = df_filtered
        
        # Executa a simulação
        try:
            results = await backtester.run()
        except Exception as e:
            print(f"❌ Erro durante a execução do backtest: {e}")
            return
        
        if not results or 'total_pnl' not in results:
            print("❌ Backtest não gerou resultados válidos (provavelmente sem trades).")
            return

        # Cálculo manual de métricas faltantes
        final_balance = results.get('final_balance', CAPITAL)
        total_pnl = results.get('total_pnl', 0.0)
        return_pct = (total_pnl / CAPITAL) * 100
        
        # Relatório Final Consolidado
        print("\n" + "="*60)
        print("🏆 RESULTADOS CONSOLIDADOS (3 CONTRATOS)")
        print("="*60)
        print(f"💰 Capital Alocado: R$ {CAPITAL:.2f}")
        print(f"📈 Lucro Bruto:     R$ {total_pnl:.2f}")
        print(f"📊 Retorno ROI:      {return_pct:.2f}%")
        print(f"📉 Max Drawdown:    {results.get('max_drawdown', 0.0):.2f}%")
        print(f"🤝 Total Trades:    {len(results.get('trades', []))}")
        print(f"🎯 Win Rate:        {results.get('win_rate', 0.0):.1f}%")
        print(f"⚖️ Profit Factor:    {results.get('profit_factor', 0.0):.2f}")
        
        # Análise Shadow (Oportunidades)
        shadow = results.get('shadow_signals', {})
        print("\n" + "🔍 ANALISE DE FILTROS & OPORTUNIDADES")
        print("-" * 40)
        print(f"💡 Sinais Candidatos (V22):  {shadow.get('v22_candidates', 0)}")
        print(f"🚫 Filtro IA Confidência:     {shadow.get('filtered_by_ai', 0)}")
        print(f"🚫 Filtro Fluxo/Sentiment:   {shadow.get('filtered_by_flux', 0)}")
        print(f"✅ Sinais Executados:         {len(results.get('trades', []))}")
        
        print("\n" + "="*60)
        print("⚡ DIAGNÓSTICO DE POTENCIAL:")
        if total_pnl > 0:
            print(f"O uso de 3 contratos permitiu um ganho de R$ {total_pnl:.2f} em UM DIA.")
            print("A assertividade está equilibrada. Os filtros de fluxo estão sendo seletivos.")
        else:
            print("O dia foi lateral ou truncado. O 'cooldown' evitou maiores perdas.")
        print("="*60)

    else:
        print("❌ Falha na carga de dados.")

if __name__ == "__main__":
    asyncio.run(main())
