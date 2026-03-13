import asyncio
import pandas as pd
from backend.backtest_pro import BacktestPro
import logging

# Configuração de logging PT-BR
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def run_audit():
    # Parâmetros de 10/03 com v24.3
    params = {
        'force_lots': 10,
        'use_ai_core': True,
        'volatility_pause_threshold': 250.0,
        'volatility_scalability_threshold': 450.0,
        'reduced_lot_factor': 0.5,
        'momentum_bypass_threshold': 84.0,
        'vwap_dist_threshold': 400.0,
        'confidence_level': 0.6
    }
    
    days = [
        # ("10/03 (Volatilidade Extrema)", "backend/historico_WIN_10mar_warmup.csv"),
        ("11/03 (Tendência Normal)", "backend/historico_WIN_11mar_warmup.csv")
    ]
    
    for label, csv in days:
        print(f"\n🚀 EXECUTANDO AUDITORIA DINÂMICA v24.4: {label}")
        bt = BacktestPro(csv_path=csv, **params)
        await bt.run()
        report = bt.generate_report()
        
        vetos = report['shadow_signals'].get('veto_reasons', {})
        print(f"Saldo Final: R$ {report['final_balance']:.2f} | Lucro: R$ {report['total_pnl']:.2f}")
        print(f"Trades: {len(report['trades'])} | Win Rate: {report['win_rate']:.1f}%")
        print("Principais Vetos:")
        # Mostrar apenas os 2 principais vetos para brevidade
        sorted_vetos = sorted(vetos.items(), key=lambda x: x[1], reverse=True)[:2]
        for v, c in sorted_vetos:
            print(f" - {v}: {c}")
        print("-" * 30)



if __name__ == "__main__":
    asyncio.run(run_audit())
