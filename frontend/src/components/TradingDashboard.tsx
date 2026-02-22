"use client";

import { useTradingStore, useTradingWebSocket } from "@/hooks/use-trading-ws";
import { TradingChart } from "./TradingChart";
import { FlowMeter } from "./FlowMeter";
import { OrderBookHeatmap } from "./OrderBookHeatmap";
import { SotaMetrics } from "./SotaMetrics";
import { PerformanceWidget } from "./PerformanceWidget";
import {
  AlertCircle,
  Zap,
  TrendingUp,
  ShieldAlert,
  Wifi,
  WifiOff,
  Activity,
  Bot,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { Switch } from "@/components/ui/switch"; // Assumindo shadcn
import { Label } from "@/components/ui/label";

export function TradingDashboard() {
  const { data, connected } = useTradingStore();
  const { sendOrder, setAutonomous } = useTradingWebSocket();

  // Dados SOTA (Buscando das chaves mapeadas no backend/main.py packet)
  const sotaData = {
    forecast: data?.ai_prediction?.forecast ?? data?.price ?? 0,
    // A API Python manda o "score" de 0 a 100. Frontend espera decimals para progress.
    confidence:
      (data?.ai_prediction?.score ?? data?.ai_prediction?.confidence ?? 0) /
      100,
    uncertaintyRange: data?.risk_status?.uncertainty_range ?? 0,
    unweightedOfi: data?.obi ?? 0,
    weightedOfi: data?.risk_status?.weighted_ofi ?? 0,
    regime: data?.risk_status?.regime ?? 0,
    psr: data?.risk_status?.psr ?? 0,
    syntheticIndex: data?.risk_status?.synthetic_index ?? 0,
  };

  const riskOk = data?.risk_status.time_ok && data?.risk_status.loss_ok;

  // Latency Alert Threshold
  const isHighLatency = (data?.latency_ms ?? 0) > 300;

  // Derived Metrics
  const aiScore = data?.risk_status?.ai_score ?? 0;
  const aiDirection = data?.risk_status?.ai_direction ?? "NEUTRAL";

  const isObiOk = Math.abs(data?.obi ?? 0) > 0.2; // Exemplo de threshold
  const isConfidenceOk = (data?.ai_confidence ?? 0) > 0.6;
  const sentimentValue =
    typeof data?.sentiment === "object"
      ? data.sentiment.score
      : (data?.sentiment ?? 0);
  const isSentimentOk = Math.abs(sentimentValue) > 0.1;

  const isAuthorized = riskOk && isObiOk && isConfidenceOk;

  // Autonomous State
  const [autonomousMode, setAutonomousMode] = useState(false);
  const [isUpdatingAuto, setIsUpdatingAuto] = useState(false);

  const toggleAutonomous = async () => {
    if (isUpdatingAuto) return;
    setIsUpdatingAuto(true);

    // Dispara o estado desejado para a inteligência em Python
    const newState = !autonomousMode;
    const response = await setAutonomous(newState);

    if (response?.status === "success") {
      setAutonomousMode(newState);
    } else {
      console.error("Falha ao alterar Modo Autônomo na rede");
    }

    setIsUpdatingAuto(false);
  };

  // Limits
  const limits = data?.risk_status?.limits;
  const currentPrice = data?.price ?? 0;
  const isLimitWarning = limits
    ? currentPrice > limits.upper * 0.95 || currentPrice < limits.lower * 1.05
    : false;
  const limitProgress = limits
    ? ((currentPrice - limits.lower) / (limits.upper - limits.lower)) * 100
    : 50;
  // ... (resto do código)

  return (
    <div className="flex flex-col gap-3 w-full max-w-[1600px] mx-auto p-2 md:p-4 animate-in fade-in duration-1000">
      {/* Alerta de Latência Crítica (Constituição) - Movido para o Topo Real */}
      {isHighLatency && (
        <div className="w-full bg-loss/10 border border-loss text-loss py-2 px-4 rounded-lg flex items-center justify-center gap-2 animate-pulse font-bold shadow-lg ring-1 ring-loss/50">
          <Activity size={20} />
          ALERTA DE ALTA LATÊNCIA ({data?.latency_ms.toFixed(1)}ms) - RISCO DE
          EXECUÇÃO
        </div>
      )}

      {/* Header / StatusBar */}
      <div className="flex items-center justify-between glass p-4 rounded-2xl shadow-2xl">
        <div className="flex items-center gap-6">
          <div
            className={cn(
              "flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-bold tracking-wide transition-all duration-500",
              connected
                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-[0_0_10px_rgba(52,211,153,0.2)]"
                : "bg-red-500/10 text-red-400 border border-red-500/20",
            )}
          >
            {connected ? <Wifi size={14} /> : <WifiOff size={14} />}
            {connected ? "CONECTADO MT5" : "DESCONECTADO"}
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Quantum<span className="text-emerald-500 font-light">Trade</span>{" "}
            <span className="text-[10px] align-top text-zinc-500 ml-0.5 font-mono">
              PRO
            </span>
          </h1>
          <div className="h-8 w-px bg-white/10 mx-2" />
          <div
            className={cn(
              "flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors border border-white/5 tabular-nums",
              isHighLatency
                ? "bg-red-500/10 text-red-400 animate-pulse border-red-500/30"
                : "bg-white/5 text-muted-foreground",
            )}
          >
            <Activity
              size={14}
              className={cn(
                isHighLatency ? "text-red-400" : "text-emerald-400",
              )}
            />
            <span>
              {data?.latency_ms?.toFixed(1) ?? "0.0"}ms
              {isHighLatency && " (ALTA)"}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-10">
          <div className="text-right">
            <p className="text-[10px] text-muted-foreground uppercase tracking-widest font-semibold mb-0.5">
              Resultado Dia
            </p>
            <p
              className={cn(
                "text-2xl font-mono font-bold tracking-tight",
                (data?.risk_status.profit_day ?? 0) >= 0
                  ? "text-emerald-400 text-shadow-glow-green"
                  : "text-red-400 text-shadow-glow-red",
              )}
            >
              R$ {data?.risk_status.profit_day.toFixed(2) ?? "0.00"}
            </p>
          </div>
          <div className="text-right">
            <p className="text-[10px] text-muted-foreground uppercase tracking-widest font-semibold mb-0.5">
              Patrimônio
            </p>
            <p className="text-2xl font-mono font-bold text-foreground tabular-nums tracking-tighter">
              R${" "}
              {data?.account.equity.toLocaleString("pt-BR", {
                minimumFractionDigits: 2,
              }) ?? "0,00"}
            </p>
          </div>
          <div className="h-12 w-px bg-white/10" />
          <div className="text-right">
            <p className="text-[10px] text-muted-foreground uppercase tracking-widest font-semibold mb-0.5">
              Ativo
            </p>
            <p className="text-xl font-bold text-primary">
              {data?.symbol ?? "WIN..."}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Coluna Esquerda: Métricas SOTA */}
        <div className="space-y-6 lg:col-span-1 flex flex-col">
          <SotaMetrics {...sotaData} />
          <PerformanceWidget />

          {/* Sidebar Controls */}
          <div className="flex flex-col gap-6">
            <div className="p-5 glass-heavy rounded-2xl shadow-2xl flex flex-col gap-5">
              <div className="space-y-3">
                <h3 className="font-bold text-lg flex items-center gap-2 text-white/90">
                  <Zap
                    className="text-amber-400 fill-amber-400 drop-shadow-[0_0_8px_rgba(251,191,36,0.5)]"
                    size={18}
                  />
                  Decisão da IA
                </h3>
                <div className="h-2.5 w-full bg-black/40 rounded-full overflow-hidden border border-white/5">
                  <div
                    className="h-full bg-gradient-to-r from-primary/50 to-primary transition-all duration-700 ease-out shadow-[0_0_10px_rgba(255,255,255,0.3)]"
                    style={{
                      width: `${(data?.ai_confidence ?? 0.5) * 100}%`,
                    }}
                  />
                </div>
                <div className="flex justify-between items-center text-[10px] uppercase tracking-wider font-medium">
                  <span className="text-muted-foreground">
                    Score Integrado (AI)
                  </span>
                  <span
                    className={cn(
                      "font-bold text-lg",
                      aiScore >= 85
                        ? "text-emerald-400 text-shadow-glow-green"
                        : "text-primary text-shadow-glow-blue",
                    )}
                  >
                    {aiScore}/100
                  </span>
                </div>
                <div className="flex justify-between items-center text-[10px] uppercase tracking-wider font-medium mt-1">
                  <span className="text-muted-foreground">Direção</span>
                  <span
                    className={cn(
                      "font-bold",
                      aiDirection === "BUY"
                        ? "text-emerald-400"
                        : aiDirection === "SELL"
                          ? "text-red-400"
                          : "text-muted-foreground",
                    )}
                  >
                    {aiDirection}
                  </span>
                </div>
              </div>

              {/* Faróis de Decisão (Master Plan) */}
              <div className="grid grid-cols-3 gap-2 py-3 border-y border-border/40">
                <div className="flex flex-col items-center gap-1">
                  <div
                    className={cn(
                      "w-3 h-3 rounded-full shadow-sm",
                      isObiOk ? "bg-profit animate-pulse" : "bg-muted",
                    )}
                  />
                  <span className="text-[10px] text-muted-foreground font-bold">
                    OBI
                  </span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <div
                    className={cn(
                      "w-3 h-3 rounded-full shadow-sm",
                      isConfidenceOk ? "bg-profit animate-pulse" : "bg-muted",
                    )}
                  />
                  <span className="text-[10px] text-muted-foreground font-bold">
                    IA
                  </span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <div
                    className={cn(
                      "w-3 h-3 rounded-full shadow-sm",
                      isSentimentOk ? "bg-profit animate-pulse" : "bg-muted",
                    )}
                  />
                  <span className="text-[10px] text-muted-foreground font-bold">
                    SENT
                  </span>
                </div>
              </div>

              <div className="pt-2 border-t border-border/40">
                <div className="flex justify-between items-center bg-muted/20 p-2 rounded shadow-inner">
                  <span className="text-[10px] uppercase text-muted-foreground">
                    Regime de Mercado
                  </span>
                  <span className="text-xs font-bold font-mono">
                    {data?.risk_status?.regime === 1
                      ? "📈 TENDÊNCIA"
                      : data?.risk_status?.regime === 2
                        ? "🌪️ RUÍDO"
                        : "↔️ CONSOLIDAÇÃO"}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3">
                <button
                  onClick={() => sendOrder("BUY")}
                  disabled={!isAuthorized}
                  className={cn(
                    "py-4 rounded-xl font-bold text-white transition-all transform active:scale-95 shadow-lg border border-white/10",
                    isAuthorized
                      ? "bg-gradient-to-r from-emerald-600 to-emerald-500 hover:brightness-110 cursor-pointer shadow-[0_0_20px_rgba(16,185,129,0.3)]"
                      : "bg-muted text-muted-foreground cursor-not-allowed grayscale bg-opacity-50",
                  )}
                >
                  {isAuthorized ? "COMPRA AUTORIZADA" : "AGUARDANDO SINAL"}
                </button>
                <button
                  onClick={() => sendOrder("SELL")}
                  disabled={!isAuthorized}
                  className={cn(
                    "py-3 rounded-xl font-bold border-2 transition-all active:scale-95 backdrop-blur-sm",
                    isAuthorized
                      ? "border-red-500/50 text-red-500 hover:bg-red-500/10 hover:border-red-500"
                      : "border-muted/50 text-muted-foreground cursor-not-allowed bg-muted/10",
                  )}
                >
                  VENDA (CONTRA-FLUXO)
                </button>
              </div>

              <button
                onClick={() => sendOrder("CLOSE_ALL")}
                className="py-3 rounded-xl bg-gradient-to-r from-red-600 to-red-500 font-bold text-white hover:brightness-110 active:scale-95 shadow-[0_0_20px_rgba(239,68,68,0.4)] flex items-center justify-center gap-2 border border-white/10"
              >
                <AlertCircle size={20} />
                ZERAR TUDO (PANIC)
              </button>

              <div className="pt-4 mt-2 border-t border-border/40 flex flex-col gap-4">
                <div className="flex items-center justify-between p-3 bg-primary/5 rounded-lg border border-primary/20">
                  <div className="flex items-center gap-2">
                    <Bot
                      className={cn(
                        "w-5 h-5",
                        autonomousMode
                          ? "text-profit"
                          : "text-muted-foreground",
                      )}
                    />
                    <div>
                      <Label
                        htmlFor="auto-mode"
                        className="text-xs font-bold block"
                      >
                        MODO AUTÔNOMO
                      </Label>
                      <span className="text-[10px] text-muted-foreground leading-none">
                        Score &gt; 90
                      </span>
                    </div>
                  </div>
                  <Switch
                    id="auto-mode"
                    checked={autonomousMode}
                    onCheckedChange={toggleAutonomous}
                    disabled={isUpdatingAuto}
                  />
                </div>

                {autonomousMode && (
                  <div className="bg-profit/10 text-profit p-2 rounded text-[10px] font-medium animate-pulse text-center border border-profit/20">
                    SISTEMA AUTORIZADO PARA OPERAR SOZINHO
                  </div>
                )}
              </div>
            </div>

            <div className="p-4 glass rounded-2xl border-dashed flex flex-col gap-3">
              <h4 className="text-[10px] font-bold text-muted-foreground uppercase flex items-center gap-2 tracking-widest">
                <ShieldAlert size={14} className="text-primary" />
                Trava de Risco
              </h4>
              <ul className="text-xs space-y-2 font-medium">
                <li className="flex justify-between items-center">
                  <span className="text-muted-foreground">
                    Horário Operacional
                  </span>
                  <span
                    className={cn(
                      "px-2 py-0.5 rounded text-[10px] font-bold border",
                      riskOk
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                        : "bg-red-500/10 text-red-400 border-red-500/20",
                    )}
                  >
                    {data?.risk_status.time_ok ? "OK" : "BLOQUEADO"}
                  </span>
                </li>
                <li className="flex justify-between items-center">
                  <span className="text-muted-foreground">
                    Limite de Perda (R$ 200)
                  </span>
                  <span
                    className={cn(
                      "px-2 py-0.5 rounded text-[10px] font-bold border",
                      riskOk
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                        : "bg-red-500/10 text-red-400 border-red-500/20",
                    )}
                  >
                    {data?.risk_status.loss_ok ? "OK" : "ATINGIDO"}
                  </span>
                </li>

                {/* Compliance / Túneis */}
                {limits && limits.upper > 0 && (
                  <li className="pt-2 border-t border-white/5 flex flex-col gap-1">
                    <div className="flex justify-between items-center text-[10px] uppercase text-muted-foreground">
                      <span>Túneis de Negociação</span>
                      <span
                        className={cn(
                          isLimitWarning ? "text-red-400" : "text-emerald-400",
                        )}
                      >
                        {isLimitWarning ? "ALERTA" : "NORMAL"}
                      </span>
                    </div>
                    <div className="h-1.5 w-full bg-black/40 rounded-full overflow-hidden border border-white/5 relative">
                      {/* Background Zone */}
                      <div className="absolute inset-0 bg-gradient-to-r from-red-500/30 via-transparent to-red-500/30 opacity-50" />

                      {/* Indicator */}
                      <div
                        className={cn(
                          "h-full transition-all duration-700 ease-out shadow-[0_0_5px_currentColor]",
                          isLimitWarning ? "bg-red-500" : "bg-emerald-500",
                        )}
                        style={{
                          width: "4px",
                          marginLeft: `${Math.min(100, Math.max(0, limitProgress))}%`,
                          transform: "translateX(-50%)",
                        }}
                      />
                    </div>
                    <div className="flex justify-between text-[8px] text-muted-foreground font-mono">
                      <span>{limits.lower.toFixed(0)}</span>
                      <span>{currentPrice.toFixed(0)}</span>
                      <span>{limits.upper.toFixed(0)}</span>
                    </div>
                  </li>
                )}
              </ul>
            </div>
          </div>
        </div>

        {/* Main Chart Area */}
        <div className="lg:col-span-3 flex flex-col gap-6">
          <TradingChart />

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 glass rounded-2xl shadow-lg flex flex-col gap-2">
              <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-semibold">
                Sentimento (Gemini)
              </span>
              <div className="flex items-center justify-between">
                <span className="text-3xl font-bold bg-gradient-to-r from-white to-white/70 bg-clip-text text-transparent">
                  {(typeof data?.sentiment === "object"
                    ? data.sentiment.score
                    : (data?.sentiment ?? 0)
                  ).toFixed(2)}
                </span>
                <TrendingUp
                  className={cn(
                    "w-6 h-6",
                    (typeof data?.sentiment === "object"
                      ? data.sentiment.score
                      : (data?.sentiment ?? 0)) > 0
                      ? "text-emerald-400"
                      : "text-red-400",
                  )}
                />
              </div>
            </div>

            {/* Termômetro Blue Chips (New Quant Feature) */}
            <div className="p-4 glass rounded-2xl shadow-lg flex flex-col gap-2">
              <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-semibold">
                Blue Chips (IBOV)
              </span>
              <div className="flex items-center justify-between">
                <span
                  className={cn(
                    "text-3xl font-bold bg-clip-text text-transparent",
                    (data?.risk_status?.synthetic_index ??
                      data?.synthetic_index ??
                      0) > 0
                      ? "bg-gradient-to-r from-emerald-400 to-emerald-600"
                      : (data?.risk_status?.synthetic_index ??
                            data?.synthetic_index ??
                            0) < 0
                        ? "bg-gradient-to-r from-red-400 to-red-600"
                        : "bg-gradient-to-r from-gray-400 to-gray-600",
                  )}
                >
                  {(
                    data?.risk_status?.synthetic_index ??
                    data?.synthetic_index ??
                    0
                  ).toFixed(2)}
                  %
                </span>
                <Activity
                  className={cn(
                    "w-6 h-6",
                    (data?.risk_status?.synthetic_index ??
                      data?.synthetic_index ??
                      0) > 0.1
                      ? "text-emerald-400 animate-pulse"
                      : (data?.risk_status?.synthetic_index ??
                            data?.synthetic_index ??
                            0) < -0.1
                        ? "text-red-400 animate-pulse"
                        : "text-muted-foreground",
                  )}
                />
              </div>
              <span className="text-[10px] text-muted-foreground">
                {(data?.risk_status?.synthetic_index ??
                  data?.synthetic_index ??
                  0) > 0.1
                  ? "Suporte de Alta"
                  : (data?.risk_status?.synthetic_index ??
                        data?.synthetic_index ??
                        0) < -0.1
                    ? "Pressão de Venda"
                    : "Neutro"}
              </span>
            </div>
            <div className="md:col-span-2">
              <FlowMeter />
            </div>
          </div>

          {/* Heatmap L2 (Novo - Phase 29) */}
          <OrderBookHeatmap />
        </div>
      </div>
    </div>
  );
}
