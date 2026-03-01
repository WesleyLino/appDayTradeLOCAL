import sys
import os
import asyncio
import pandas as pd
from datetime import datetime
import logging

# Path setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from backtest_pro import BacktestPro

async def run_fevereiro_test():
    # Configuração solicitada
    target_dates = [
        "2026-02-19", "2026-02-20", "2026-02-23", 
        "2026-02-24", "2026-02-25", "2026-02-26", "2026-02-27"
    ]
    
    # Carrega Sentimento Simulado (Notícias)
    import json
    sentiment_file = "backend/fev_sentiment_sim.json"
    sentiment_data = {}
    if os.path.exists(sentiment_file):
        with open(sentiment_file, "r") as f:
            # Converte chaves de string para datetime para o backtest_pro
            raw_data = json.load(f)
            sentiment_data = {pd.to_datetime(k): v for k, v in raw_data.items()}

    # Inicializa Backtester Pro com CAPITAL de 3000 e modo Alpha ativado
    backtester = BacktestPro(
        symbol="WIN$", 
        n_candles=15000, # Pega histórico suficiente para cobrir os dias
        initial_balance=3000.0,
        use_ai_core=True,
        aggressive_mode=True,
        sentiment_stream=sentiment_data
    )
    
    # Reduz nível de log para focar no resultado
    logging.getLogger().setLevel(logging.WARNING)
    
    # 1. Carregar dados
    print("⏳ Carregando dados do MetaTrader 5 (WIN$ M1)...")
    data = await backtester.load_data()
    if data is None:
        print("❌ Erro ao carregar dados do MT5. Certifique-se de que o Terminal MT5 está aberto.")
        return
    
    # 2. Filtrar pelos dias solicitados
    data['date_str'] = data.index.strftime('%Y-%m-%d')
    filtered_data = data[data['date_str'].isin(target_dates)].copy()
    del filtered_data['date_str']
    
    if filtered_data.empty:
        print("❌ Nenhum dado encontrado para as datas solicitadas.")
        print(f"Datas disponíveis no histórico carregado: {data.index.min()} até {data.index.max()}")
        return

    print(f"✅ Dados Carregados: {len(filtered_data)} velas M1 ({len(target_dates)} dias úteis)")
    print("🚀 Iniciando Simulação Alpha (ATR 2.0 / Cooldown Dinâmico / Modo Mercado)...")
    
    # 3. Executar backtest
    backtester.data = filtered_data
    await backtester.run()
    
    # 4. Resultados Customizados (BUY vs SELL)
    backtester.generate_report()
    
    df_trades = pd.DataFrame(backtester.trades)
    print("\n" + "="*60)
    print("🏆 PERFORMANCE FINAL ALPHA V222 - FEVEREIRO/26")
    print("="*60)
    
    if not df_trades.empty:
        buys = df_trades[df_trades['side'] == 'buy']
        sells = df_trades[df_trades['side'] == 'sell']
        
        total_pnl = df_trades['pnl_fin'].sum()
        win_rate = (len(df_trades[df_trades['pnl_fin'] > 0]) / len(df_trades)) * 100
        
        print(f"Capital Inicial:  R$ {backtester.initial_balance:.2f}")
        print(f"Saldo Final:      R$ {backtester.balance:.2f}")
        print(f"Lucro Líquido:    R$ {total_pnl:.2f} ({ (total_pnl/backtester.initial_balance)*100:.1f}%)")
        print(f"Max Drawdown:     {backtester.max_drawdown*100:.2f}%")
        print("-" * 60)
        print(f"SINAIS DISPARADOS: {len(df_trades)} (WR: {win_rate:.1f}%)")
        print(f"  • COMPRAS: {len(buys)} trades | PnL: R$ {buys['pnl_fin'].sum():.2f} | WR: {(len(buys[buys['pnl_fin']>0])/len(buys)*100 if len(buys)>0 else 0):.1f}%")
        print(f"  • VENDAS:  {len(sells)} trades | PnL: R$ {sells['pnl_fin'].sum():.2f} | WR: {(len(sells[sells['pnl_fin']>0])/len(sells)*100 if len(sells)>0 else 0):.1f}%")
        
        print("\n🛡️ ANÁLISE DE OPORTUNIDADES FILTRADAS")
        print("-" * 60)
        print(f"Total de sinais vetados pela IA: {backtester.shadow_signals['total_missed']}")
        print(f"  • Motivo: Filtro de Convicção (Incerteza): {backtester.shadow_signals['filtered_by_ai']}")
        print(f"  • Motivo: Filtro de Fluxo/Volume:        {backtester.shadow_signals['filtered_by_flux']}")
        
        # Breakdown por confiança
        print("\n🔬 NÍVEIS DE CONFIANÇA DOS SINAIS FILTRADOS (LOST OPS):")
        for tier, count in backtester.shadow_signals['tiers'].items():
            print(f"  • Tier {tier}%: {count} oportunidades")
        
        print("\n💡 RECOMENDAÇÃO PARA ASSERTIVIDADE:")
        if win_rate < 50:
            print("  - Reduzir o multiplicador de ATR para 1.8 para saídas mais rápidas.")
            print("  - Aumentar o Score Mínimo de 85 para 90 para filtragem mais severa.")
        else:
            print("  - A configuração atual de 2.0 ATR está capturando bem as tendências.")
            print("  - Avaliar aumentar o Cooldown para 20 min se o Drawdown superar 10%.")
    else:
        print("⚠️ Nenhum trade realizado com os critérios atuais.")
        print(f"Sinais Vetados pela IA: {backtester.shadow_signals['total_missed']}")
    
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_fevereiro_test())
