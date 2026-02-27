import asyncio
import logging
import pandas as pd
from datetime import datetime
import sys
import os

# Adiciona diretorio raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from backend.backtest_pro import BacktestPro

async def detailed_audit():
    # Habilita logs detalhados para análise de auditoria
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    print(f"\n{'='*60}")
    print("AUDITORIA DETALHADA: PERFORMANCE WIN$ (19/02/2026)")
    print(f"{'='*60}")
    
    symbol = "WIN$"
    capital = 3000.0
    target_date = datetime(2026, 2, 19).date()

    configs = [
        {"name": "V22 GOLDEN (ORIGINAL)", "use_ai": True, "conf_thresh": 0.70, "flux_thresh": 1.2, "refine": False},
        {"name": "V22 + REFINAMENTO AI", "use_ai": True, "conf_thresh": 0.70, "flux_thresh": 1.2, "refine": True},
        {"name": "AGGRESSIVE (POTENTIAL)", "use_ai": True, "conf_thresh": 0.60, "flux_thresh": -1.0, "refine": True},
        {"name": "RAW (NO AI)", "use_ai": False, "conf_thresh": 0.0, "flux_thresh": -1.0, "refine": False}
    ]

    for cfg in configs:
        print(f"\n>>> TESTANDO CONFIGURAÇÃO: {cfg['name']}")
        tester = BacktestPro(
            symbol=symbol,
            n_candles=10000, # Aumentado para garantir que pegamos o dia 19/02 (hoje e 25/02)
            timeframe="M1",
            initial_balance=capital,
            base_lot=1,
            dynamic_lot=True,
            use_ai_core=cfg['use_ai']
        )
        tester.opt_params['confidence_threshold'] = cfg['conf_thresh']
        tester.opt_params['flux_imbalance_threshold'] = cfg['flux_thresh']
        
        # O BacktestPro usa o AICore interno. Se quisermos testar o refinamento, 
        # ele ja esta implementado no ai_core.py que o BacktestPro instancia.
        # No entanto, o AICore agora usa as novas regras por padrao.
        # Para comparar com o "Original", precisariamos de uma versao do AICore sem o refinamento,
        # ou desativar as flags de refinamento se tivessemos implementado flags.
        # Como as mudancas foram diretas no AICore, o "V22 GOLDEN" ja vai usar o refinamento
        # se o codigo foi alterado.
        
        tester.data = await tester.load_data()
        
        if tester.data is None or tester.data.empty:
            print(f"Erro: Falha ao carregar dados do MT5 para {symbol}.")
            continue
            
        tester.data = tester.data[tester.data.index.date == target_date]
        
        if tester.data.empty:
            print(f"Erro: Dados de {target_date} não encontrados na amostra.")
            continue
            
        await tester.run()
        
        trades = tester.trades
        shadow = tester.shadow_signals
        
        print(f"- PnL Final:       RS {tester.balance - capital:.2f}")
        print(f"- Total Trades:    {len(trades)}")
        print(f"- Sinais V22:      {shadow.get('v22_candidates', 0)}")
        print(f"- Vetos pela IA:   {shadow.get('filtered_by_ai', 0)}")
        print(f"- Vetos pelo Fluxo: {shadow.get('filtered_by_flux', 0)}")
        
        if len(trades) > 0:
            wins = len([t for t in trades if t['pnl_fin'] > 0])
            print(f"- Assertividade:   {(wins/len(trades))*100:.2f}%")
            print(f"- Maior Gain:      RS {max([t['pnl_fin'] for t in trades]):.2f}")
            print(f"- Maior Loss:      RS {min([t['pnl_fin'] for t in trades]):.2f}")
            
            if not cfg['use_ai']:
                print("\n>>> DETALHE TRADES RAW:")
                for t in trades:
                    print(f"  [{t['entry_time'].strftime('%H:%M')}] {t['side'].upper()} @ {t['entry']:.2f} -> {t['exit']:.2f} | PnL: RS {t['pnl_fin']:.2f} ({t['reason']})")
    
    print(f"\n{'='*60}")
    print("RESUMO DA AUDITORIA 19/02:")
    print("Análise do impacto do Refinamento de Assertividade em dia de alta volatilidade.")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    asyncio.run(detailed_audit())
