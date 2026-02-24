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
    def __init__(self, bridge, calendar, interval=10):
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
            # Usamos o símbolo base WIN$ para o worker, mas o bridge lida com isso
            bluechips = await asyncio.to_thread(self.bridge.get_bluechips_data)
            
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
                "macro": macro_data if isinstance(macro_data, dict) else {"score": 0.0, "reason": "No data"},
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
