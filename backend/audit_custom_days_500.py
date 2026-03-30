import asyncio
import logging
from datetime import datetime, date
import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.backtest_pro import BacktestPro

async def run_audit():
    if os.path.exists("v24_audit_report_500.md"):
        os.remove("v24_audit_report_500.md")
    
    with open("v24_audit_report_500.md", "w", encoding="utf-8") as rf:
        rf.write("# 🛡️ RELATÓRIO DE AUDITORIA SOTA V24 - CONTA R$ 500\n")
        rf.write(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n")

    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    print("=====================================================================")
    print(" 🚀 INICIANDO AUDITORIA DIÁRIA (CONTA 500 REAIS) - SOTA V24 ")
    print("=====================================================================")

    symbol = "WIN$"
    capital = 500.0

    target_dates = [
        date(2026, 2, 27), date(2026, 2, 26), date(2026, 2, 25), date(2026, 2, 24), date(2026, 2, 23),
        date(2026, 2, 20), date(2026, 2, 19), 
        date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 4), date(2026, 3, 5), date(2026, 3, 6),
        date(2026, 3, 9), date(2026, 3, 10), date(2026, 3, 11), date(2026, 3, 12), date(2026, 3, 13),
        date(2026, 3, 16), date(2026, 3, 19), date(2026, 3, 20), date(2026, 3, 23)
    ]

    param_path = os.path.join(os.path.dirname(__file__), "v24_locked_params.json")
    try:
        with open(param_path, "r", encoding="utf-8") as f:
            v24_params = json.load(f)
            print(f"✔️ Parâmetros SOTA {v24_params.get('version', 'V24')} carregados para Auditoria.")
    except Exception as e:
        print(f"❌ Erro ao ler v24_locked_params.json: {e}")
        return

    # To optimize fetching, we can fetch all data in a large chunk, then filter?
    # BacktestPro load_data() fetches typically a fixed number of candles.
    # We will instantiate a new tester per day just to be fully isolated.

    # We will fetch a large chunk once to avoid MT5 throttling or latency,
    # 20 days * 600 min/day = 12000 candles. Let's fetch 15000 candles.
    print("\n⏳ Baixando histórico MT5 de alta densidade...")
    
    global_tester = BacktestPro(
        symbol=symbol,
        n_candles=20000, 
        timeframe="M1",
        initial_balance=capital,
        base_lot=1,  # 1 lote para capital de 500
        dynamic_lot=False,
        use_ai_core=True,
    )
    all_data = await global_tester.load_data()
    
    if all_data is None or all_data.empty:
        print("❌ Falha crítica: Sem conexão ou dados do MT5.")
        return
        
    for d in target_dates:
        print(f"\n{'='*50}")
        print(f" 📅 AUDITORIA: {d.strftime('%d/%m/%Y')} ")
        print(f"{'='*50}")
        
        day_data = all_data[all_data.index.date == d].copy()
        
        if day_data.empty:
            print("⚠️ Sem dados registrados no MT5 para este dia.")
            continue
            
        # Re-instance isolated tester
        tester = BacktestPro(
            symbol=symbol,
            n_candles=100, # Fake, we will override self.data
            timeframe="M1",
            initial_balance=capital,
            base_lot=1,  # Usar 1 mini contrato para 500 BRL
            dynamic_lot=False,
            use_ai_core=True,
        )
        
        for k, v in v24_params.items():
            if k != "account_config":
                tester.opt_params[k] = v
                
        tester.data = day_data
        
        # Execute
        await tester.run()
        
        # Report
        shadow = tester.shadow_signals
        trades = tester.trades
        
        pnl = tester.balance - capital
        win_rate = (len([t for t in trades if t['pnl_fin'] > 0]) / len(trades) * 100) if trades else 0.0
        
        buy_trades = [t for t in trades if t["side"] == "buy"]
        sell_trades = [t for t in trades if t["side"] == "sell"]
        
        buy_pnl = sum([t["pnl_fin"] for t in buy_trades])
        sell_pnl = sum([t["pnl_fin"] for t in sell_trades])
        loss_total = sum([t["pnl_fin"] for t in trades if t["pnl_fin"] < 0])
        
        buy_wr = ((len([t for t in buy_trades if t["pnl_fin"] > 0]) / len(buy_trades) * 100) if buy_trades else 0)
        sell_wr = ((len([t for t in sell_trades if t["pnl_fin"] > 0]) / len(sell_trades) * 100) if sell_trades else 0)
        
        # Sugestão de Melhoria (Lógica Inteligente)
        melhoria = "Estabilidade Máxima. Manter Parâmetros."
        if pnl < 0:
            if abs(loss_total) > 50: melhoria = "Reduzir Risk-Per-Trade ou apertar ATR Veto."
            else: melhoria = "Ruído de mercado detectado. BE curto evitou perda maior."
        elif win_rate < 60:
            melhoria = "Otimizar filtros de Microestrutura (OBI/Fluxo)."

        output = [
            f"\n{'='*50}",
            f" 📅 AUDITORIA: {d.strftime('%d/%m/%Y')} ",
            f"{'='*50}",
            f"💰 PnL do Dia: R$ {pnl:.2f}",
            f"🎫 Total de Trades Disparados: {len(trades)}",
            f"🎯 Assertividade Diária: {win_rate:.2f}%\n",
            f"🛒 POTENCIAL COMPRA: {len(buy_trades)} entradas | Gain: R$ {buy_pnl:.2f} | Assertiv: {buy_wr:.2f}%",
            f"📉 POTENCIAL VENDA:  {len(sell_trades)} entradas | Gain: R$ {sell_pnl:.2f} | Assertiv: {sell_wr:.2f}%",
            f"📉 PREJUÍZO ACUMULADO: R$ {abs(loss_total):.2f}\n",
            f"🚫 PERDA OPORTUNIDADE (Vetos IA/Filtros): {shadow.get('filtered_by_ai', 0) + shadow.get('filtered_by_flux', 0)}",
            f"⚠️  Bloqueios por horário/outros: {shadow.get('component_fail', {}).get('time', 0)}",
            f"🚀 SUGESTÃO: {melhoria}"
        ]
        
        with open("v24_audit_report_500.md", "a", encoding="utf-8") as rf:
            rf.write("\n".join(output) + "\n\n")
        
        for line in output:
            print(line)

if __name__ == "__main__":
    asyncio.run(run_audit())
