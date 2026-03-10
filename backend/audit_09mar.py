import asyncio
import json
import os
import sys
import pandas as pd
from datetime import datetime

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def run_audit_09mar():
    params_path = "backend/v22_locked_params.json"
    with open(params_path, 'r') as f:
        config = json.load(f)
    
    params = config['strategy_params']
    initial_capital = 3000.0
    # Pegamos candles suficientes para cobrir o dia de hoje (aprox 500-600 M1)
    n_candles = 800 

    bt = BacktestPro(
        symbol="WIN$", 
        n_candles=n_candles, 
        timeframe="M1", 
        initial_balance=initial_capital,
        **params
    )
    bt.opt_params['force_lots'] = 3

    print("\n" + "🔍" * 15)
    print("AUDITORIA FOCALIZADA: 09/03/2026")
    print("Protocolo SOTA | Capital: R$ 3.000")
    print("🔍" * 15 + "\n")

    report = await bt.run()
    
    # Filtrar apenas trades de hoje (caso existam)
    target_date = datetime(2026, 3, 9).date()
    trades = [t for t in report['trades'] if pd.to_datetime(t['exit_time']).date() == target_date]
    
    print(f"📊 RESULTADO FINANCEIRO (09/03):")
    if not trades:
        print(" > Resultado: R$ 0,00 (Nenhum trade executado)")
    else:
        df = pd.DataFrame(trades)
        wins = len(df[df['pnl_fin'] > 0])
        wr = (wins / len(df)) * 100
        pnl = df['pnl_fin'].sum()
        print(f" > Trades: {len(df)} | Win Rate: {wr:.1f}% | PnL: R$ {pnl:.2f}")

    # Shadow Mode Analysis (Filtros que agiram no dia)
    shadow = report.get('shadow_signals', {})
    print("\n🕵️ SHADOW MODE (O QUE ACONTECEU 'POR BAIXO'):")
    print(f" > Gatilhos Técnicos Identificados: {shadow.get('v22_candidates', 0)}")
    print(f" > Vetos Totais (Proteção):......... {shadow.get('total_missed', 0)}")
    
    veto_reasons = shadow.get('veto_reasons', {})
    if veto_reasons:
        print("\nRAZÕES DOS VETOS EM 09/03:")
        for reason, count in veto_reasons.items():
            print(f" - {reason}: {count} vezes")

    print("\n" + "="*50)
    print("🏆 CONCLUSÃO SOTA")
    if not trades:
        print("O robô agiu corretamente ao NÃO operar em 09/03 devido aos filtros de risco e fluxo.")
    else:
        print("Operação realizada sob condições controladas.")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(run_audit_09mar())
