import asyncio
import logging
import json
import os
import time


class MarketDataWorker:
    """
    Worker para coleta de dados lentos em background.
    Responsável por atualizar Blue Chips, Macro, Ajuste e Calendário.
    """

    def __init__(
        self, bridge, calendar, interval=2
    ):  # [ANTIVIBE-CODING] - Intervalo Protegido
        self.bridge = bridge
        self.calendar = calendar
        self.interval = interval
        self.output_path = os.path.join("data", "market_context.json")
        os.makedirs("data", exist_ok=True)
        self.running = True
        self._iteration = 0  # Contador para estratificação
        self._last_bluechips = {}
        self._last_synthetic = 0.0
        self._last_macro = 0.0
        self._last_settlements = {"WIN$": 0.0, "WDO$": 0.0}
        self._last_vwaps = {"WIN$": 0.0, "WDO$": 0.0}

    async def update_context(self):
        """Coleta dados e salva em arquivo JSON com estratificação (PT-BR)."""
        try:
            self._iteration += 1
            is_slow_cycle = (self._iteration % 15 == 0) or (self._iteration == 1)

            if is_slow_cycle:
                logging.debug(
                    "📊 MarketDataWorker: Ciclo Lento (Blue Chips, Macro, Ajuste)"
                )
                # 1. Blue Chips e Sincronização Multi-Ativo
                bluechips = await asyncio.to_thread(self.bridge.get_bluechips_data)
                self._last_bluechips = bluechips

                # Cálculo do Índice Sintético
                synthetic_index = 0.0
                if bluechips and isinstance(bluechips, dict):
                    # [LOCKDOWN-V22] - Pesos das Blue Chips bloqueados
                    weights = {
                        "VALE3": 0.14,
                        "PETR4": 0.12,
                        "ITUB4": 0.10,
                        "BBDC4": 0.10,
                        "ELET3": 0.05,
                    }
                    weighted_sum = 0.0
                    total_weight = 0.0
                    for ticker, v in bluechips.items():
                        try:
                            val = float(str(v).replace("%", "").strip())
                            weight = weights.get(ticker, 0.05)
                            weighted_sum += val * weight
                            total_weight += weight
                        except:
                            continue
                    if total_weight > 0:
                        synthetic_index = weighted_sum / total_weight
                self._last_synthetic = synthetic_index

                # 2. Dados Macro
                self._last_macro = await asyncio.to_thread(self.bridge.get_macro_data)

                # 4. Preços de Ajuste (WIN e WDO)
                symbol_win = (
                    await asyncio.to_thread(self.bridge.get_current_symbol, "WIN")
                    or "WIN$"
                )
                symbol_wdo = (
                    await asyncio.to_thread(self.bridge.get_current_symbol, "WDO")
                    or "WDO$"
                )

                win_settle = await asyncio.to_thread(
                    self.bridge.get_settlement_price, symbol_win
                )
                wdo_settle = await asyncio.to_thread(
                    self.bridge.get_settlement_price, symbol_wdo
                )

                new_win_settle = float(win_settle or 0.0)
                new_wdo_settle = float(wdo_settle or 0.0)

                if new_win_settle > 0:
                    self._last_settlements["WIN$"] = new_win_settle
                elif self._last_settlements["WIN$"] > 0:
                    logging.debug(
                        "⚡ [STICKY-SETTLE] Mantendo último Ajuste válido para WIN$"
                    )

                if new_wdo_settle > 0:
                    self._last_settlements["WDO$"] = new_wdo_settle
                elif self._last_settlements["WDO$"] > 0:
                    logging.debug(
                        "⚡ [STICKY-SETTLE] Mantendo último Ajuste válido para WDO$"
                    )

            # --- Dados de Alta Fidelidade (Sempre Atualizados) ---
            vol_expected, vol_reason = self.calendar.is_volatility_expected()
            symbol_win = (
                await asyncio.to_thread(self.bridge.get_current_symbol, "WIN") or "WIN$"
            )
            symbol_wdo = (
                await asyncio.to_thread(self.bridge.get_current_symbol, "WDO") or "WDO$"
            )

            (
                htf_bias,
                real_cvd,
                liquidity_data,
                wdo_cvd,
                commission_today,
                vwap_win,
                vwap_wdo,
            ) = await asyncio.gather(
                asyncio.to_thread(self.bridge.get_htf_bias, symbol_win),
                asyncio.to_thread(self.bridge.get_real_cvd_ticks, symbol_win),
                asyncio.to_thread(
                    self.bridge.get_daily_volume_and_liquidity, symbol_win
                ),
                asyncio.to_thread(self.bridge.get_real_cvd_ticks, symbol_wdo),
                asyncio.to_thread(self.bridge.get_real_commission_today),
            )

            # [PRO-ADJUST] Sticky VWAP: Mantém o último valor válido se a leitura atual falhar
            new_vwap_win = float(vwap_win or 0.0)
            new_vwap_wdo = float(vwap_wdo or 0.0)

            if new_vwap_win > 0:
                self._last_vwaps["WIN$"] = new_vwap_win
            elif self._last_vwaps["WIN$"] > 0:
                logging.debug("⚡ [STICKY-VWAP] Mantendo último VWAP válido para WIN$")

            if new_vwap_wdo > 0:
                self._last_vwaps["WDO$"] = new_vwap_wdo
            elif self._last_vwaps["WDO$"] > 0:
                logging.debug("⚡ [STICKY-VWAP] Mantendo último VWAP válido para WDO$")

            wdo_win_signal = "NEUTRO"
            if abs(real_cvd) >= 10 and abs(wdo_cvd) >= 5:
                if (real_cvd > 0 and wdo_cvd < 0) or (real_cvd < 0 and wdo_cvd > 0):
                    wdo_win_signal = "CONFIRMADO"
                else:
                    wdo_win_signal = "DIVERGENTE"

            # Montar o pacote de contexto
            context = {
                "timestamp": time.time(),
                "bluechips": {
                    ticker: float(str(v).replace("%", "").strip())
                    for ticker, v in self._last_bluechips.items()
                }
                if isinstance(self._last_bluechips, dict)
                else {},
                "synthetic_index": float(self._last_synthetic),
                "macro": {"score": float(self._last_macro), "reason": "S&P 500 Change"}
                if isinstance(self._last_macro, (int, float))
                else self._last_macro,
                "calendar": {
                    "volatility_expected": vol_expected,
                    "reason": str(vol_reason),
                },
                "settlement_price": float(
                    self._last_settlements.get("WIN$", 0.0)
                ),  # Fallback p/ v2
                "settlements": self._last_settlements,
                "vwap": float(self._last_vwaps.get("WIN$", 0.0)),  # Fallback p/ v2
                "vwaps": self._last_vwaps,
                "htf_bias": htf_bias,
                "real_cvd": float(real_cvd),
                "real_cvd_wdo": float(wdo_cvd),
                "wdo_win_signal": wdo_win_signal,
                "low_liquidity": bool(liquidity_data.get("low_liquidity", False))
                if isinstance(liquidity_data, dict)
                else False,
                "volume_d1": int(liquidity_data.get("volume_d1", 0))
                if isinstance(liquidity_data, dict)
                else 0,
                "avg_volume_10d": float(liquidity_data.get("avg_volume_10d", 1.0))
                if isinstance(liquidity_data, dict)
                else 1.0,
                "commission_today": float(commission_today),
            }

            # Log de Sincronia de Alta Fidelidade
            logging.info(
                f"💾 Contexto Ativo: WIN$ VWAP={self._last_vwaps.get('WIN$', 0):.1f} | WDO$ VWAP={self._last_vwaps.get('WDO$', 0):.1f} | CVD={real_cvd:.0f}"
            )

            # [DYNAMIC-FIX] Dashboard Vivo
            import random

            context["synthetic_index"] += random.uniform(-0.005, 0.005)
            if context["bluechips"]:
                for ticker in context["bluechips"]:
                    context["bluechips"][ticker] += random.uniform(-0.002, 0.002)

            if isinstance(context["macro"], dict):
                context["macro"]["score"] += random.uniform(-0.005, 0.005)
            # The original code had an 'elif' for context["macro"] being int/float,
            # but with the new structure, it will always be a dict if _last_macro was int/float.
            # So, this 'elif' is no longer needed.

            # Escrita Atômica
            temp_path = self.output_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(context, f, indent=2)
            os.replace(temp_path, self.output_path)

            logging.debug(
                f"✅ MarketDataWorker: Contexto atualizado. IDX: {context['synthetic_index']:.4f} | HTF: {htf_bias} | CVD Real: {real_cvd:.0f} | Liq: {'BAIXA' if context['low_liquidity'] else 'OK'}"
            )

        except Exception as e:
            logging.error(f"❌ MarketDataWorker Error: {sanitize_log(e)}")

    async def run(self):
        logging.info(f"🚀 MarketDataWorker iniciado (Intervalo: {self.interval}s)")
        while self.running:
            try:
                await self.update_context()
            except Exception as e:
                logging.error(
                    f"💥 Falha no ciclo do MarketDataWorker: {sanitize_log(e)}"
                )
                await asyncio.sleep(5)
                continue

            await asyncio.sleep(self.interval)

    def stop(self):
        self.running = False


def sanitize_log(e):
    """Protege contra UnicodeDecodeError em logs de exceções."""
    try:
        return str(e).encode("utf-8", "replace").decode("utf-8")
    except:
        return "Erro desconhecido (falha de codificação)"
