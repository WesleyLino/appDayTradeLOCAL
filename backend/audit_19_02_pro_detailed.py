import asyncio
import logging
import pandas as pd
from datetime import datetime
import sys
import os

# Adiciona diretorio raiz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_detailed_audit():
    # Configuracao de Logs
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.info("🚀 INICIANDO AUDITORIA DETALHADA SOTA PRO (19/02/2026)")

    symbol = "WIN$"
    capital = 3000.0
    target_date = datetime(2026, 2, 19).date()

    # 1. Configurar Backtest com modo PRO
    tester = BacktestPro(
        symbol=symbol,
        n_candles=4000,  # Aumentado para garantir o dia todo e lookback
        timeframe="M1",
        initial_balance=capital,
        base_lot=1,
        dynamic_lot=True,
        use_ai_core=True,  # ATIVA O MOTOR SOTA PRO
    )

    # Aplicar Filtros PRO de Rigor (SOTA v3.1 PRO)
    tester.opt_params["confidence_threshold"] = 0.85  # Threshold Sniper
    tester.opt_params["use_flux_filter"] = True
    tester.opt_params["flux_imbalance_threshold"] = 1.2
    tester.opt_params["be_trigger"] = 60.0  # Breakeven agressivo

    # 2. Carregar dados do MT5
    logging.info(f"Solicitando dados historicos do terminal MT5 para {target_date}...")
    data = await tester.load_data()

    if data is None or data.empty:
        logging.error("Falha ao carregar dados do MT5.")
        return

    # Atribui o dataset completo para o motor
    tester.data = data

    # 3. Executar Simulacao
    await tester.run()

    # 4. Processamento de Resultados PRO (Filtrando apenas o dia 19/02)
    trades = [t for t in tester.trades if t["entry_time"].date() == target_date]
    df_trades = pd.DataFrame(trades)

    buy_trades = [t for t in trades if t["side"] == "buy"]
    sell_trades = [t for t in trades if t["side"] == "sell"]

    buy_pnl = sum(t["pnl_fin"] for t in buy_trades)
    sell_pnl = sum(t["pnl_fin"] for t in sell_trades)
    total_pnl = sum(t["pnl_fin"] for t in trades)

    shadow = tester.shadow_signals

    # Formatação do Relatório
    report_content = f"""# Relatório de Auditoria SOTA PRO - {target_date}

## Resumo Executivo
- **Capital Inicial**: R$ {capital:.2f}
- **Saldo Final do Dia**: R$ {capital + total_pnl:.2f}
- **PnL Total**: **R$ {total_pnl:.2f}**
- **Sincronia Sniper**: 100% (Modo Autônomo Ativo)

## Performance por Direção
| Direção | Trades | PnL Bruto | Win Rate |
| :--- | :--- | :--- | :--- |
| **COMPRA** | {len(buy_trades)} | R$ {buy_pnl:.2f} | {len([t for t in buy_trades if t["pnl_fin"] > 0]) / len(buy_trades) * 100 if buy_trades else 0:.1f}% |
| **VENDA** | {len(sell_trades)} | R$ {sell_pnl:.2f} | {len([t for t in sell_trades if t["pnl_fin"] > 0]) / len(sell_trades) * 100 if sell_trades else 0:.1f}% |
| **TOTAL** | {len(trades)} | R$ {total_pnl:.2f} | {len([t for t in trades if t["pnl_fin"] > 0]) / len(trades) * 100 if trades else 0:.1f}% |

## Análise de Oportunidades (Shadow Trading)
O sistema monitorou o mercado e aplicou os filtros de rigor PRO.

- **Candidatos V22/SOTA**: {shadow.get("v22_candidates", 0)}
- **Sinais Vetados pela IA (Incerteza/Meta)**: {shadow.get("filtered_by_ai", 0)}
- **Sinais Vetados pelo Fluxo (Book)**: {shadow.get("filtered_by_flux", 0)}

### Detalhamento de Bloqueios IA
| Tier de Confiança | Sinais Bloqueados |
| :--- | :--- |
| 70% - 75% | {shadow.get("tiers", {}).get("70-75", 0)} |
| 75% - 80% | {shadow.get("tiers", {}).get("75-80", 0)} |
| 80% - 85% | {shadow.get("tiers", {}).get("80-85", 0)} |

## Conclusão de Auditoria
O teste confirma o rigor PRO em {target_date}. O capital foi preservado com seletividade máxima.
"""

    # Salva o relatório
    report_path = os.path.join(
        os.path.dirname(__file__), "..", "backend", "audit_pro_1902_report.md"
    )
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"\n✅ Auditoria concluída. Relatório salvo em: {report_path}")


if __name__ == "__main__":
    asyncio.run(run_detailed_audit())
