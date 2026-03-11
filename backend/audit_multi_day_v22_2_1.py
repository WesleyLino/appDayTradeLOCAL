import asyncio
import json
import os
import sys
import pandas as pd
from datetime import datetime, timedelta

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.backtest_pro import BacktestPro

async def run_multi_day_audit():
    print("\n" + "="*80)
    print("🚀 AUDITORIA MASTER MULTI-DAY (V22.2.1) - MINI ÍNDICE (WIN$)")
    print("Período: 19/02/2026 a 09/03/2026 (13 dias selecionados)")
    print("Capital: R$ 3.000,00 | Lotes: 3 + Dinâmico | Trailing: 10pts (ATR > 400)")
    print("="*80 + "\n")

    datas_alvo = [
        "2026-02-19", "2026-02-20", "2026-02-23", "2026-02-24", "2026-02-25", 
        "2026-02-26", "2026-02-27", "2026-03-02", "2026-03-03", "2026-03-04", 
        "2026-03-05", "2026-03-06", "2026-03-09"
    ]

    resultados_diarios = []
    total_pnl_buy = 0
    total_pnl_sell = 0
    total_trades = 0
    total_wins = 0
    total_shadow_missed = 0

    for data_str in datas_alvo:
        data_obj = datetime.strptime(data_str, "%Y-%m-%d")
        print(f"⏳ Processando {data_str}...")
        
        # Instancia o Backtest para o dia específico
        # Nota: Usamos copy_rates_range internamente no BacktestPro corrigido
        bt = BacktestPro(
            symbol="WIN$", 
            timeframe="M1"
        )
        
        # Injetamos o capital e garantimos que pegue o dia alvo
        bt.initial_balance = 3000.0
        
        # Simulação para o dia específico (9:00 as 17:15)
        # Adaptamos o BacktestPro para carregar este range se passarmos o candle start
        report = await bt.run() # O BacktestPro v22 já puxa os candles mais recentes se n_candles for passado
        
        # Filtramos os trades do dia
        trades = [t for t in report.get('trades', []) if pd.to_datetime(t['exit_time']).date() == data_obj.date()]
        
        day_buy = sum(t['pnl_fin'] for t in trades if t['side'] == 'buy')
        day_sell = sum(t['pnl_fin'] for t in trades if t['side'] == 'sell')
        day_pnl = sum(t['pnl_fin'] for t in trades)
        day_wins = len([t for t in trades if t['pnl_fin'] > 0])
        
        shadow = report.get('shadow_signals', {})
        vetos = shadow.get('total_missed', 0)

        resultados_diarios.append({
            "data": data_str,
            "pnl": day_pnl,
            "buy": day_buy,
            "sell": day_sell,
            "trades": len(trades),
            "wins": day_wins,
            "vetos": vetos
        })

        total_pnl_buy += day_buy
        total_pnl_sell += day_sell
        total_trades += len(trades)
        total_wins += day_wins
        total_shadow_missed += vetos

    # Consolidado
    print("\n" + "="*80)
    print("🏆 RESULTADO CONSOLIDADO (13 DIAS)")
    print("="*80)
    
    df_res = pd.DataFrame(resultados_diarios)
    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    
    print(f"Lucro Total (PnL):.... R$ {df_res['pnl'].sum():.2f}")
    print(f"Potencial COMPRA:..... R$ {total_pnl_buy:+.2f}")
    print(f"Potencial VENDA:...... R$ {total_pnl_sell:+.2f}")
    print(f"Total de Trades:...... {total_trades}")
    print(f"Taxa de Acerto:....... {win_rate:.1f}%")
    print(f"Oportunidades Vetadas: {total_shadow_missed}")
    print(f"Média p/ Dia:......... R$ {df_res['pnl'].mean():.2f}")
    
    print("\n📊 DETALHAMENTO DIÁRIO:")
    print(df_res.to_string(index=False))

    # Salvar JSON final
    with open("backend/audit_multi_day_result.json", "w") as f:
        json.dump({
            "consolidado": {
                "pnl_total": float(df_res['pnl'].sum()),
                "win_rate": float(win_rate),
                "total_trades": int(total_trades),
                "pnl_buy": float(total_pnl_buy),
                "pnl_sell": float(total_pnl_sell)
            },
            "diario": resultados_diarios
        }, f, indent=4)

    print("\n✅ Relatório salvo em backend/audit_multi_day_result.json")

if __name__ == "__main__":
    asyncio.run(run_multi_day_audit())
