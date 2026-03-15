import asyncio
import pandas as pd
import sys
import os
from datetime import datetime
import MetaTrader5 as mt5

# Adiciona diretório raiz para importações
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro
from backend.mt5_bridge import MT5Bridge


async def run_scenario(symbol, config, mode="Híbrido"):
    print(f"\n[CENARIO] Operando: {mode}")
    bt = BacktestPro(symbol=symbol, **config)

    if mode == "Somente Compra":
        bt.opt_params["confidence_sell_threshold"] = 1.0
    elif mode == "Somente Venda":
        bt.opt_params["confidence_buy_threshold"] = 1.0

    await bt.run()
    return bt


async def main():
    print("=" * 60)
    print("INICIANDO ANALISE DE POTENCIAL 11/03 - SOTA v24.2")
    print("=" * 60)

    bridge = MT5Bridge()
    if not bridge.connect():
        print("Erro: Nao foi possivel conectar ao MetaTrader 5.")
        return

    symbol = "WIN$"
    timeframe = mt5.TIMEFRAME_M1
    date_target = datetime(2026, 3, 11)

    # Coleta de dados
    rates = mt5.copy_rates_range(
        symbol, timeframe, date_target, date_target.replace(hour=18, minute=0)
    )
    if rates is None or len(rates) == 0:
        print("❌ Erro: Dados do dia 11/03 não encontrados no histórico.")
        return

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    temp_file = "data/data_audit_11mar.csv"
    os.makedirs("data", exist_ok=True)
    df.to_csv(temp_file)

    config = {
        "initial_balance": 500.0,
        "data_file": temp_file,
        "n_candles": len(df),
        "base_lot": 2,  # Sincronizado com a agressividade solicitada
    }

    # Execução dos Cenários
    scenarios = ["Híbrido", "Somente Compra", "Somente Venda"]
    results = {}

    for s in scenarios:
        results[s] = await run_scenario(symbol, config, mode=s)

    # Análise Híbrida (Base de Realidade)
    h = results["Híbrido"]
    trades = h.trades
    ganho_compra = sum(
        t["pnl_fin"] for t in trades if t["pnl_fin"] > 0 and t["side"] == "buy"
    )
    ganho_venda = sum(
        t["pnl_fin"] for t in trades if t["pnl_fin"] > 0 and t["side"] == "sell"
    )
    prejuizo_total = abs(sum(t["pnl_fin"] for t in trades if t["pnl_fin"] < 0))

    # Oportunidade Perdida (Shadow Signals)
    missed = h.shadow_signals

    # Salvar em arquivo para evitar truncamento
    with open("audit_11mar_final.txt", "w") as f:
        f.write("RELATORIO FINAL 11/03\n")
        f.write("=" * 30 + "\n")
        f.write(f"Ganho (COMPRA): R$ {ganho_compra:.2f}\n")
        f.write(f"Ganho (VENDA):  R$ {ganho_venda:.2f}\n")
        f.write(f"Prejuizo:       R$ {prejuizo_total:.2f}\n")
        f.write(
            f"Liquido:        R$ {(ganho_compra + ganho_venda - prejuizo_total):.2f}\n"
        )
        f.write("-" * 30 + "\n")
        f.write("FILTROS:\n")
        f.write(f"   - Confianca: {missed['veto_reasons'].get('LOW_CONFIDENCE', 0)}\n")
        f.write(f"   - Volatilidade: {missed['veto_reasons'].get('HL_EXTREMO', 0)}\n")
        f.write(f"   - Outros: {missed['filtered_by_bias']}\n")
        f.write("=" * 30 + "\n")

    print("\n✅ Auditoria concluida. Resultados em audit_11mar_final.txt")


if __name__ == "__main__":
    asyncio.run(main())
