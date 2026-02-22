import asyncio
import json
import os
import sys
from datetime import datetime

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def run_1day_micro_test():
    print("📈 Iniciando Audit MT5 de 1 Dia: 1 Contrato / Cap R$ 1000")
    print("🚀 Foco: Verificação ultra-recente (Micro-Micro) com a estratégia SOTA.")
    
    params_path = "best_params_WIN.json"
    if not os.path.exists(params_path):
        print(f"❌ Erro: {params_path} não encontrado.")
        return

    with open(params_path, 'r') as f:
        config = json.load(f)
    params = config['params']
    
    # Parâmetros solicitados pelo usuário
    params['start_time'] = "10:00"
    params['end_time'] = "15:00" 
    params['aggressive_mode'] = True 
    
    # ~500 candles M1 cobrem um dia operacional Sniper (10h-15h + margem indicadores)
    backtester = BacktestPro(
        symbol="WIN$", 
        n_candles=600,
        initial_balance=1000.0,
        use_trailing_stop=True,
        use_flux_filter=True,
        dynamic_lot=False, # 1 CONTRATO FIXO
        **params
    )
    
    await backtester.run()
    
    print("\n=== RESUMO 1 DIA (1 LOTE) ===")
    print(f"Saldo Final: R$ {backtester.balance:.2f}")
    if len(backtester.trades) > 0:
        profit_total = backtester.balance - 1000.0
        print(f"Lucro Líquido: R$ {profit_total:.2f}")
        print(f"Total de Trades: {len(backtester.trades)}")
        
        win_trades = [t for t in backtester.trades if t['pnl_fin'] > 0]
        loss_trades = [t for t in backtester.trades if t['pnl_fin'] < 0]
        be_trades = [t for t in backtester.trades if t['pnl_fin'] == 0]
        
        print(f"Vitórias: {len(win_trades)} | Derrotas: {len(loss_trades)} | BE: {len(be_trades)}")
        print(f"Oportunidades Ignoradas (Prob 70-85%): {backtester.missed_signals}")
    else:
        print("Nenhum trade realizado no pregão mais recente.")
    
    print("\n=== LISTAGEM DE TRADES (DETALHADA) ===")
    for t in backtester.trades:
        print(f"Saída: {t['exit_time'].strftime('%H:%M:%S')} | Side: {t['side']} | Pts: {t['pnl_points']:.1f} | R$: {t['pnl_fin']:.2f} | Motivo: {t['reason']}")
    
    print("\n✅ Auditoria de 1 Dia Concluída.")

if __name__ == "__main__":
    asyncio.run(run_1day_micro_test())
