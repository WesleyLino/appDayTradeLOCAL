import asyncio
import logging
from datetime import datetime
import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro

async def run_mt5_analysis_23mar():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print("=====================================================================")
    print(" INICIANDO AUDITORIA E RETREINAMENTO DE MÁXIMA PERFORMANCE - 23/03")
    print("=====================================================================")
    
    symbol = "WIN$"
    capital = 3000.0

    # 1. Configurar Backtest
    tester = BacktestPro(
        symbol=symbol,
        n_candles=2000,
        timeframe="M1",
        initial_balance=capital,
        base_lot=2,  # Configurado para forçar 2 lotes igual ao real
        dynamic_lot=False,
        use_ai_core=True,
    )

    # Carregar os parametros aprovados pelo usuario (v24_locked_params)
    param_path = os.path.join(os.path.dirname(__file__), "v24_locked_params.json")
    try:
        with open(param_path, "r", encoding="utf-8") as f:
            v24_params = json.load(f)
            # Aplicando os parâmetros soltos pela autorização do usuário
            for k, v in v24_params.items():
                if k != "account_config":
                    tester.opt_params[k] = v
            print("✔️  Parâmetros V24 carregados com sucesso (Fluxo: 1.2, Bypass: 75%).")
    except Exception as e:
        print(f"❌ Erro ao ler v24_locked_params.json: {e}")
        return

    # 2. Carregar dados do MT5
    print("\n⏳ Conectando ao MetaTrader 5 e baixando histórico do M1...")
    data = await tester.load_data()

    if data is None or data.empty:
        print("❌ Falha crítica: Sem conexão ou dados do MT5.")
        return

    # Filtrar apenas para o dia 23/03/2026
    target_date = datetime(2026, 3, 23).date()
    data = data[data.index.date == target_date]

    if data.empty:
        print(f"❌ Nenhum candle recuperado para {target_date}.")
        return

    print(f"✔️  Dados recuperados: {len(data)} candles processados para calibração.\n")

    # 3. Executar Simulacao (Backtest)
    print("⚙️  Executando motor de inferência (RL + PatchTST)...")
    await tester.run()

    # 4. Relatorio
    shadow = tester.shadow_signals
    trades = tester.trades

    print("\n" + "=" * 60)
    print("📊 RESULTADO DO RETREINAMENTO DE ALTA PERFORMANCE - 23/03/2026")
    print("=" * 60)
    print(f"💰 Saldo Inicial:   R$ {capital:.2f}")
    print(f"💰 Saldo Final:     R$ {tester.balance:.2f}")
    
    pnl_total = tester.balance - capital
    pnl_color = "🟩" if pnl_total > 0 else "🟥" if pnl_total < 0 else "⬜"
    print(f"📈 PnL Total:       {pnl_color} R$ {pnl_total:.2f}")
    print(f"🎫 Total de Trades: {len(trades)}")

    if len(trades) > 0:
        win_rate = (len([t for t in trades if t["pnl_fin"] > 0]) / len(trades)) * 100
        print(f"🎯 Assertividade:   {win_rate:.2f}%\n")

        # Analise Comprada vs Vendida
        buy_trades = [t for t in trades if t["side"] == "buy"]
        sell_trades = [t for t in trades if t["side"] == "sell"]

        buy_pnl = sum([t["pnl_fin"] for t in buy_trades])
        sell_pnl = sum([t["pnl_fin"] for t in sell_trades])

        buy_wr = ((len([t for t in buy_trades if t["pnl_fin"] > 0]) / len(buy_trades) * 100) if buy_trades else 0)
        sell_wr = ((len([t for t in sell_trades if t["pnl_fin"] > 0]) / len(sell_trades) * 100) if sell_trades else 0)

        print("\n--- PERFORMANCE POR DIREÇÃO (POTENCIAL) ---")
        print(f"🛒 COMPRAS (BUY):   {len(buy_trades)} entradas | Gain: R$ {buy_pnl:.2f} | Assertividade: {buy_wr:.2f}%")
        print(f"📉 VENDAS (SELL):   {len(sell_trades)} entradas | Gain: R$ {sell_pnl:.2f} | Assertividade: {sell_wr:.2f}%")

    print("\n--- ANÁLISE DE OPORTUNIDADES E PERDAS ---")
    print(f"🔍 Sinais Potenciais Detectados (V22): {shadow.get('v22_candidates', 0)}")
    print(f"🚫 Trades Negados pela I.A.:           {shadow.get('filtered_by_ai', 0)}")
    print(f"🚫 Trades Negados por Falta de Fluxo:  {shadow.get('filtered_by_flux', 0)}")
    
    component_fails = shadow.get('component_fail', {})
    if component_fails:
        print(f"⚠️  Falhas Específicas de Filtro (Motivos):")
        for k, v in component_fails.items():
            print(f"   - {k.capitalize()}: {v} vezes")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(run_mt5_analysis_23mar())
