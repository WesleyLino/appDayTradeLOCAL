"use client";

import { useTradingStore, useTradingWebSocket } from "@/hooks/use-trading-ws";
import { API_CONFIG } from "@/lib/api-config";
import { TradingChart } from "./TradingChart";
import { FlowMeter } from "./FlowMeter";
import { OrderBookHeatmap } from "./OrderBookHeatmap";
import { SotaMetrics } from "./SotaMetrics";
import { ConfluenceGauge } from "./ConfluenceGauge";
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
  ListTodo,
  Info,
  AlertTriangle,
  XCircle,
  CheckCircle,
  ArrowDown,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { Switch } from "@/components/ui/switch"; // Assumindo shadcn
import { Label } from "@/components/ui/label";

export function TradingDashboard() {
  const { data, connected } = useTradingStore();
  const {
    sendOrder,
    setAutonomous,
    startSniper,
    stopSniper,
    toggleNewsFilter,
    toggleCalendarFilter,
    toggleMacroFilter,
  } = useTradingWebSocket();

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
    macroIndex: data?.macro?.score ?? 0,
    lotMultiplier: data?.ai_prediction?.lot_multiplier ?? 1.0,
  };

  const riskOk = data?.risk_status.time_ok && data?.risk_status.loss_ok;

  // Latency Alert Threshold
  const isHighLatency = (data?.latency_ms ?? 0) > 300;

  // Derived Metrics
  const aiScore = data?.ai_prediction?.score ?? 0;
  const aiDirection = data?.ai_prediction?.direction ?? "NEUTRO";
  const aiVeto = data?.ai_prediction?.veto ?? null;

  const isObiOk = Math.abs(data?.obi ?? 0) > 0.2; // Exemplo de threshold
  const isConfidenceOk = (data?.ai_confidence ?? 0) > 0.6;
  const sentimentValue =
    typeof data?.sentiment === "object"
      ? data.sentiment.score
      : (data?.sentiment ?? 0);
  const isSentimentOk = Math.abs(sentimentValue) > 0.1;

  const isAuthorized = riskOk && isObiOk && isConfidenceOk;

  // [ANTIVIBE-CODING] - Sincronização de Estado Autônomo via WebSocket
  const [autonomousMode, setAutonomousMode] = useState(false);
  const [isUpdatingAuto, setIsUpdatingAuto] = useState(false);

  // Estados para os novos filtros Manuais
  const [newsFilterEnabled, setNewsFilterEnabled] = useState(true);
  const [calendarFilterEnabled, setCalendarFilterEnabled] = useState(true);
  const [macroFilterEnabled, setMacroFilterEnabled] = useState(true);
  const [isUpdatingFilters, setIsUpdatingFilters] = useState(false);

  // Buscar estado inicial ao carregar a página
  useEffect(() => {
    fetch(`${API_CONFIG.http}/config/filters`)
      .then((res) => res.json())
      .then((json) => {
        if (json.status === "success") {
          setNewsFilterEnabled(json.news);
          setCalendarFilterEnabled(json.calendar);
          setMacroFilterEnabled(json.macro ?? true);
        }
      })
      .catch((err) =>
        console.error("Erro ao carregar configurações de filtro:", err),
      );
  }, []);

  const handleToggleNews = async () => {
    console.log(
      "[DEBUG] handleToggleNews called. isUpdatingFilters:",
      isUpdatingFilters,
    );
    if (isUpdatingFilters) return;
    setIsUpdatingFilters(true);
    const newState = !newsFilterEnabled;
    const response = await toggleNewsFilter(newState);
    console.log("[DEBUG] handleToggleNews response:", response);
    if (response?.status === "success") {
      setNewsFilterEnabled(newState);
    }
    setTimeout(() => setIsUpdatingFilters(false), 500);
  };

  const handleToggleCalendar = async () => {
    console.log(
      "[DEBUG] handleToggleCalendar called. isUpdatingFilters:",
      isUpdatingFilters,
    );
    if (isUpdatingFilters) return;
    setIsUpdatingFilters(true);
    const newState = !calendarFilterEnabled;
    const response = await toggleCalendarFilter(newState);
    console.log("[DEBUG] handleToggleCalendar response:", response);
    if (response?.status === "success") {
      setCalendarFilterEnabled(newState);
    }
    setTimeout(() => setIsUpdatingFilters(false), 500);
  };

  const handleToggleMacro = async () => {
    console.log(
      "[DEBUG] handleToggleMacro called. isUpdatingFilters:",
      isUpdatingFilters,
    );
    if (isUpdatingFilters) return;
    setIsUpdatingFilters(true);
    const newState = !macroFilterEnabled;
    const response = await toggleMacroFilter(newState);
    console.log("[DEBUG] handleToggleMacro response:", response);
    if (response?.status === "success") {
      setMacroFilterEnabled(newState);
    }
    setTimeout(() => setIsUpdatingFilters(false), 500);
  };

  // Sincroniza estado local com dado do servidor quando o pacote chega
  useEffect(() => {
    // [ANTIVIBE-CODING] - Proteção contra pacotes parciais (Hb)
    if (
      data?.risk_status &&
      data.risk_status.allow_autonomous !== undefined &&
      !isUpdatingAuto
    ) {
      setAutonomousMode(data.risk_status.allow_autonomous);
    }
  }, [data?.risk_status?.allow_autonomous, isUpdatingAuto]);

  const toggleAutonomous = async () => {
    if (isUpdatingAuto) return;
    setIsUpdatingAuto(true);

    const newState = !autonomousMode;
    const response = await setAutonomous(newState);

    if (response?.status === "success") {
      // O estado será atualizado pelo próximo pacote de WebSocket via useEffect
      setAutonomousMode(newState);
    } else {
      console.error("Falha ao alterar Modo Autônomo na rede");
    }

    // Delay curto para evitar flickering antes do próximo tick do WS
    setTimeout(() => setIsUpdatingAuto(false), 500);
  };

  // Controle de Estado dos Logs
  const [logFilter, setLogFilter] = useState<
    "TODOS" | "INFO" | "SUCESSO" | "ALERTA" | "ERRO"
  >("TODOS");
  const [isAutoScroll, setIsAutoScroll] = useState(true);
  const logContainerRef = useRef<HTMLDivElement>(null);

  const handleLogScroll = () => {
    if (!logContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = logContainerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 10;
    setIsAutoScroll(isAtBottom);
  };

  useEffect(() => {
    if (isAutoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [data?.logs, isAutoScroll]);

  const filteredLogs =
    data?.logs?.filter((log: any) => {
      if (logFilter === "TODOS") return true;
      const typeMap: Record<string, string> = {
        SUCCESS: "SUCESSO",
        WARNING: "ALERTA",
        ERROR: "ERRO",
        INFO: "INFO",
      };
      return (
        (typeMap[log.type.toUpperCase()] || log.type.toUpperCase()) ===
        logFilter
      );
    }) ?? [];

  const formatLogMessage = (msg: string) => {
    if (!msg) return msg;
    const parts = msg.split(
      /(\bCOMPRA\b|\bBUY\b|\bVENDA\b|\bSELL\b|R\$\s?[\d.,]+|[\d.,]+%)/g,
    );

    return parts.map((part, i) => {
      if (/COMPRA|BUY/.test(part))
        return (
          <span
            key={i}
            className="text-emerald-400 font-bold px-1 py-[1px] bg-emerald-500/10 border border-emerald-500/20 rounded-md shadow-sm"
          >
            {part}
          </span>
        );
      if (/VENDA|SELL/.test(part))
        return (
          <span
            key={i}
            className="text-red-400 font-bold px-1 py-[1px] bg-red-500/10 border border-red-500/20 rounded-md shadow-sm"
          >
            {part}
          </span>
        );
      if (/R\$|%/.test(part))
        return (
          <span key={i} className="text-amber-400 font-bold">
            {part}
          </span>
        );
      return part;
    });
  };

  // Mapeamento de Cores e Ícones por Tipo
  const LOG_COLORS = {
    success: "text-emerald-400",
    warning: "text-amber-400",
    error: "text-red-400",
    info: "text-blue-400",
  };

  const LOG_ICONS = {
    success: <CheckCircle size={14} className="text-emerald-400 shrink-0" />,
    warning: <AlertTriangle size={14} className="text-amber-400 shrink-0" />,
    error: <XCircle size={14} className="text-red-400 shrink-0" />,
    info: <Info size={14} className="text-blue-400 shrink-0" />,
    SUCESSO: <CheckCircle size={14} className="text-emerald-400 shrink-0" />,
    ALERTA: <AlertTriangle size={14} className="text-amber-400 shrink-0" />,
    ERRO: <XCircle size={14} className="text-red-400 shrink-0" />,
    INFO: <Info size={14} className="text-blue-400 shrink-0" />,
  };

  // Sniper Bot State (Mapped to backend telemetry)
  const isSniperRunning = data?.risk_status?.sniper?.running ?? false;
  const [isUpdatingSniper, setIsUpdatingSniper] = useState(false);

  const toggleSniper = async () => {
    if (isUpdatingSniper) return;
    setIsUpdatingSniper(true);

    const newState = !isSniperRunning;
    const response = newState ? await startSniper() : await stopSniper();

    if (response?.status !== "success") {
      console.error("Falha ao alterar Sniper Bot na rede");
    }

    setIsUpdatingSniper(false);
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
          ALERTA DE ALTA LATÊNCIA ({(data?.latency_ms ?? 0).toFixed(1)}ms) -
          RISCO DE EXECUÇÃO
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
                (data?.risk_status?.profit_day ?? 0) >= 0
                  ? "text-emerald-400 text-shadow-glow-green"
                  : "text-red-400 text-shadow-glow-red",
              )}
            >
              R$ {data?.risk_status?.profit_day?.toFixed(2) ?? "0.00"}
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
            <ConfluenceGauge
              score={aiScore}
              direction={aiDirection}
              veto={aiVeto}
              obi={data?.obi ?? 0}
              sentiment={
                typeof data?.sentiment === "object"
                  ? data.sentiment.score
                  : (data?.sentiment ?? 0)
              }
              syntheticIndex={data?.risk_status?.synthetic_index ?? 0}
            />

            <div className="p-5 glass-heavy rounded-2xl shadow-2xl flex flex-col gap-5">
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
                        Score ≥ 85
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

                <div className="flex flex-col gap-2 p-3 bg-indigo-500/5 rounded-lg border border-indigo-500/20 mt-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Zap
                        className={cn(
                          "w-5 h-5",
                          isSniperRunning
                            ? "text-indigo-400"
                            : "text-muted-foreground",
                        )}
                      />
                      <div>
                        <Label
                          htmlFor="sniper-mode"
                          className="text-xs font-bold block"
                        >
                          PRECISION SNIPER
                        </Label>
                        <span className="text-[10px] text-muted-foreground leading-none">
                          Microstructure SOTA
                        </span>
                      </div>
                    </div>

                    <Switch
                      id="sniper-mode"
                      checked={isSniperRunning}
                      onCheckedChange={toggleSniper}
                      disabled={isUpdatingSniper}
                    />
                  </div>

                  {isSniperRunning && data?.risk_status?.sniper && (
                    <div className="grid grid-cols-2 gap-2 mt-1">
                      <div className="bg-black/40 p-1.5 rounded border border-white/5 text-center">
                        <p className="text-[12px] text-muted-foreground uppercase">
                          Vitórias
                        </p>
                        <p className="text-xs font-bold text-indigo-400">
                          {data.risk_status.sniper.consecutive_wins}
                        </p>
                      </div>
                      <div className="bg-black/40 p-1.5 rounded border border-white/5 text-center">
                        <p className="text-[12px] text-muted-foreground uppercase">
                          Trades
                        </p>
                        <p className="text-xs font-bold text-white">
                          {data.risk_status.sniper.trade_count}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
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
                      data?.risk_status.time_ok
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                        : "bg-red-500/10 text-red-400 border-red-500/20",
                    )}
                  >
                    {data?.risk_status.time_ok ? "OK" : "BLOQUEADO"}
                  </span>
                </li>
                <li className="flex justify-between items-center">
                  <span className="text-muted-foreground">Limite de Perda</span>
                  <span
                    className={cn(
                      "px-2 py-0.5 rounded text-[10px] font-bold border",
                      data?.risk_status?.loss_ok
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                        : "bg-red-500/10 text-red-400 border-red-500/20",
                    )}
                  >
                    {data?.risk_status?.loss_ok ? "OK" : "ATINGIDO"}
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

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-5 glass rounded-2xl shadow-xl flex flex-col gap-4 min-h-[380px] border border-white/10">
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-muted-foreground uppercase tracking-widest font-bold flex items-center gap-2">
                  <Bot size={16} className="text-primary animate-pulse" />
                  Sentimento do Mercado (Gemini IA)
                </span>
                <div className="flex items-center gap-3 bg-white/5 px-3 py-1 rounded-full border border-white/5">
                  <span className="text-2xl font-black bg-gradient-to-r from-emerald-400 to-white bg-clip-text text-transparent">
                    {sentimentValue.toFixed(2)}
                  </span>
                  <TrendingUp
                    className={cn(
                      "w-5 h-5",
                      sentimentValue > 0 ? "text-emerald-400" : "text-red-400",
                    )}
                  />
                </div>
              </div>

              <div className="flex-1 space-y-3 overflow-y-auto max-h-[420px] custom-scrollbar pr-2">
                {data?.sentiment &&
                typeof data.sentiment === "object" &&
                Array.isArray(data.sentiment.headlines) &&
                data.sentiment.headlines.length > 0 ? (
                  data.sentiment.headlines.map((item: any, idx: number) => {
                    const impactMap: Record<
                      string,
                      { label: string; color: string }
                    > = {
                      BULLISH: {
                        label: "ALTISTA",
                        color:
                          "text-emerald-400 bg-emerald-500/20 border-emerald-500/20",
                      },
                      BEARISH: {
                        label: "BAIXISTA",
                        color: "text-red-400 bg-red-500/20 border-red-500/20",
                      },
                      NEUTRAL: {
                        label: "NEUTRO",
                        color:
                          "text-zinc-400 bg-zinc-500/20 border-zinc-500/20",
                      },
                      ALTISTA: {
                        label: "ALTISTA",
                        color:
                          "text-emerald-400 bg-emerald-500/20 border-emerald-500/20",
                      },
                      BAIXISTA: {
                        label: "BAIXISTA",
                        color: "text-red-400 bg-red-500/20 border-red-500/20",
                      },
                      NEUTRO: {
                        label: "NEUTRO",
                        color:
                          "text-zinc-400 bg-zinc-500/20 border-zinc-500/20",
                      },
                    };
                    const impact = impactMap[item.impact] || impactMap.NEUTRAL;

                    return (
                      <div
                        key={idx}
                        className="flex flex-col gap-2 p-3 rounded-xl bg-white/[0.03] border border-white/[0.05] hover:border-primary/30 hover:bg-white/[0.06] transition-all duration-300 group"
                      >
                        <div className="flex justify-between items-start gap-4">
                          <p className="text-[16px]  leading-relaxed text-zinc-200 group-hover:text-white transition-colors">
                            {typeof item === "string" ? item : item.headline}
                          </p>
                          <span
                            className={cn(
                              "text-[12px] font-black px-2 py-0.5 rounded uppercase tracking-wider shrink-0 border",
                              impact.color,
                            )}
                          >
                            {impact.label}
                          </span>
                        </div>

                        {item.relevance !== undefined && (
                          <div className="flex items-center gap-3 mt-1">
                            <div className="flex items-center gap-1.5 min-w-[60px]">
                              <span className="text-[14px] text-muted-foreground font-medium">
                                Relevância:
                              </span>
                              <span className="text-[18px] font-mono font-bold text-primary">
                                {(item.relevance * 100).toFixed(0)}%
                              </span>
                            </div>
                            <div className="h-1 flex-1 bg-white/5 rounded-full overflow-hidden">
                              <div
                                className={cn(
                                  "h-full transition-all duration-1000 ease-out",
                                  item.impact === "BULLISH"
                                    ? "bg-emerald-500/60 shadow-[0_0_10px_rgba(16,185,129,0.3)]"
                                    : item.impact === "BEARISH"
                                      ? "bg-red-500/60 shadow-[0_0_10px_rgba(239,68,68,0.3)]"
                                      : "bg-primary/40",
                                )}
                                style={{
                                  width: `${(item.relevance * 100).toFixed(0)}%`,
                                }}
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })
                ) : (
                  <div className="flex flex-col items-center justify-center h-full py-4 gap-3 opacity-60">
                    <div className="relative">
                      <Activity
                        size={24}
                        className="animate-spin text-primary/40"
                      />
                      <Bot
                        size={12}
                        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-primary"
                      />
                    </div>
                    <p className="text-[10px] text-zinc-400 font-medium italic tracking-wide">
                      Processando panorama global em tempo real...
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Termômetro Blue Chips (New Quant Feature) */}
            {/* Termômetro Blue Chips (New Quant Feature) */}
            <div className="p-4 glass rounded-2xl shadow-lg flex flex-col gap-3 min-h-[180px]">
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-bold flex items-center gap-2">
                  <Activity
                    size={14}
                    className={cn(
                      "text-primary",
                      (data?.risk_status?.synthetic_index ?? 0) !== 0 &&
                        "animate-pulse",
                    )}
                  />
                  Blue Chips (IBOV)
                </span>

                <span
                  className={cn(
                    "text-[18px] font-black font-mono",
                    (data?.risk_status?.synthetic_index ?? 0) > 0
                      ? "text-emerald-400"
                      : (data?.risk_status?.synthetic_index ?? 0) < 0
                        ? "text-red-400"
                        : "text-muted-foreground",
                  )}
                >
                  {(data?.risk_status?.synthetic_index ?? 0).toFixed(2)}%
                </span>
              </div>

              <div className="flex-1 grid grid-cols-1 gap-2 overflow-y-auto max-h-[420px] custom-scrollbar pr-1">
                {data?.risk_status?.bluechips ? (
                  Object.entries(data.risk_status.bluechips).map(
                    ([ticker, change]: [string, any]) => (
                      <div
                        key={ticker}
                        className="flex items-center justify-between p-2 rounded-xl bg-white/[0.03] border border-white/[0.05] hover:bg-white/[0.06] transition-all group"
                      >
                        <span className="text-[14px] font-bold text-zinc-300 group-hover:text-primary transition-colors">
                          {ticker}
                        </span>
                        <div className="flex items-center gap-2">
                          <div className="w-12 h-1 bg-white/5 rounded-full overflow-hidden">
                            <div
                              className={cn(
                                "h-full transition-all duration-1000",
                                change > 0
                                  ? "bg-emerald-500/50"
                                  : change < 0
                                    ? "bg-red-500/50"
                                    : "bg-zinc-500/20",
                              )}
                              style={{
                                width: `${Math.min(100, Math.max(5, Math.abs(change * 20)))}%`,
                              }}
                            />
                          </div>
                          <span
                            className={cn(
                              "text-[18px] font-mono font-black min-w-[75px] text-right tabular-nums tracking-tighter",
                              change > 0
                                ? "text-emerald-400"
                                : change < 0
                                  ? "text-red-400"
                                  : "text-zinc-500",
                            )}
                          >
                            {change > 0 ? "+" : ""}
                            {Number(change || 0).toFixed(2)}%
                          </span>
                        </div>
                      </div>
                    ),
                  )
                ) : (
                  <div className="flex flex-col items-center justify-center h-full gap-2 opacity-40">
                    <Activity size={16} className="animate-spin" />
                    <span className="italic text-[9px]">
                      Sincronizando IBOV...
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Log de Execução Autônoma (Simulation Focus) */}
            <div className="md:col-span-2 p-4 glass rounded-2xl shadow-lg flex flex-col gap-3 min-h-[120px] relative">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-semibold flex items-center gap-2">
                  <ListTodo size={14} className="text-primary" />
                  Log de Execução Autônoma
                </span>
                <div className="flex items-center gap-2 self-end sm:self-auto">
                  <div className="flex bg-black/40 p-0.5 rounded-lg border border-white/5 ">
                    {["TODOS", "INFO", "SUCESSO", "ALERTA", "ERRO"].map((f) => (
                      <button
                        key={f}
                        onClick={() => setLogFilter(f as any)}
                        className={cn(
                          "px-2 py-0.5 text-[12px] font-bold rounded-md transition-all",
                          logFilter === f
                            ? "bg-white/10 text-white shadow-sm"
                            : "text-muted-foreground hover:text-zinc-300",
                        )}
                      >
                        {f}
                      </button>
                    ))}
                  </div>
                  <span
                    className={`text-[16px] animate-pulse border px-2 py-0.5 rounded hidden sm:inline-block ${
                      data?.dry_run
                        ? "text-emerald-400/70 border-emerald-500/20 bg-emerald-500/10"
                        : "text-amber-400/90 border-amber-500/30 bg-amber-500/10"
                    }`}
                  >
                    {data?.dry_run ? "SIMULAÇÃO" : "REAL"}
                  </span>
                </div>
              </div>

              {!isAutoScroll && filteredLogs.length > 0 && (
                <button
                  onClick={() => setIsAutoScroll(true)}
                  className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 bg-indigo-500/90 text-white px-3 py-1 rounded-full text-[10px] font-bold shadow-lg flex items-center gap-1 hover:bg-indigo-600 transition-colors border border-indigo-400/50 backdrop-blur-sm animate-in fade-in slide-in-from-bottom-2"
                >
                  <ArrowDown size={12} />
                  NOVOS EVENTOS
                </button>
              )}

              <div
                ref={logContainerRef}
                onScroll={handleLogScroll}
                className="flex-1 font-mono text-[10px] space-y-1 overflow-y-auto max-h-[400px] custom-scrollbar pr-2 pb-1 relative"
              >
                {filteredLogs.length > 0 ? (
                  filteredLogs.map((log: any, index: number) => (
                    <div
                      key={log.id}
                      className={cn(
                        "text-[16px] flex items-start gap-2 p-1.5 rounded transition-all animate-in slide-in-from-left-2 duration-300 border border-transparent group hover:bg-white/[0.04] hover:border-white/[0.05]",
                        index % 2 !== 0 ? "bg-white/[0.02]" : "",
                        LOG_COLORS[log.type as keyof typeof LOG_COLORS] ||
                          "text-muted-foreground",
                      )}
                    >
                      <span className="text-[16px] text-zinc-500 opacity-90 font-light shrink-0 tabular-nums">
                        [{log.time}]
                      </span>
                      {LOG_ICONS[log.type as keyof typeof LOG_ICONS] || (
                        <Info size={14} className="text-zinc-500 shrink-0" />
                      )}
                      <span className=" text-[14px] text-white/70 leading-relaxed tracking-wide flex-1">
                        {formatLogMessage(log.msg)}
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="flex gap-2 text-muted-foreground italic items-center justify-center p-4 opacity-50">
                    <Activity size={14} className="animate-spin" />
                    <span>
                      {logFilter !== "TODOS"
                        ? `Nenhum log do tipo ${logFilter} encontrado...`
                        : "Aguardando sinais de alta confiança (>85%)..."}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="md:col-span-1">
            {/* Filtros HFT (Toggles Manuais) */}
            <div className="grid grid-cols-3 gap-2 mt-2 border-t border-border/40 pt-4">
              {/* Toggle: Calendário Econômico */}
              <div
                className={cn(
                  "flex items-center justify-between p-3 rounded-lg border transition-all duration-300",
                  calendarFilterEnabled
                    ? "bg-emerald-500/10 border-emerald-500/30"
                    : "bg-white/5 border-white/10",
                )}
              >
                <div className="flex flex-col gap-1">
                  <Label
                    htmlFor="calendar-filter"
                    className={cn(
                      "text-\\[11px\\] font-bold uppercase tracking-wider cursor-pointer",
                      calendarFilterEnabled
                        ? "text-emerald-500"
                        : "text-muted-foreground",
                    )}
                  >
                    Filtro Calendário{" "}
                    <span className="opacity-60 text-xs">🕒</span>
                  </Label>
                  <span className="text-[14px] text-muted-foreground leading-tight">
                    {calendarFilterEnabled
                      ? "ATIVO (Evitando eventos)"
                      : "DESATIVADO"}
                  </span>
                </div>
                <Switch
                  id="calendar-filter"
                  checked={calendarFilterEnabled}
                  onCheckedChange={handleToggleCalendar}
                  disabled={isUpdatingFilters}
                  className={
                    calendarFilterEnabled
                      ? "data-[state=checked]:bg-emerald-500"
                      : ""
                  }
                />
              </div>

              {/* Toggle: Filtro de Notícias NLP */}
              <div
                className={cn(
                  "flex items-center justify-between p-3 rounded-lg border transition-all duration-300",
                  newsFilterEnabled
                    ? "bg-emerald-500/10 border-emerald-500/30"
                    : "bg-white/5 border-white/10",
                )}
              >
                <div className="flex flex-col gap-1">
                  <Label
                    htmlFor="news-filter"
                    className={cn(
                      "text-\\[11px\\] font-bold uppercase tracking-wider cursor-pointer",
                      newsFilterEnabled
                        ? "text-emerald-500"
                        : "text-muted-foreground",
                    )}
                  >
                    Notícias NLP <span className="opacity-60 text-xs">📰</span>
                  </Label>
                  <span className="text-[14px] text-muted-foreground leading-tight">
                    {newsFilterEnabled
                      ? "ATIVO (Filtrando sentimentos)"
                      : "DESATIVADO"}
                  </span>
                </div>
                <Switch
                  id="news-filter"
                  checked={newsFilterEnabled}
                  onCheckedChange={handleToggleNews}
                  disabled={isUpdatingFilters}
                  className={
                    newsFilterEnabled
                      ? "data-[state=checked]:bg-emerald-500"
                      : ""
                  }
                />
              </div>

              {/* Toggle: Filtro Macro S&P 500 */}
              <div
                className={cn(
                  "flex items-center justify-between p-3 rounded-lg border transition-all duration-300",
                  macroFilterEnabled
                    ? "bg-emerald-500/10 border-emerald-500/30"
                    : "bg-white/5 border-white/10",
                )}
              >
                <div className="flex flex-col gap-1">
                  <Label
                    htmlFor="macro-filter"
                    className={cn(
                      "text-\\[11px\\] font-bold uppercase tracking-wider cursor-pointer",
                      macroFilterEnabled
                        ? "text-emerald-500"
                        : "text-muted-foreground",
                    )}
                  >
                    Filtro S&P 500{" "}
                    <span className="opacity-60 text-xs">🌍</span>
                  </Label>
                  <span className="text-[14px] text-muted-foreground leading-tight">
                    {macroFilterEnabled
                      ? "ATIVO (Corta buys > 0.5%)"
                      : "DESATIVADO"}
                  </span>
                </div>
                <Switch
                  id="macro-filter"
                  checked={macroFilterEnabled}
                  onCheckedChange={handleToggleMacro}
                  disabled={isUpdatingFilters}
                  className={
                    macroFilterEnabled
                      ? "data-[state=checked]:bg-emerald-500"
                      : ""
                  }
                />
              </div>
            </div>
          </div>
          <FlowMeter />
          {/* Heatmap L2 (Novo - Phase 29) */}
          <OrderBookHeatmap />
        </div>
      </div>
    </div>
  );
}
