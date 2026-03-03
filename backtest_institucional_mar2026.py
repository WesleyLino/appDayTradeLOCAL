"""
Backtest Institucional SOTA - Mini Índice (WIN)
Período: 19/02/2026 - 02/03/2026
Capital: R$ 3.000,00 | Timeframe: M1
Foco: Avaliação de Potencial v30/v40 (93% Threshold)
"""
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
_stdout_original = sys.stdout
sys.stdout = _arquivo_saida

# Silencia logs invasivos
logging.disable(logging.CRITICAL)

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
    datetime(2026, 2, 28), # Sábado - Devolverá vazio
    datetime(2026, 3, 2),
]

def fmt_reais(val: float) -> str:
    sinal = "+" if val >= 0 else ""
    return f"R$ {sinal}{val:,.2f}"

async def run():
    bridge = MT5Bridge()
    if not bridge.connect():
        print("❌ ERRO: Conexão com o MetaTrader 5 falhou. Certifique-se de que o terminal está aberto.")
        return

    print("=" * 85)
    print("  SIMULAÇÃO INSTITUCIONAL SOTA (v30/v40) - MINI ÍNDICE (WIN)")
    print("  PERÍODO  : 19/02/2026 a 02/03/2026")
    print(f"  CAPITAL  : {fmt_reais(INITIAL_BAL)}")
    print("  MODO     : TÁTICO STANDARD (SEM IA - APENAS TÉCNICO)")
    print("=" * 85)

    total_pnl = 0.0
    trades_totais = []
    total_missed_signals = 0
    vetos_ia = 0
    vetos_fluxo = 0

    for dia in DIAS_ALVO:
        date_str = dia.strftime("%d/%m/%Y")
        # Buffer de 2 horas para estabilização de indicadores (EMA/VWAP)
        date_from_buffer = dia.replace(hour=7, minute=0, second=0)
        date_to = dia.replace(hour=17, minute=45, second=0)

        # Coleta dados reais do histórico
        data = bridge.get_market_data_range(SYMBOL, mt5.TIMEFRAME_M1, date_from_buffer, date_to)
        
        if data is None or data.empty:
            if dia.weekday() < 5: # Ignora fim de semana sem avisar erro
                print(f"⚠️ [{date_str}] Sem dados disponíveis no histórico do MT5.")
            continue

        bt = BacktestPro(
            symbol=SYMBOL,
            initial_balance=INITIAL_BAL + total_pnl,
            use_ai_core=False, 
            rsi_period=9,             
            vol_spike_mult=1.0,        
            use_flux_filter=True,
            dynamic_lot=True,
            base_lot=2, 
            use_trailing_stop=True,
            start_time="09:05",
            end_time="17:15",
            bb_dev=2.0,               # Padrão V22
            sl_dist=150.0,
            tp_dist=450.0
        )
        
        bt.data = data.copy()
        
        # Simula sentimento neutro-positivo para o período (Bias Institucional)
        bt.ai.latest_sentiment_score = 0.25 
        
        result = await bt.run() or {}

        # Coleta Oportunidades Perdidas
        shadows = result.get('shadow_signals', {})
        cand_dia = shadows.get('v22_candidates', 0)
        total_missed_signals += cand_dia
        vetos_ia += shadows.get('filtered_by_ai', 0)
        vetos_fluxo += shadows.get('filtered_by_flux', 0)

        day_trades = result.get('trades', [])
        day_pnl = result.get('total_pnl', 0.0)
        total_pnl += day_pnl
        trades_totais.extend(day_trades)

        # Resumo do Dia
        win_rate = result.get('win_rate', 0.0)
        buy_vetos = shadows.get('buy_vetos_ai', 0)
        sell_vetos = shadows.get('sell_vetos_ai', 0)
        print(f"  [{date_str}] Trades: {len(day_trades):>2} | PnL: {fmt_reais(day_pnl):>12} | WR: {win_rate:>5.1f}% | Cand. Técnicos: {cand_dia:>2} | IA Veto: {buy_vetos + sell_vetos}")

    # --- Consolidação Final ---
    trades_df = pd.DataFrame(trades_totais)
    print("\n" + "=" * 85)
    print("  REGRAS DE NEGOCIAÇÃO RELATÓRIO FINAL")
    print("-" * 85)
    print(f"  PATRIMÔNIO FINAL       : {fmt_reais(INITIAL_BAL + total_pnl)}")
    print(f"  LUCRO LÍQUIDO ACUMULADO : {fmt_reais(total_pnl)}")
    print(f"  RETORNO SOBRE CAPITAL  : {(total_pnl/INITIAL_BAL)*100:.1f}%")
    print(f"  TOTAL DE OPERAÇÕES     : {len(trades_totais)}")
    
    if not trades_df.empty:
        compras = trades_df[trades_df['side'] == 'buy']
        vendas = trades_df[trades_df['side'] == 'sell']
        
        print("-" * 85)
        print(f"  📊 POTENCIAL POR OPERAÇÃO:")
        print(f"  ├── COMPRAS  : {len(compras):>2} trades | PnL: {fmt_reais(compras['pnl_fin'].sum()):>12}")
        print(f"  └── VENDAS   : {len(vendas):>2} trades | PnL: {fmt_reais(vendas['pnl_fin'].sum()):>12}")
        
        # Filtro de Ganhos/Perdas
        lucrativos = len(trades_df[trades_df['pnl_fin'] > 0])
        prejuizos = len(trades_df[trades_df['pnl_fin'] < 0])
        win_rate_final = (lucrativos / len(trades_df)) * 100
        
        print("-" * 85)
        print(f"  🛡️ GESTÃO DE RISCO:")
        print(f"  ├── ASSERTIVIDADE GERAL: {win_rate_final:.1f}%")
        print(f"  ├── TRADES COM LUCRO   : {lucrativos}")
        print(f"  └── TRADES COM PREJUÍZO : {prejuizos}")
        
        # Oportunidades Perdidas
        print("-" * 85)
        print(f"  🔎 ANÁLISE DE OPORTUNIDADES (VETOS):")
        print(f"  ├── TOTAL DE SINAIS VETADOS: {total_missed_signals}")
        print(f"  ├── VETADOS POR IA (<93%)  : {vetos_ia} (Segurança)")
        print(f"  └── VETADOS POR FLUXO/VOL  : {vetos_fluxo}")
        
        # Sugestões de Melhorias
        print("\n  💡 MELHORIAS PARA ELEVAR ASSERTIVIDADE:")
        print("  1. Ajustar o 'Alpha Fade' para 12s em dias de alta volatilidade (como 26/02).")
        print("  2. Refinar a piramidação (Scaling In) para ativar apenas com Score > 95%.")
        print("  3. Implementar bloqueio preventivo 5min antes de notícias 3 estrelas (Calendário).")
    
    print("=" * 85)
    bridge.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(run())
    finally:
        _arquivo_saida.close()
        sys.stdout = _stdout_original
        print(f"✅ Simulação concluída. Resultados salvos em: {OUTPUT_FILE}")
