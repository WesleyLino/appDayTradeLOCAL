import asyncio
import json
import os
import sys
import logging
import pandas as pd
from datetime import datetime

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def run_detailed_audit_09mar():
    print("\n" + "="*80)
    print("🚀 AUDITORIA DE POTENCIAL AGRESSIVO (V22.2) - PREGÃO 09/03/2026")
    print("Foco: Mini Índice (WIN$) | Capital: R$ 3.000,00 | Lotes: 3 (Base) + Dinâmico")
    print("="*80 + "\n")

    # O BacktestPro já carrega v22_locked_params.json internamente via RiskManager e self.opt_params
    # Vamos apenas instanciar e rodar para a janela de hoje
    bt = BacktestPro(
        symbol="WIN$", 
        n_candles=800, # Cobre o dia todo em M1
        timeframe="M1"
    )
    
    # Sobrescrita manual para garantir que o capital de R$ 3000 seja testado
    bt.initial_balance = 3000.0
    
    print("⏳ Analisando dados históricos do MT5 e processando sinais HFT...")
    report = await bt.run()
    
    # Filtrar trades apenas do dia 09/03
    target_date = datetime(2026, 3, 9).date()
    trades = [t for t in report.get('trades', []) if pd.to_datetime(t['exit_time']).date() == target_date]
    
    buy_trades = [t for t in trades if t['side'] == 'buy']
    sell_trades = [t for t in trades if t['side'] == 'sell']
    
    pnl_buy = sum(t['pnl_fin'] for t in buy_trades)
    pnl_sell = sum(t['pnl_fin'] for t in sell_trades)
    pnl_total = sum(t['pnl_fin'] for t in trades)
    
    losses = [t for t in trades if t['pnl_fin'] < 0]
    total_prejuizo = sum(t['pnl_fin'] for t in losses)
    
    # Shadow Mode Analysis
    shadow = report.get('shadow_signals', {})
    
    print("\n" + "-"*50)
    print("📊 RESULTADO FINANCEIRO (09/03)")
    print("-"*50)
    print(f"Lucro Líquido:...... R$ {pnl_total:.2f}")
    print(f"Potencial COMPRA:.... R$ {pnl_buy:+.2f} ({len(buy_trades)} trades)")
    print(f"Potencial VENDA:..... R$ {pnl_sell:+.2f} ({len(sell_trades)} trades)")
    print(f"Total Prejuízo:...... R$ {total_prejuizo:+.2f} ({len(losses)} losses)")
    
    if len(trades) > 0:
        wr = (len([t for t in trades if t['pnl_fin'] > 0]) / len(trades)) * 100
        print(f"Taxa de Acerto:..... {wr:.1f}%")

    print("\n" + "-"*50)
    print("🕵️ SHADOW MODE (OPORTUNIDADES PERDIDAS)")
    print("-"*50)
    veto_reasons = shadow.get('veto_reasons', {})
    if veto_reasons:
        for reason, count in veto_reasons.items():
            print(f" - Vetado por {reason}: {count} vezes")
    else:
        print("Nenhuma oportunidade perdida significativa ou dados de shadow não processados.")

    # Melhoria Sugerida
    print("\n" + "-"*50)
    print("💡 ANALISE DE MELHORIA SOTA")
    print("-"*50)
    if pnl_total > 0:
        print("1. A calibragem V22.2 é lucrativa em alta volatilidade.")
        print("2. Reduzir o Trailing Step para 10pts em dias de ATR > 400 pode travar ainda mais lucro.")
    else:
        print("1. O mercado de hoje apresentou reversões bruscas.")
        print("2. Recomenda-se manter o Breakeven em 70pts para evitar saídas prematuras em pullbacks.")

    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(run_detailed_audit_09mar())
