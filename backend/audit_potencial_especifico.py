import asyncio
import pandas as pd
import logging
import os
import sys

# Adiciona diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.backtest_pro import BacktestPro


async def run_audit_sota():
    """
    Executa uma auditoria de GANHO POTENCIAL (Shadow Trading) desativando os filtros conservadores.
    Focado nos períodos de 19/02 a 02/03.
    """
    print("🔎 Iniciando Auditoria de Potencial Estratégico SOTA v26...")

    # Configuração de Logs para ver vetos
    logging.getLogger().setLevel(logging.DEBUG)

    # Carrega dados e filtra pelo período solicitado
    bt = BacktestPro(
        symbol="WIN$", n_candles=15000, initial_balance=3000.0, use_ai_core=True
    )
    all_data = await bt.load_data()

    # Filtro Temporal: 19/02/2026 até hoje
    start_date = pd.Timestamp("2026-02-19")
    data = all_data[all_data.index >= start_date].copy()
    bt.data = data

    # Parâmetros ULTRA-SENSÍVEIS para capturar potencial
    bt.opt_params["confidence_threshold"] = 0.0
    bt.opt_params["vol_spike_mult"] = 0.0
    bt.opt_params["daily_trade_limit"] = 100
    bt.opt_params["bb_dev"] = 1.0
    bt.opt_params["rsi_period"] = 14
    bt.opt_params["audit_mode"] = True  # Força execução total

    # Ajusta sensibilidade do AICore para Auditoria de Potencial
    bt.ai.spread_veto_threshold = 10.0
    bt.ai.uncertainty_threshold_base = 10.0
    bt.ai.macro_bull_lock = False
    bt.ai.macro_bear_lock = False
    bt.ai.h1_trend = 0

    # Executa o backtest
    results = await bt.run()

    # Processa resultados
    df_trades = pd.DataFrame(bt.trades)
    if not df_trades.empty:
        buys = df_trades[df_trades["side"] == "buy"]
        sells = df_trades[df_trades["side"] == "sell"]
        profit_buys = buys["pnl_fin"].sum()
        profit_sells = sells["pnl_fin"].sum()
        wr_buys = (
            (len(buys[buys["pnl_fin"] > 0]) / len(buys) * 100) if not buys.empty else 0
        )
        wr_sells = (
            (len(sells[sells["pnl_fin"] > 0]) / len(sells) * 100)
            if not sells.empty
            else 0
        )
        total_pnl = profit_buys + profit_sells
        total_trades = len(df_trades)
        total_wr = len(df_trades[df_trades["pnl_fin"] > 0]) / len(df_trades) * 100
    else:
        buys = pd.DataFrame()
        sells = pd.DataFrame()
        profit_buys = 0.0
        profit_sells = 0.0
        wr_buys = 0.0
        wr_sells = 0.0
        total_pnl = 0.0
        total_trades = 0
        total_wr = 0.0

    # Filtros de Oportunidade (Shadow Trading)
    shadow = bt.shadow_signals

    # Geração do Relatório em Markdown
    report_md = f"""# Relatorio de Auditoria de Potencial - SOTA v26
    
**Periodo:** 19/02/2026 a 02/03/2026
**Capital Inicial:** R$ 3.000,00
**Ativo:** WIN$ (Mini Indice Bovespa)

## 💹 1. Performance por Ponta (Executado)

| Operação | Qtd Trades | Lucro Bruto (R$) | Assertividade (WR) |
| :--- | :---: | :---: | :---: |
| **COMPRA** | {len(buys)} | R$ {profit_buys:.2f} | {wr_buys:.1f}% |
| **VENDA** | {len(sells)} | R$ {profit_sells:.2f} | {wr_sells:.1f}% |
| **TOTAL** | {total_trades} | R$ {total_pnl:.2f} | {total_wr:.1f}% |

## 🛡️ 2. Análise de Risco e Prejuízo
- **Saldo Final:** R$ {bt.balance:.2f}
- **Drawdown Maximo:** {bt.max_drawdown * 100:.2f}%
- **Maior Perda Individual:** R$ {df_trades["pnl_fin"].min() if not df_trades.empty else 0.0:.2f}

## 🕵️ 3. Sombra de Oportunidade (Shadow Trading)
*Representa sinais que obedeceram ao setup matemático (RSI + BB), mas foram bloqueados por filtros de segurança.*

- **Candidatos Identificados (V22):** {shadow.get("v22_candidates", 0)}
- **Sinais Vetados pela IA (Compra/Venda):** {shadow.get("buy_vetos_ai", 0)} / {shadow.get("sell_vetos_ai", 0)}
- **Vetos de Tendência Macro (Alpha V28):** {shadow.get("filtered_by_bias", 0)}

## 💡 4. Recomendações de Melhoria
1. **Assimetria de Lote:** {"Otimizar lotes em vendas" if profit_sells < profit_buys else "Manter equilíbrio atual"}.
2. **Filtro de Ruído:** A IA evitou sinais com alta incerteza no modo Sniper.
3. **Assertividade:** O lucro potencial bruto mostra o que é possível sem as travas de segurança.

---
*Relatório gerado automaticamente por Antigravity SOTA v25.*
"""

    base_dir = os.path.dirname(os.path.abspath(__file__))
    report_file = os.path.join(base_dir, "relatorio_potencial_sota.md")
    print(f"📝 Gravando relatório em: {report_file}")

    try:
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_md)
        print("✅ Arquivo gravado com sucesso.")
    except Exception as e:
        print(f"❌ Erro ao gravar arquivo: {e}")

    print(f"Finalizado. Relatorio em: {report_file}")
    print(f"Lucro Total: R$ {profit_buys + profit_sells:.2f}")


if __name__ == "__main__":
    asyncio.run(run_audit_sota())
