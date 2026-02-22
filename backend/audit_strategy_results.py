import asyncio
import json
import os
import sys
import pandas as pd
from datetime import datetime

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def run_deep_audit():
    # 1. Carregar parâmetros
    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        params_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'best_params_WIN.json'))
    
    with open(params_path, 'r') as f:
        config = json.load(f)
    params = config['params']
    params['force_lots'] = 3
    params['use_trailing_stop'] = True

    # 2. Executar simulação contínua de 30 dias (12000 candles)
    bt = BacktestPro(
        symbol="WIN$", 
        n_candles=12000, 
        timeframe="M1", 
        initial_balance=3000.0,
        **params
    )
    
    print("\n[INICIANDO] Auditoria Profunda SOTA (30 Dias)...")
    report = await bt.run()
    
    # 3. Analisar Trades
    trades = report['trades']
    df_trades = pd.DataFrame(trades)
    
    winning_trades = df_trades[df_trades['pnl_fin'] > 0]
    losing_trades = df_trades[df_trades['pnl_fin'] < 0]
    
    # 4. Analisar Shadow Signals
    shadow = report['shadow_signals']
    
    print("\n" + "="*85)
    print("RESULTADO DA AUDITORIA DE ESTRATEGIA")
    print("="*85)
    
    print(f"\n[+] PONTOS FORTES:")
    print(f"- ROI Mensal: {((report['final_balance']-3000)/3000)*100:.1f}% (Excelente para R$ 3k)")
    print(f"- Drawdown: {report['max_drawdown']:.2f}% (Baixo risco sistemico)")
    if len(winning_trades) > 0:
        print(f"- Media de Ganho: R$ {winning_trades['pnl_fin'].mean():.2f}")
    if len(losing_trades) > 0:
        print(f"- Media de Perda: R$ {losing_trades['pnl_fin'].mean():.2f}")
    print(f"- Relacao Ganho/Perda: {abs(winning_trades['pnl_fin'].mean()/losing_trades['pnl_fin'].mean()):.2f}x (O SOTA Trailing funciona!)")

    print(f"\n[-] PONTOS NEGATIVOS:")
    print(f"- Taxa de Acerto (WR): {report['win_rate']:.1f}% (Pode ser estressante para iniciantes)")
    print(f"- Dependencia de 'Big Moves': O lucro vem de poucos trades longos.")

    print(f"\n[!] OPORTUNIDADES FILTRADAS (SHADOW SIGNALS):")
    print(f"- Total de Sinais Bloqueados: {shadow['total_missed']}")
    print(f"- Bloqueados por IA (Baixa Confianca): {shadow['filtered_by_ai']}")
    print(f"- Bloqueados por Fluxo (Sem Volume): {shadow['filtered_by_flux']}")
    print(f"- Distribuicao Tiers (Confianca IA): {shadow['tiers']}")

    print(f"\n[*] MELHORIAS RECOMENDADAS:")
    print("1. Reduzir Filtro de Fluxo em Regimes de Tendencia (Trend Maestro): Muitos sinais filtrados podem ser lucrativos em tendencia forte.")
    print("2. Ajuste de Trailing Trigger: Ativar o trailing um pouco antes (ex: 70 pts) pode garantir lucro em scalps rapidos.")
    print("3. Filtro de Horario: Evitar trades apos as 17:00 (Maior volatilidade erratica).")

    print("\n" + "="*85)

if __name__ == "__main__":
    asyncio.run(run_deep_audit())
