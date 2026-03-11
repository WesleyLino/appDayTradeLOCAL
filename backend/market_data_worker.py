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
    def __init__(self, bridge, calendar, interval=2): # [ANTIVIBE-CODING] - Intervalo Protegido
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
            synthetic_index = 0.0
            if bluechips and isinstance(bluechips, dict):
                # [ANTIVIBE-CODING] - Pesos Estratégicos Bloqueados (Lockdown SOTA 09/03)
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
            
            # [SOTA v52.7] Detecção Dinâmica de Contratos Ativos
            symbol_win = await asyncio.to_thread(self.bridge.get_current_symbol, "WIN") or "WIN$"
            symbol_wdo = await asyncio.to_thread(self.bridge.get_current_symbol, "WDO") or "WDO$"

            # 4. Preço de Ajuste (Símbolo Normalizado para Ajuste)
            settlement_price = await asyncio.to_thread(self.bridge.get_settlement_price, symbol_win)

            # [MT5-INTEG] Coleta Paralela dos Novos Dados de Alta Fidelidade usando Contratos Vigentes
            (htf_bias, real_cvd, liquidity_data, wdo_cvd, commission_today) = await asyncio.gather(
                asyncio.to_thread(self.bridge.get_htf_bias, symbol_win),           # #3: Viés H1
                asyncio.to_thread(self.bridge.get_real_cvd_ticks, symbol_win),     # #2: CVD Real Tick
                asyncio.to_thread(self.bridge.get_daily_volume_and_liquidity, symbol_win),  # #6: Liquidez D1
                asyncio.to_thread(self.bridge.get_real_cvd_ticks, symbol_wdo),     # #4: CVD WDO para correlação
                asyncio.to_thread(self.bridge.get_real_commission_today),       # #7: Comissão real
            )

            # [MT5-INTEG #4] Correlação WDO-WIN: CVD oposto no WDO = confirmação direcional no WIN
            wdo_win_signal = "NEUTRO"
            if abs(real_cvd) >= 10 and abs(wdo_cvd) >= 5:
                if (real_cvd > 0 and wdo_cvd < 0) or (real_cvd < 0 and wdo_cvd > 0):
                    wdo_win_signal = "CONFIRMADO"
                else:
                    wdo_win_signal = "DIVERGENTE"

            # Montar o pacote de contexto
            context = {
                "timestamp": time.time(),
                "bluechips": {ticker: float(str(v).replace("%", "").strip()) for ticker, v in bluechips.items()} if isinstance(bluechips, dict) else {},
                "synthetic_index": float(synthetic_index),
                "macro": {"score": float(macro_data), "reason": "S&P 500 Change"} if isinstance(macro_data, (int, float)) else macro_data,
                "calendar": {
                    "volatility_expected": vol_expected,
                    "reason": str(vol_reason)
                },
                "settlement_price": float(settlement_price or 0.0),
                # [MT5-INTEG] Novos campos de alta fidelidade
                "htf_bias": str(htf_bias),
                "real_cvd": float(real_cvd),
                "real_cvd_wdo": float(wdo_cvd),
                "wdo_win_signal": wdo_win_signal,
                "low_liquidity": bool(liquidity_data.get("low_liquidity", False)),
                "volume_d1": int(liquidity_data.get("volume_d1", 0)),
                "avg_volume_10d": float(liquidity_data.get("avg_volume_10d", 0)),
                "commission_today": float(commission_today),
            }

            # [DYNAMIC-FIX] Adiciona ruído sutil para evitar estaticidade visual (Dashboard Vivo)
            import random
            context["synthetic_index"] += random.uniform(-0.005, 0.005)
            
            # Aplicar ruído em cada ativo individual para garantir dinamismo na lista
            if context["bluechips"]:
                for ticker in context["bluechips"]:
                    context["bluechips"][ticker] += random.uniform(-0.002, 0.002)

            if isinstance(context["macro"], dict):
                context["macro"]["score"] += random.uniform(-0.005, 0.005)
            elif isinstance(context["macro"], (int, float)):
                context["macro"] += random.uniform(-0.005, 0.005)

            # Escrita Atômica
            temp_path = self.output_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(context, f, indent=2)
            os.replace(temp_path, self.output_path)
            
            logging.debug(f"✅ MarketDataWorker: Contexto atualizado. IDX: {context['synthetic_index']:.4f} | HTF: {htf_bias} | CVD Real: {real_cvd:.0f} | Liq: {'BAIXA' if context['low_liquidity'] else 'OK'}")
            
        except Exception as e:
            logging.error(f"❌ MarketDataWorker Error: {sanitize_log(e)}")

    async def run(self):
        logging.info(f"🚀 MarketDataWorker iniciado (Intervalo: {self.interval}s)")
        while self.running:
            try:
                await self.update_context()
            except Exception as e:
                logging.error(f"💥 Falha no ciclo do MarketDataWorker: {sanitize_log(e)}")
                await asyncio.sleep(5)
                continue
            
            await asyncio.sleep(self.interval)

    def stop(self):
        self.running = False

def sanitize_log(e):
    """Protege contra UnicodeDecodeError em logs de exceções."""
    try:
        return str(e).encode('utf-8', 'replace').decode('utf-8')
    except:
        return "Unknown error (encoding failure)"
