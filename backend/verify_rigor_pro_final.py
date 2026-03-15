import asyncio
import os
import sys

# Adiciona diretório raiz para importar módulos do backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_audit(target_date, label):
    print(f"\n🚀 {label} - {target_date}")
    print("=" * 60)

    backtester = BacktestPro(
        symbol="WIN$",
        n_candles=10000,
        initial_balance=3000.0,
        use_ai_core=True,
        aggressive_mode=True,
        base_lot=1,
        dynamic_lot=False,
    )

    data = await backtester.load_data()
    if data is not None:
        data_filtered = data[data.index.strftime("%Y-%m-%d") == target_date]
        if not data_filtered.empty:
            backtester.data = data_filtered
            print(
                f"✅ Dados de {target_date} carregados: {len(data_filtered)} candles."
            )
        else:
            print(f"❌ Dados para {target_date} não encontrados no MT5.")
            return

    results = await backtester.run()

    if results:
        print(f"PnL Total:        R$ {results['total_pnl']:.2f}")
        print(f"Win Rate:         {results['win_rate']:.1f}%")
        print(f"Total de Trades:  {len(results['trades'])}")
        shadow = results["shadow_signals"]
        print(f"Vetos de Fluxo:   {shadow['filtered_by_flux']}")
        print("=" * 60)
        return results
    return None


async def main():
    print("🧪 INICIANDO BATERIA DE VALIDAÇÃO RIGOR SOTA v3.1 PRO")
    await run_audit("2026-02-19", "CENÁRIO CRÍTICO (RUÍDO)")
    await run_audit("2026-02-26", "CENÁRIO ATUAL (TENDÊNCIA)")


if __name__ == "__main__":
    asyncio.run(main())
