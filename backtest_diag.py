"""
Diagnóstico: verifica se MT5 retorna dados e por que não há trades nos backtests
"""

import sys
import os
import asyncio
import logging
import MetaTrader5 as mt5
from datetime import datetime

# Ativa logs para ver tudo
logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from backend.mt5_bridge import MT5Bridge
from backend.backtest_pro import BacktestPro


async def diag():
    bridge = MT5Bridge()
    ok = bridge.connect()
    print(f"[MT5] Conectado: {ok}")
    if not ok:
        print("[ERRO] MT5 nao conectado. Verifique o terminal.")
        return

    # Testa coleta de dados para 1 dia simples
    dia = datetime(2026, 2, 25)
    date_from = dia.replace(hour=8, minute=0)
    date_to = dia.replace(hour=18, minute=30)
    print(f"\n[DADOS] Coletando M1 para {dia.strftime('%d/%m/%Y')}...")
    data = bridge.get_market_data_range("WIN$N", mt5.TIMEFRAME_M1, date_from, date_to)

    if data is None or data.empty:
        print("[ERRO] Sem dados! Tentando simbolo alternativo WIN$...")
        data = bridge.get_market_data_range(
            "WIN$", mt5.TIMEFRAME_M1, date_from, date_to
        )

    if data is None or data.empty:
        print(
            "[ERRO] Sem dados para nenhum simbolo. Verificando simbolos disponiveis no MT5..."
        )
        syms = mt5.symbols_get()
        if syms:
            win_syms = [s.name for s in syms if "WIN" in s.name]
            print(f"  Simbolos WIN disponiveis: {win_syms[:15]}")
        bridge.disconnect()
        return

    print(f"[OK] {len(data)} candles carregados para {dia.strftime('%d/%m/%Y')}")
    print(f"  Primeiro candle: {data.index[0]}")
    print(f"  Ultimo candle : {data.index[-1]}")
    print(f"  Colunas: {list(data.columns)}")
    print(f"  Amostra:\n{data.head(3)}\n")

    # Testa BacktestPro com modo LEGACY (use_ai_core=False) para isolar problema de IA
    print("\n[BACKTEST] Executando backtest LEGADO (sem AI Core) para diagnosrico...")
    bt = BacktestPro(
        symbol="WIN$N",
        initial_balance=3000.0,
        use_ai_core=False,  # Modo legado para teste
        aggressive_mode=True,
        confidence_threshold=0.65,  # Threshold mais baixo para forcar sinais
    )
    bt.data = data.copy()
    result = await bt.run()

    if result is None:
        print("[RESULTADO] BacktestPro retornou None (nenhum trade executado).")
        print("  Causa provavel: nenhum sinal passou pelos filtros.")
        print(f"  Shadow signals: {bt.shadow_signals}")
        print(f"  Total de velas processadas: {len(data)}")
    else:
        print(f"[RESULTADO] {len(result['trades'])} trades executados!")
        print(f"  PNL: R$ {result['total_pnl']:.2f}")
        print(f"  Win Rate: {result['win_rate']:.1f}%")
        print(f"  Shadows: {result['shadow_signals']}")

    bridge.disconnect()


if __name__ == "__main__":
    asyncio.run(diag())
