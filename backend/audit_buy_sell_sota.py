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

async def run_deep_audit():
    # Carregar v22_locked_params.json (Golden Params)
    params_path = "backend/v22_locked_params.json"
    if not os.path.exists(params_path):
        # Fallback se rodar do root
        params_path = "backend/v22_locked_params.json"
    
    with open(params_path, 'r') as f:
        config = json.load(f)
    
    params = config['strategy_params']
    initial_capital = 3000.0
    n_candles = 12000 # ~30 dias

    bt = BacktestPro(
        symbol="WIN$", 
        n_candles=n_candles, 
        timeframe="M1", 
        initial_balance=initial_capital,
        **params
    )
    bt.opt_params['force_lots'] = 3

    print("\n" + "="*75)
    print("🕵️ AUDITORIA PROFUNDA SOTA 09/03 (COMPRA vs VENDA)")
    print(f"Capital: R$ {initial_capital:.2f} | Filtros Ativos: IA={params['use_ai_core']}, Fluxo={params['use_flux_filter']}")
    print("="*75)

    print("⏳ Coletando dados e executando simulação...")
    report = await bt.run()
    
    trades = report['trades']
    df_trades = pd.DataFrame(trades)
    
    if df_trades.empty:
        print("❌ Nenhum trade realizado.")
        return

    # 1. Performance por Direção
    buy_trades = df_trades[df_trades['side'] == 'buy']
    sell_trades = df_trades[df_trades['side'] == 'sell']
    
    def get_stats(df, name):
        if df.empty: return f"{name} | Sem trades realizados."
        wr = (len(df[df['pnl_fin'] > 0]) / len(df)) * 100
        total = df['pnl_fin'].sum()
        avg = df['pnl_fin'].mean()
        max_win = df['pnl_fin'].max()
        max_loss = df['pnl_fin'].min()
        return f"{name} | Trades: {len(df)} | WR: {wr:.1f}% | PnL Total: R$ {total:.2f} | Média: R$ {avg:.2f} | Maior Win: {max_win:.0f} | Maior Loss: {max_loss:.0f}"

    print("\n📊 PERFORMANCE DETALHADA")
    print("-" * 50)
    print(get_stats(buy_trades, "🔵 COMPRA"))
    print(get_stats(sell_trades, "🔴 VENDA"))
    
    # 2. Oportunidades Perdidas
    shadow = report.get('shadow_signals', {})
    print("\n🔍 AUDITORIA DE OPORTUNIDADES (SHADOW MODE)")
    print("-" * 50)
    print(f"Total de Gatilhos Técnicos:..... {shadow.get('v22_candidates', 0)}")
    print(f"Total de Oportunidades Vetadas:.. {shadow.get('total_missed', 0)}")
    print(f"Vetos pela IA (SOTA):........... {shadow.get('filtered_by_ai', 0)}")
    print(f"Vetos por Bias Diário (H):...... {shadow.get('filtered_by_bias', 0)}")
    
    # Detalhar motivos dos vetos da IA
    veto_reasons = shadow.get('veto_reasons', {})
    if veto_reasons:
        print("\nRAZÕES DOS VETOS (TOP 5):")
        sorted_reasons = sorted(veto_reasons.items(), key=lambda x: x[1], reverse=True)[:5]
        for reason, count in sorted_reasons:
            print(f" - {reason}: {count} ocorrências")

    # 3. Análise Final
    pct_return = (report['total_pnl'] / initial_capital) * 100
    print("\n🏆 VEREDITO SOTA")
    print("-" * 50)
    print(f"Lucro Líquido: R$ {report['total_pnl']:.2f} ({pct_return:.1f}%)")
    print(f"Profit Factor: {report['profit_factor']:.2f}")
    print(f"Max Drawdown: {report['max_drawdown']:.2f}%")
    
    if buy_trades.empty or sell_trades.empty:
        print("\n⚠️ ALERTA: Assimetria crítica detectada. Um dos lados está inativo.")
    elif abs(len(buy_trades) - len(sell_trades)) > len(df_trades) * 0.5:
        print("\n⚠️ OBSERVADO: Bias direcional forte. IA está filtrando majoritariamente um dos lados.")

if __name__ == "__main__":
    asyncio.run(run_deep_audit())
