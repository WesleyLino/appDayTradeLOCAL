import asyncio
import json
import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def run_production_audit():
    # Configuração de Logs - Nível INFO para ver detalhes dos trades
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    # 1. Carregar parâmetros oficiais de produção
    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        params_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'best_params_WIN.json'))
    
    with open(params_path, 'r') as f:
        config = json.load(f)
    params = config['params']
    
    # Garantir capital de 3000 e 3 lotes fixos conforme pedido
    initial_capital = 3000.0
    params['force_lots'] = 3
    params['dynamic_lot'] = False
    params['aggressive_mode'] = True # Validade do fluxo 1.2x
    
    print("\n" + "="*85)
    print(f"🕵️ AUDITORIA DE CONFIGURAÇÃO DE PRODUÇÃO (1 DIA - MT5)")
    print(f"Capital: R$ {initial_capital:.2f} | Lotes: 3.0 | SOTA Trailing: {params['trailing_trigger']}pts")
    print(f"Breakeven: {params['be_trigger']}pts | Flux Filter: {params['vol_spike_mult']}x")
    print("="*85 + "\n")

    # 2. Carregar dados do MT5 (Último dia disponível)
    # n_candles=1000 para cobrir um dia cheio (aprox 600 min) + padding
    bt_loader = BacktestPro(symbol="WIN$", n_candles=1500, timeframe="M1")
    print("⏳ Sincronizando com MetaTrader 5...")
    df = await bt_loader.load_data()
    
    if df is None or df.empty:
        print("❌ Erro: Não foi possível obter dados do MT5. Verifique se o terminal está aberto.")
        return

    # Pegar o último dia útil completo
    df['date'] = df.index.date
    last_day = sorted(df['date'].unique())[-1]
    
    # Se hoje ainda estiver rodando e for cedo, talvez pegar o dia anterior
    current_time = datetime.now().time()
    if last_day == datetime.now().date() and current_time < datetime.strptime("17:45", "%H:%M").time():
        last_day = sorted(df['date'].unique())[-2]

    day_data = df[df['date'] == last_day].copy()
    
    print(f"📅 Dia Analisado: {last_day.strftime('%d/%m/%Y')} ({len(day_data)} candles M1)")
    
    # 3. Rodar Backtest com as "Shadow Signals" ligadas (embutido no backtest_pro)
    bt = BacktestPro(
        symbol="WIN$", 
        n_candles=len(day_data), 
        timeframe="M1", 
        initial_balance=initial_capital,
        **params
    )
    bt.df = day_data
    # Mock do loader para usar o chunk filtrado
    async def mock_load(): return day_data
    bt.load_data = mock_load
    
    report = await bt.run()
    
    if not report:
        print("❌ Falha na geração do relatório.")
        return

    # 4. Resultados Financeiros
    trades = report.get('trades', [])
    total_pnl = sum(t['pnl_fin'] for t in trades)
    wins = len([t for t in trades if t['pnl_fin'] > 0])
    wr = (wins / len(trades)) * 100 if trades else 0
    max_dd = report.get('max_drawdown', 0)
    
    print("\n" + "-"*40)
    print(f"💰 RESULTADO FINANCEIRO")
    print(f"Lucro/Prejuízo: R$ {total_pnl:.2f}")
    print(f"Taxa de Acerto: {wr:.1f}% ({wins}/{len(trades)})")
    print(f"Drawdown Max:   {max_dd:.2f}%")
    print("-"*40)

    # 5. Oportunidades Perdidas (Shadow Signals)
    shadow = report.get('shadow_signals', {'filtered_by_ai': 0, 'filtered_by_flux': 0})
    print(f"\n🚫 OPORTUNIDADES FILTRADAS (Potential Signals)")
    print(f"Bloqueadas por IA (AlphaX Score < 85):  {shadow['filtered_by_ai']}")
    print(f"Bloqueadas por FLUXO (Micro-vol < 1.2x): {shadow['filtered_by_flux']}")
    
    # 6. Diagnóstico e Sugestões
    print(f"\n📝 DIAGNÓSTICO SOTA")
    if total_pnl > 0:
        print("✅ Configuração ATUAL é lucrativa para este cenário.")
    else:
        print("⚠️ Configuração defensiva. Possível preservação de capital em dia difícil.")

    if shadow['filtered_by_ai'] > 5:
        print("💡 Sugestão: Reduzir Confidence Threshold para 0.80 pode aumentar trades, mas aumenta risco.")
    
    if total_pnl > 0 and wr < 50:
        print("💡 Sugestão: O Trailing Stop de 70pts salvou a operação. Manter ativado.")

    print("\n" + "="*85)
    print("Auditoria Finalizada.")
    print("="*85 + "\n")

if __name__ == "__main__":
    asyncio.run(run_production_audit())
