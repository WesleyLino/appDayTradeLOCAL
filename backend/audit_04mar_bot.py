import asyncio
import logging
from datetime import date
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_mt5_analysis():
    # Setup de Logging para Auditoria
    logger = logging.getLogger()
    logger.setLevel(logging.ERROR)

    print("===================================================================")
    print("🚀 INICIANDO RETREINAMENTO HIGH-PERFORMANCE (MT5) - 04/03/2026")
    print("===================================================================")

    symbol = "WIN$"
    capital = 3000.0

    # 1. Configurar Backtest
    tester = BacktestPro(
        symbol=symbol,
        n_candles=1500,
        timeframe="M1",
        initial_balance=capital,
        base_lot=1,
        dynamic_lot=True,
        use_ai_core=True,
    )

    # Usando config robusta do golden params
    tester.opt_params["vol_spike_mult"] = 1.0
    tester.opt_params["use_flux_filter"] = True
    tester.opt_params["confidence_threshold"] = 0.70

    print("⏳ Coletando base histórica de ultra-fidelidade do terminal MT5...")
    data = await tester.load_data()

    if data is None or data.empty:
        print("❌ Falha ao carregar dados do MT5.")
        return

    # Filtrar apenas 04/03/2026
    target_date = date(2026, 3, 4)
    data = data[data.index.date == target_date]

    if data.empty:
        print(
            f"❌ Nenhum dado encontrado para o dia de hoje ({target_date}). Verifique o pregão."
        )
        return

    print(
        f"✅ Dados carregados: {len(data)} candles capturados (Timeline: {data.index[0].strftime('%H:%M')} as {data.index[-1].strftime('%H:%M')})."
    )
    print(
        "🧠 Executando simulação de redes complexas e análise de sinal... Isso pode demorar alguns segundos."
    )

    # 3. Executar Simulacao Baseline
    tester.data = data
    await tester.run()

    # 4. Relatorio de Performance e Oportunidades
    shadow = tester.shadow_signals
    trades = tester.trades

    print("\n📊 RELATÓRIO DO DIA - BASELINE (SOTA V22 MESTRE)")
    print("--------------------------------------------------")
    print(f"Capital Operacional:   R$ {capital:.2f}")
    print(f"Caixa Final:           R$ {tester.balance:.2f}")
    pnl = tester.balance - capital
    print(f"LUCRO LÍQUIDO NO DIA:  R$ {pnl:.2f}")
    print(f"Nº de Operações:       {len(trades)}")

    if len(trades) > 0:
        win_rate = (len([t for t in trades if t["pnl_fin"] > 0]) / len(trades)) * 100
        print(f"Assertividade Global:  {win_rate:.2f}%")

        # Analise Direcional
        buy_trades = [t for t in trades if t["side"] == "buy"]
        sell_trades = [t for t in trades if t["side"] == "sell"]

        buy_pnl = sum([t["pnl_fin"] for t in buy_trades])
        sell_pnl = sum([t["pnl_fin"] for t in sell_trades])

        buy_wr = (
            (len([t for t in buy_trades if t["pnl_fin"] > 0]) / len(buy_trades) * 100)
            if buy_trades
            else 0
        )
        sell_wr = (
            (len([t for t in sell_trades if t["pnl_fin"] > 0]) / len(sell_trades) * 100)
            if sell_trades
            else 0
        )

        print("\n--- PERFORMANCE BI-DIRECIONAL (COMPRA x VENDA) ---")
        print(
            f"🟢 COMPRA: {len(buy_trades)} trades | PnL: R$ {buy_pnl:+.2f} | Assertividade: {buy_wr:.1f}%"
        )
        print(
            f"🔴 VENDA:  {len(sell_trades)} trades | PnL: R$ {sell_pnl:+.2f} | Assertividade: {sell_wr:.1f}%"
        )

    print("\n--- SHADOW ANALYSIS (Oportunidades Perdidas) ---")
    print(
        f"- Total de Sinais Brutos da IA (v22_candidates): {shadow.get('v22_candidates', 0)}"
    )
    print(
        f"- Veto por Padrão de Incerteza (IA):             {shadow.get('filtered_by_ai', 0)}"
    )
    print(
        f"- Veto por Microestrutura de Fluxo (CVD/OFI):    {shadow.get('filtered_by_flux', 0)}"
    )
    print(
        f"- Falhas nos Componentes Restritivos:            {shadow.get('component_fail', {})}"
    )

    print("\n💡 RESULTADOS DE CALIBRAÇÃO (POTENCIAL DE GANHO EXTRA):")

    best_pnl = pnl
    best_wr = win_rate if len(trades) > 0 else 0
    best_config = {}

    for thresh in [0.65, 0.70, 0.75, 0.80]:
        for flux in [True, False]:
            tmp_tester = BacktestPro(
                symbol=symbol, initial_balance=capital, use_ai_core=True
            )
            tmp_tester.opt_params["confidence_threshold"] = thresh
            tmp_tester.opt_params["use_flux_filter"] = flux
            tmp_tester.data = data
            await tmp_tester.run()

            p = tmp_tester.balance - capital
            t = tmp_tester.trades
            w = (
                (len([x for x in t if x["pnl_fin"] > 0]) / len(t)) * 100
                if len(t) > 0
                else 0
            )

            if p > best_pnl and w >= 55.0:
                best_pnl = p
                best_wr = w
                best_config = {"thresh": thresh, "flux": flux}

    if best_config:
        print("🌟 PARAMETRIZAÇÃO DE SUPERAÇÃO ENCONTRADA!")
        print(
            f"-> Utilizar Confidence={best_config['thresh']} | Filtro de Fluxo={best_config['flux']}"
        )
        print(f"-> Elevou o Ganho do Dia para R$ {best_pnl:.2f}")
        print(f"-> Elevou a Assertividade para {best_wr:.1f}%")
        print(
            "\n⚠️ NOTA: O arquivo V22 Mestre NÃO foi sobrescrito (Blindagem Ativada). Se superior e seguro, a alteração pode ser acatada."
        )
    else:
        print(
            "\n🎯 V22 LÍDER ABSOLUTO - Setup Mestre já possui o cenário mais lucrativo para hoje."
        )
        print(
            "Nenhuma combinação de re-treinamento rápido superou a estabilidade e previsibilidade de lucro do Golden State atual."
        )

    print("\n===================================================================")


if __name__ == "__main__":
    asyncio.run(run_mt5_analysis())
