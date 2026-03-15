import asyncio
import logging
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from backend.mt5_bridge import MT5Bridge
from backend.backtest_pro import BacktestPro
from backend.ai_core import AICore

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class MassAuditMotor:
    def __init__(self, symbol="WIN$N", timeframe="M1", days_back=90):
        self.symbol = symbol
        self.timeframe = timeframe
        self.days_back = days_back
        self.bridge = MT5Bridge()
        self.ai = AICore()
        self.results = []

    async def run_audit(self):
        logging.info(
            f"🔍 Iniciando Auditoria Global para {self.symbol} ({self.days_back} dias)"
        )

        if not self.bridge.connect():
            logging.error("❌ Falha ao conectar ao MT5")
            return

        # 1. Definir Janela de Tempo
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.days_back)

        current_day = start_date
        while current_day <= end_date:
            if current_day.weekday() < 5:  # Apenas dias de semana (seg-sex)
                await self.audit_day(current_day)
            current_day += timedelta(days=1)

        self.bridge.disconnect()
        self.generate_summary_report()

    async def audit_day(self, day_date):
        day_str = day_date.strftime("%Y-%m-%d")
        logging.info(f"📅 Processando Dia: {day_str}")

        start_ts = int(datetime.combine(day_date, datetime.min.time()).timestamp())
        end_ts = int(datetime.combine(day_date, datetime.max.time()).timestamp())

        configs = [
            {"name": "LEGACY_V22", "use_ai": False, "params": {}},
            {"name": "SOTA_V2_AI", "use_ai": True, "params": {}},
        ]

        day_result = {"date": day_str}

        # 2. Buscar Dados com Padding para Indicadores (Ex: 1 hora antes do pregão)
        # Pregão B3: 09:00 - 18:00. Buscamos a partir das 08:00 para padding.
        date_from = day_date.replace(hour=8, minute=0, second=0)
        date_to = day_date.replace(hour=18, minute=30, second=0)

        for cfg in configs:
            try:
                backtester = BacktestPro(
                    symbol=self.symbol,
                    use_ai_core=cfg["use_ai"],
                    initial_balance=5000.0,
                )

                # Usar o novo método de range
                data = self.bridge.get_market_data_range(
                    self.symbol, mt5.TIMEFRAME_M1, date_from, date_to
                )

                if data is None or data.empty:
                    logging.warning(f"⚠️ Sem dados para {day_str} ({cfg['name']})")
                    continue

                # O BacktestPro vai recalcular indicadores sobre o 'data' injetado
                backtester.data = data
                await backtester.run()

                # Coletar métricas
                df_trades = pd.DataFrame(backtester.trades)
                pnl = df_trades["pnl_fin"].sum() if not df_trades.empty else 0.0
                win_rate = (
                    (len(df_trades[df_trades["pnl_fin"] > 0]) / len(df_trades) * 100)
                    if not df_trades.empty
                    else 0.0
                )

                day_result[f"{cfg['name']}_pnl"] = pnl
                day_result[f"{cfg['name']}_trades"] = len(df_trades)
                day_result[f"{cfg['name']}_winrate"] = win_rate

            except Exception as e:
                logging.error(f"❌ Erro no dia {day_str} ({cfg['name']}): {e}")

        self.results.append(day_result)

    def generate_summary_report(self):
        if not self.results:
            logging.error("❌ Nenhum resultado coletado para gerar relatório.")
            return

        df = pd.DataFrame(self.results)

        # Garantir que todas as colunas esperadas existam
        expected_cols = [
            "LEGACY_V22_pnl",
            "LEGACY_V22_trades",
            "LEGACY_V22_winrate",
            "SOTA_V2_AI_pnl",
            "SOTA_V2_AI_trades",
            "SOTA_V2_AI_winrate",
        ]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = 0.0

        df = df.fillna(0.0)
        df.to_csv("mass_audit_results.csv", index=False)

        # Consolidação
        total_legacy_pnl = df["LEGACY_V22_pnl"].sum()
        total_sota_pnl = df["SOTA_V2_AI_pnl"].sum()

        logging.info("\n" + "=" * 50)
        logging.info("📊 RESUMO DA AUDITORIA GLOBAL")
        logging.info("=" * 50)
        logging.info(f"Total Dias: {len(df)}")
        logging.info(f"PnL Acumulado LEGACY: R$ {total_legacy_pnl:.2f}")
        logging.info(f"PnL Acumulado SOTA V2: R$ {total_sota_pnl:.2f}")
        logging.info(f"Melhoria Absoluta: R$ {total_sota_pnl - total_legacy_pnl:.2f}")
        logging.info("=" * 50)


if __name__ == "__main__":
    motor = MassAuditMotor(days_back=10)
    asyncio.run(motor.run_audit())
