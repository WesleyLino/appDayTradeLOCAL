import asyncio
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import sys
import os

# Adiciona diretório raiz para imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.backtest_pro import BacktestPro
from backend.risk_manager import RiskManager

class AlphaXBacktest(BacktestPro):
    """
    Motor de Backtest especializado para AlphaX v2.1.
    Herda do BacktestPro e injeta lógicas rígidas de R$ 3000 de capital.
    """
    def __init__(self, **kwargs):
        # Primeiro inicializamos o super com o símbolo correto, removendo-o de kwargs se presente
        symbol = kwargs.pop('symbol', "WIN$")
        super().__init__(symbol=symbol, **kwargs)
        
        # Força parâmetros AlphaX v2.1 para o capital de R$ 3000
        self.opt_params['base_lot'] = 1             # Começa com 1 contrato
        self.opt_params['dynamic_lot'] = True       # Ativa Alpha Force (escalonamento)
        self.opt_params['daily_trade_limit'] = 3    # Limite conservador
        self.opt_params['be_trigger'] = 50.0        # Breakeven em 50 pts
        self.opt_params['be_lock'] = 0.0            # Trava no preço de entrada
        self.opt_params['trailing_trigger'] = 70.0  # Trailing ativa em 70 pts
        self.opt_params['trailing_lock'] = 50.0     # Garante 50 pts
        
        # Novas Métricas AlphaX v2.1
        self.velocity_time_limit_sec = 20.0
        self.velocity_drawdown_limit = -30.0
        self.alpha_fade_timeout = 10.0
        
        # Acoplamento de resultados
        self.long_pnl = 0.0
        self.short_pnl = 0.0
        self.long_trades = 0
        self.short_trades = 0
        self.velocity_exits = 0
        self.fade_expirations = 0

    def simulate_oco(self, row, position):
        """
        Sobrescreve a simulação OCO para incluir o Velocity Limit (AlphaX v2.1).
        """
        side = position['side']
        entry = position['entry_price']
        
        # [ALPHAX] Velocity Limit Check
        # Simulação simplificada para M1: se o candle for contra a posição em -30 pts.
        current_pnl_pts = (row['close'] - entry) if side == 'buy' else (entry - row['close'])
        
        if current_pnl_pts <= self.velocity_drawdown_limit:
            # Em M1, consideramos que o Velocity Limit (20s) abortaria aqui.
            self.velocity_exits += 1
            return 'VELOCITY_LIMIT', (entry + self.velocity_drawdown_limit) if side == 'buy' else (entry - self.velocity_drawdown_limit)

        # Segue a lógica padrão do BacktestPro para SL/TP/Trailing
        return super().simulate_oco(row, position)

async def run_audit():
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    symbol = "WIN$" # Mini Índice Contínuo
    capital = 3000.0
    
    # Datas solicitadas (Fevereiro 2026)
    target_dates = ["19/02/2026", "20/02/2026", "23/02/2026", "24/02/2026", "25/02/2026", "26/02/2026", "27/02/2026"]
    
    output_report = "# 📊 Auditoria AlphaX v2.1: Relatório de Fevereiro 2026\n"
    output_report += f"**Ativo**: {symbol} | **Capital**: R$ {capital:.2f} | **Foco**: Mini Índice (WIN)\n\n"
    output_report += "| Data | PnL Total | Trades | Compra (PnL) | Venda (PnL) | Win Rate | Velocity Exits | Lote Max |\n"
    output_report += "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |\n"

    total_pnl = 0.0
    total_trades_count = 0
    total_wins = 0
    
    logging.info("📥 Conectando ao MetaTrader 5 para coleta de histórico especializado...")
    tester_data = AlphaXBacktest(symbol=symbol, n_candles=15000)
    full_df = await tester_data.load_data()
    
    if full_df is None or full_df.empty:
        logging.error("❌ Falha crítica: Verifique se o MT5 está conectado e o símbolo WIN$ visível.")
        return

    for date_str in target_dates:
        target_date = datetime.strptime(date_str, "%d/%m/%Y").date()
        
        mask = full_df.index.date == target_date
        if not any(mask):
            output_report += f"| {date_str} | **SEM DADOS** | - | - | - | - | - | - |\n"
            continue
            
        day_index = full_df.index.get_loc(full_df[mask].index[0])
        start_idx = max(0, day_index - 100) # Buffer para indicadores
        end_idx = full_df.index.get_loc(full_df[mask].index[-1]) + 1
        day_data = full_df.iloc[start_idx:end_idx].copy()
        
        tester = AlphaXBacktest(
            symbol=symbol,
            initial_balance=capital,
            base_lot=1
        )
        tester.data = day_data
        
        # Executar Simulação do Pregão
        await tester.run()
        
        # Filtrar trades que iniciaram no dia
        trades = [t for t in tester.trades if t['entry_time'].date() == target_date]
        
        day_pnl = sum(t['pnl_fin'] for t in trades)
        total_pnl += day_pnl
        
        buy_trades = [t for t in trades if t['side'] == 'buy']
        sell_trades = [t for t in trades if t['side'] == 'sell']
        
        wins = len([t for t in trades if t['pnl_fin'] > 0])
        wr = (wins / len(trades) * 100) if trades else 0
        
        total_trades_count += len(trades)
        total_wins += wins
        
        max_lot = max([t.get('lots', 1) for t in trades]) if trades else 1
        v_exits = len([t for t in trades if t.get('reason') == 'VELOCITY_LIMIT'])
        
        row_str = f"| {date_str} | **R$ {day_pnl:.2f}** | {len(trades)} | {len(buy_trades)} (R$ {sum(t['pnl_fin'] for t in buy_trades):.2f}) | {len(sell_trades)} (R$ {sum(t['pnl_fin'] for t in sell_trades):.2f}) | {wr:.1f}% | {v_exits} | Lote {max_lot} |"
        output_report += row_str + "\n"
        logging.info(f"✅ Dia {date_str} processado com sucesso.")

    final_wr = (total_wins / total_trades_count * 100) if total_trades_count else 0
    output_report += "\n\n### 🏆 Resultado Consolidado AlphaX\n"
    output_report += f"- **PnL Acumulado (7 Dias)**: R$ {total_pnl:.2f}\n"
    output_report += f"- **Retorno sobre Capital**: {(total_pnl/capital*100):.2f}%\n"
    output_report += f"- **Assertividade Média**: {final_wr:.1f}%\n"
    output_report += f"- **Total de Operações**: {total_trades_count}\n"
    
    # Salvar em Markdown e printar no console
    with open("backend/audit_alphax_results.md", "w", encoding="utf-8") as f:
        f.write(output_report)
        
    print("\n" + output_report)

if __name__ == "__main__":
    asyncio.run(run_audit())
