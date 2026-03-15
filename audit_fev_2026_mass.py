import asyncio
import logging
import pandas as pd
from datetime import datetime
from backend.mt5_bridge import MT5Bridge
from backend.backtest_pro import BacktestPro
import MetaTrader5 as mt5
import os
import json

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def run_mass_audit():
    bridge = MT5Bridge()
    if not bridge.connect():
        logger.error("❌ ERRO: Falha ao conectar ao Terminal MetaTrader 5.")
        return

    # Configurações de Auditoria
    symbol = "WIN$N"
    initial_balance = 3000.0
    dates = [
        datetime(2026, 2, 19),
        datetime(2026, 2, 20),
        datetime(2026, 2, 23),
        datetime(2026, 2, 24),
        datetime(2026, 2, 25),
        datetime(2026, 2, 26),
        datetime(2026, 2, 27),
    ]

    # Carregar Golden Params para garantir conformidade
    locked_params = {}
    params_path = "backend/v22_locked_params.json"
    if os.path.exists(params_path):
        with open(params_path, "r") as f:
            config = json.load(f)
            locked_params = config.get("strategy_params", {})
            logger.info("🛡️ Parâmetros V22 (Golden) carregados para auditoria.")

    all_results = []

    print("\n" + "=" * 80)
    print(
        f"--- START MASS AUDIT: SOTA PRO (REFINADA) | CAPITAL: R$ {initial_balance:,.2f} | SYMBOL: {symbol}"
    )
    print("=" * 80)

    for audit_date in dates:
        date_str = audit_date.strftime("%d/%m/%Y")
        print(f"\n>>> PROCESSANDO DIA: {date_str} <<<")

        date_from = audit_date.replace(hour=8, minute=0, second=0)
        date_to = audit_date.replace(hour=18, minute=30, second=0)

        # Coleta de dados históricos M1
        print(f"--- Coletando dados para {date_str} ---")
        data = bridge.get_market_data_range(
            symbol, mt5.TIMEFRAME_M1, date_from, date_to
        )

        if data is None or data.empty:
            print(f"[AVISO] Sem dados para {date_str}. Pulando...")
            continue

        # Garante que use_ai_core seja True para o teste SOTA PRO
        audit_params = locked_params.copy()
        audit_params["use_ai_core"] = True

        # Execução Backtest com AI (SOTA PRO)
        print(f"--- Executando Backtest SOTA PRO ({date_str}) ---")
        backtester = BacktestPro(
            symbol=symbol, initial_balance=initial_balance, **audit_params
        )
        backtester.data = data.copy()
        results = await backtester.run()

        if results:
            day_summary = {
                "date": date_str,
                "total_pnl": results["total_pnl"],
                "trades_count": len(results["trades"]),
                "shadow_count": len(results["shadow_signals"]),
                "max_drawdown": results["max_drawdown"],
            }

            # Análise por Lado (Real)
            trades_df = pd.DataFrame(results["trades"])
            if not trades_df.empty:
                buy_trades = trades_df[trades_df["side"] == "buy"]
                sell_trades = trades_df[trades_df["side"] == "sell"]
                day_summary["real_buy_pnl"] = buy_trades["pnl_fin"].sum()
                day_summary["real_sell_pnl"] = sell_trades["pnl_fin"].sum()
            else:
                day_summary["real_buy_pnl"] = 0
                day_summary["real_sell_pnl"] = 0

            # Análise Shadow (Sinais Vetados)
            shadow_buys = [s for s in results["shadow_signals"] if s["side"] == "buy"]
            shadow_sells = [s for s in results["shadow_signals"] if s["side"] == "sell"]
            day_summary["shadow_buy_count"] = len(shadow_buys)
            day_summary["shadow_sell_count"] = len(shadow_sells)

            # Classificação de Vetos
            vetos = {}
            for s in results["shadow_signals"]:
                reason = s.get("reason", "Desconhecido")
                vetos[reason] = vetos.get(reason, 0) + 1
            day_summary["vetos_detalhe"] = vetos

            all_results.append(day_summary)
            print(
                f"[OK] DIA {date_str}: PNL R$ {results['total_pnl']:.2f} | Trades: {len(results['trades'])} | Shadows: {len(results['shadow_signals'])}"
            )

    # Consolidação Final (Português BR)
    if all_results:
        summary_df = pd.DataFrame(all_results)
        final_pnl = summary_df["total_pnl"].sum()
        total_shadows = summary_df["shadow_count"].sum()

        print("\n" + "=" * 80)
        print("📊 RELATORIO CONSOLIDADO: AUDITORIA FEVEREIRO 2026")
        print("-" * 80)
        print(f"PNL TOTAL ACUMULADO (REAL) : R$ {final_pnl:>12.2f}")
        print(f"TOTAL DE TRADES REAIS      : {summary_df['trades_count'].sum():>12}")
        print(f"TOTAL DE SHADOW TRADES     : {total_shadows:>12}")
        print(
            f"OPORTUNIDADES DE COMPRA    : {summary_df['shadow_buy_count'].sum():>12}"
        )
        print(
            f"OPORTUNIDADES DE VENDA     : {summary_df['shadow_sell_count'].sum():>12}"
        )
        print("-" * 80)

        # Resumo de Vetos (Por que não entramos?)
        consolidated_vetos = {}
        for res in all_results:
            for reason, count in res["vetos_detalhe"].items():
                consolidated_vetos[reason] = consolidated_vetos.get(reason, 0) + count

        print("MOTIVOS DE VETO (COST OF SAFETY):")
        for reason, count in consolidated_vetos.items():
            print(f" - {reason}: {count} sinais bloqueados")
        print("-" * 80)

        # Salvar resultados
        with open("audit_mass_refined_results.txt", "w", encoding="utf-8") as f:
            f.write(summary_df.to_string())
            f.write(f"\n\nPNL TOTAL: R$ {final_pnl:.2f}")
            f.write(f"\nSHADOW TOTAL: {total_shadows}")
            f.write(f"\nVETOS: {json.dumps(consolidated_vetos, indent=2)}")

    bridge.disconnect()


if __name__ == "__main__":
    asyncio.run(run_mass_audit())
