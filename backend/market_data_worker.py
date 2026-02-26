import asyncio
import logging
import json
import os
import time
from datetime import datetime

class MarketDataWorker:
    """
    Worker para coleta de dados lentos em background.
    Responsável por atualizar Blue Chips, Macro, Ajuste e Calendário.
    """
    def __init__(self, bridge, calendar, interval=2): # [ANTIVIBE-CODING]
        self.bridge = bridge
        self.calendar = calendar
        self.interval = interval
        self.output_path = os.path.join("data", "market_context.json")
        os.makedirs("data", exist_ok=True)
        self.running = True

    async def update_context(self):
        """Coleta dados e salva em arquivo JSON."""
        try:
            logging.debug("📊 MarketDataWorker: Coletando dados lentos...")
            
            # 1. Blue Chips e Sincronização Multi-Ativo
            bluechips = await asyncio.to_thread(self.bridge.get_bluechips_data)
            
            # Cálculo do Índice Sintético (Média das Variações das Blue Chips)
            # Cálculo do Índice Sintético Ponderado (Plano Mestre 2.0)
            synthetic_index = 0.0
            if bluechips and isinstance(bluechips, dict):
                weights = {
                    "VALE3": 0.14,
                    "PETR4": 0.12,
                    "ITUB4": 0.10,
                    "BBDC4": 0.10,
                    "ELET3": 0.05
                }
                weighted_sum = 0.0
                total_weight = 0.0
                for ticker, v in bluechips.items():
                    try:
                        val = float(str(v).replace("%", "").strip())
                        weight = weights.get(ticker, 0.05)
                        weighted_sum += val * weight
                        total_weight += weight
                    except (ValueError, TypeError):
                        continue
                if total_weight > 0:
                    synthetic_index = weighted_sum / total_weight

            # 2. Dados Macro
            macro_data = await asyncio.to_thread(self.bridge.get_macro_data)
            
            # 3. Calendário de Volatilidade
            vol_expected, vol_reason = self.calendar.is_volatility_expected()
            
            # 4. Preço de Ajuste (WIN$)
            settlement_price = await asyncio.to_thread(self.bridge.get_settlement_price, "WIN$")

            # Montar o pacote de contexto
            context = {
                "timestamp": time.time(),
                "bluechips": bluechips if isinstance(bluechips, dict) else {},
                "synthetic_index": float(synthetic_index),
                "macro": {"score": float(macro_data), "reason": "S&P 500 Change"} if isinstance(macro_data, (int, float)) else macro_data,
                "calendar": {
                    "volatility_expected": vol_expected,
                    "reason": str(vol_reason)
                },
                "settlement_price": float(settlement_price or 0.0)
            }


            # Escrita Atômica
            temp_path = self.output_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(context, f, indent=2)
            os.replace(temp_path, self.output_path)
            
            logging.debug("✅ MarketDataWorker: Contexto atualizado com sucesso.")
            
        except Exception as e:
            logging.error(f"❌ MarketDataWorker Error: {e}")

    async def run(self):
        logging.info(f"🚀 MarketDataWorker iniciado (Intervalo: {self.interval}s)")
        while self.running:
            try:
                await self.update_context()
            except Exception as e:
                logging.error(f"💥 Falha no ciclo do MarketDataWorker: {e}")
                await asyncio.sleep(5)
                continue
            
            await asyncio.sleep(self.interval)

    def stop(self):
        self.running = False
