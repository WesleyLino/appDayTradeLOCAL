import asyncio
import pandas as pd
import json
import os
from backend.backtest_pro import BacktestPro


async def analise_dia():
    print("======= ANALISANDO PERFORMANCE 06/03/2026 =======")

    # Carregar parâmetros V22 GOLDEN
    params_path = "backend/v22_locked_params.json"
    with open(params_path, "r", encoding="utf-8") as f:
        params = json.load(f)

    # Configurar Backtest para o dia 06/03
    # Nota: BacktestPro carrega os dados do arquivo MASTER se data_file for None,
    # mas aqui vamos carregar e filtrar explicitamente para o dia 06/03.

    data_file = "data/sota_training/training_WIN$_MASTER.csv"
    df = pd.read_csv(data_file)
    df["time"] = pd.to_datetime(df["time"])

    # Filtrar dia 06/03
    day_df = df[
        (df["time"] >= "2026-03-06 09:00:00") & (df["time"] <= "2026-03-06 18:00:00")
    ].copy()

    if day_df.empty:
        print("Erro: Nenhum dado encontrado para 06/03 no arquivo MASTER.")
        return

    # Salvar temporariamente para o BacktestPro ler
    temp_csv = "data/sota_training/temp_0603.csv"
    day_df.to_csv(temp_csv, index=False)

    # Instanciar BacktestPro com os parâmetros GOLDEN
    bt = BacktestPro(symbol="WIN$", data_file=temp_csv, **params["strategy_params"])

    print(f"Iniciando simulação com {len(day_df)} candles...")
    await bt.run()

    # Gerar Relatório
    report = bt.generate_report()

    print("\n======= RESULTADOS 06/03 =======")
    print(f"Saldo Final: {bt.balance:.2f}")
    print(f"Trades Totais: {len(bt.trades)}")

    # Analisar Assertividade por Direção
    buys = [t for t in bt.trades if t["type"] == "BUY"]
    sells = [t for t in bt.trades if t["type"] == "SELL"]

    win_buys = [t for t in buys if t["profit"] > 0]
    win_sells = [t for t in sells if t["profit"] > 0]

    print(
        f"Assertividade COMPRA: {len(win_buys)}/{len(buys)} ({len(win_buys) / len(buys) * 100:.1f}%)"
        if buys
        else "Nenhuma COMPRA"
    )
    print(
        f"Assertividade VENDA: {len(win_sells)}/{len(sells)} ({len(win_sells) / len(sells) * 100:.1f}%)"
        if sells
        else "Nenhuma VENDA"
    )

    # Identificar Perdas de Oportunidades (Sinais SOTA fortes que foram ignorados por algum filtro)
    # No Log do BacktestPro, poderíamos interceptar onde os filtros barraram.

    print("\n======= DETECÇÃO DE OPORTUNIDADES PERDIDAS =======")
    # Simulação rápida: verificar onde confidence > threshold mas algum outro filtro barrou
    # Para isso, precisamos olhar as colunas de sinal do SOTA se existirem.

    # Limpeza
    if os.path.exists(temp_csv):
        os.remove(temp_csv)


if __name__ == "__main__":
    asyncio.run(analise_dia())
