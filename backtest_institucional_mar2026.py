import asyncio
import logging
import os
import sys
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime

# Garante path correto para os módulos
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from backend.mt5_bridge import MT5Bridge
from backend.backtest_pro import BacktestPro

# Configurações de Saída
OUTPUT_FILE = "backtest_institucional_resultados.txt"
_arquivo_saida = open(OUTPUT_FILE, "w", encoding="utf-8")

# Configuração de logging para arquivo também
logging.basicConfig(level=logging.INFO, stream=_arquivo_saida)

SYMBOL = "WIN$"
INITIAL_BAL = 3000.0
DIAS_ALVO = [
    datetime(2026, 2, 19),
    datetime(2026, 2, 20),
    datetime(2026, 2, 23),
    datetime(2026, 2, 24),
    datetime(2026, 2, 25),
    datetime(2026, 2, 26),
    datetime(2026, 2, 27),
    datetime(2026, 2, 28), 
    datetime(2026, 3, 2),
]

def fmt_reais(val: float) -> str:
    sinal = "+" if val >= 0 else ""
    return f"R$ {sinal}{val:,.2f}"

async def run():
    bridge = MT5Bridge()
    if not bridge.connect():
        print("❌ ERRO: Conexão com o MetaTrader 5 falhou.")
        return

    _arquivo_saida.write("=" * 85 + "\n")
    _arquivo_saida.write("  SIMULAÇÃO INSTITUCIONAL SOTA (v50.0 MASTER) - MINI ÍNDICE (WIN)\n")
    _arquivo_saida.write("  PERÍODO  : 19/02/2026 a 02/03/2026\n")
    _arquivo_saida.write(f"  CAPITAL  : {fmt_reais(INITIAL_BAL)}\n")
    _arquivo_saida.write("  MODO     : HFT ELITE (IA SOTA ATIVADA)\n")
    _arquivo_saida.write("=" * 85 + "\n")

    total_pnl = 0.0
    trades_totais = []
    total_missed_signals = 0
    vetos_ia = 0
    vetos_fluxo = 0

    for dia in DIAS_ALVO:
        date_str = dia.strftime("%d/%m/%Y")
        date_from_buffer = dia.replace(hour=7, minute=0, second=0)
        date_to = dia.replace(hour=17, minute=45, second=0)

        data = bridge.get_market_data_range(SYMBOL, mt5.TIMEFRAME_M1, date_from_buffer, date_to)
        
        if data is None or data.empty:
            if dia.weekday() < 5:
                _arquivo_saida.write(f"⚠️ [{date_str}] Sem dados disponíveis no MT5.\n")
            continue

        _arquivo_saida.write(f"📊 [{date_str}] Dados: {len(data)} candles carregados.\n")
        
        bt = BacktestPro(
            symbol=SYMBOL,
            initial_balance=INITIAL_BAL + total_pnl,
            use_ai_core=True,
            confidence_threshold=0.50, # Threshold reduzido para diagnóstico de potencial
            rsi_period=9,             
            vol_spike_mult=0.8,        # Facilitando o spike para diagnóstico
            use_flux_filter=True,
            dynamic_lot=True,
            base_lot=2, 
            use_trailing_stop=True,
            start_time="09:05",
            end_time="17:15",
            bb_dev=2.0,
            sl_dist=150.0,
            tp_dist=500.0
        )
        
        bt.data = data.copy()
        bt.ai.latest_sentiment_score = 0.25 
        
        result = await bt.run() or {}

        shadows = result.get('shadow_signals', {})
        cand_dia = shadows.get('v22_candidates', 0)
        total_missed_signals += cand_dia
        vetos_ia += (shadows.get('buy_vetos_ai', 0) + shadows.get('sell_vetos_ai', 0))
        vetos_fluxo += shadows.get('filtered_by_flux', 0)

        day_trades = result.get('trades', [])
        day_pnl = result.get('total_pnl', 0.0)
        total_pnl += day_pnl
        trades_totais.extend(day_trades)

        win_rate = result.get('win_rate', 0.0)
        _arquivo_saida.write(f"  [{date_str}] Trades: {len(day_trades):>2} | PnL: {fmt_reais(day_pnl):>12} | WR: {win_rate:>5.1f}% | Cand: {cand_dia:>2} | Vetos: {vetos_ia}\n")
        _arquivo_saida.flush()

    # Consolidação Final
    trades_df = pd.DataFrame(trades_totais)
    _arquivo_saida.write("\n" + "=" * 85 + "\n")
    _arquivo_saida.write("  RELATÓRIO FINAL CONSOLIDADO\n")
    _arquivo_saida.write("-" * 85 + "\n")
    _arquivo_saida.write(f"  PATRIMÔNIO FINAL       : {fmt_reais(INITIAL_BAL + total_pnl)}\n")
    _arquivo_saida.write(f"  LUCRO LÍQUIDO ACUMULADO : {fmt_reais(total_pnl)}\n")
    _arquivo_saida.write(f"  TOTAL DE OPERAÇÕES     : {len(trades_totais)}\n")
    
    if not trades_df.empty:
        compras = trades_df[trades_df['side'] == 'buy']
        vendas = trades_df[trades_df['side'] == 'sell']
        _arquivo_saida.write("-" * 85 + "\n")
        _arquivo_saida.write(f"  📊 COMPRAS: {len(compras)} | VENDAS: {len(vendas)}\n")
        _arquivo_saida.write(f"  ├── PnL COMPRAS: {fmt_reais(compras['pnl_fin'].sum())}\n")
        _arquivo_saida.write(f"  └── PnL VENDAS : {fmt_reais(vendas['pnl_fin'].sum())}\n")
    
    _arquivo_saida.write("=" * 85 + "\n")
    bridge.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(run())
    finally:
        _arquivo_saida.close()
    print(f"✅ Resultados salvos em: {OUTPUT_FILE}")
