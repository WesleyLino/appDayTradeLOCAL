"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { BrainCircuit, Gauge, Scale, ShieldCheck, Globe } from "lucide-react";
import { cn } from "@/lib/utils";

interface SotaMetricsProps {
  forecast?: number;
  confidence?: number;
  uncertaintyRange?: number;
  unweightedOfi?: number;
  weightedOfi?: number;
  regime?: number;
  psr?: number;
  syntheticIndex?: number;
  macroIndex?: number;
  lotMultiplier?: number;
}

export function SotaMetrics({
  forecast = 0,
  confidence = 0,
  uncertaintyRange = 0,
  unweightedOfi = 0,
  weightedOfi = 0,
  regime = 0,
  psr = 0,
  syntheticIndex = 0,
  macroIndex = 0,
  lotMultiplier = 1.0,
}: SotaMetricsProps) {
  const getRegimeLabel = (r: number) => {
    switch (r) {
      case 0:
        return "BAIXA VOL (0)";
      case 1:
        return "TENDÊNCIA (1)";
      case 2:
        return "RUÍDO (2)";
      default:
        return "INDEFINIDO";
    }
  };

  const isPsrCalibrating = psr === 1.0;

  return (
    <Card className="bg-black/20 backdrop-blur-xl border-white/5 shadow-2xl">
      <CardHeader className="pb-3 pt-4">
        <CardTitle className="text-sm font-medium tracking-widest text-muted-foreground flex items-center gap-2">
          <BrainCircuit className="w-4 h-4 text-emerald-400" />
          INTELIGÊNCIA SOTA
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4">
        {/* PSR Reliability & Quarter-Kelly */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between text-[14px] uppercase tracking-tighter text-blue-400 font-bold bg-blue-500/10 px-2.5 py-1.5 rounded-lg border border-blue-500/10">
            <div className="flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5" /> Confiabilidade PSR
            </div>
            <span>
              {isPsrCalibrating
                ? "CALIBRANDO..."
                : `${(psr * 100).toFixed(2)}%`}
            </span>
          </div>

          <div className="flex items-center justify-between text-[14px] uppercase tracking-tight text-indigo-300 font-medium bg-indigo-500/5 px-2.5 py-1 rounded border border-indigo-500/10">
            <span>Quarter-Kelly Scaling</span>
            <span className="font-mono text-[18px] font-bold">ATIVO</span>
          </div>
        </div>

        {/* Current Exposure (Incerteza Elástica) */}
        {/* [FIX #TD-6] Classe CSS corrompida corrigida — era text-white/1px] (inválida) */}
        <div className="flex items-center justify-between text-[14px] uppercase tracking-tighter text-emerald-400 font-bold bg-emerald-500/10 px-2.5 py-1.5 rounded-lg border border-emerald-500/10">
          <div className="flex items-center gap-1.5">
            <Scale className="w-3.5 h-3.5" /> Incerteza Elástica
          </div>
          <span className="font-mono text-[18px]">
            {lotMultiplier.toFixed(2)}x
          </span>
        </div>

        {/* Forecast & Confidence */}
        <div className="space-y-1">
          <div className="flex justify-between text-[14px] uppercase tracking-tighter text-white">
            <span className="text-white/80">Confiança PatchTST</span>
            <span className="font-mono text-emerald-300 text-[18px] font-bold">
              {(confidence * 100).toFixed(1)}%
            </span>
          </div>
          <Progress
            value={confidence * 100}
            className="h-1 bg-white/5"
            indicatorClassName="bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]"
          />
        </div>

        {/* Uncertainty (Conformal) */}
        <div className="space-y-1">
          <div className="flex justify-between text-[14px] uppercase tracking-tighter text-white">
            <span className="text-white/80 flex items-center gap-1">
              <ShieldCheck className="w-3 h-3" /> Incerteza (Range)
            </span>
            <span className="font-mono text-yellow-300 text-[18px] font-bold">
              {uncertaintyRange.toFixed(1)} pts
            </span>
          </div>
          <Progress
            value={
              Math.abs(uncertaintyRange) > 0
                ? Math.min((uncertaintyRange / (forecast || 1)) * 5000, 100)
                : 0
            }
            className="h-1 bg-white/5"
            indicatorClassName="bg-amber-400 shadow-[0_0_10px_rgba(251,191,36,0.5)]"
          />
        </div>

        {/* OFI Weighted */}
        <div className="space-y-1">
          <div className="flex justify-between text-[14px] uppercase tracking-tighter text-white">
            <span className="text-white/80 flex items-center gap-1 text-[14px]">
              <Gauge className="w-3 h-3" /> OFI Ponderado
            </span>
            <span
              className={`font-mono text-[18px] font-bold ${weightedOfi >= 0 ? "text-emerald-400 text-[18px] font-bold" : "text-red-400 text-[18px] font-bold"}`}
            >
              {weightedOfi.toFixed(1)}
            </span>
          </div>
          <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden relative text-[14px]">
            <div
              className={`absolute top-0 bottom-0 transition-all duration-500 ${weightedOfi >= 0 ? "bg-emerald-500 left-1/2" : "bg-red-500 right-1/2"}`}
              style={{
                width: `${Math.abs(Math.min(Math.max((weightedOfi / 1000) * 50, -50), 50))}%`,
              }}
            />
            <div className="absolute top-0 bottom-0 left-1/2 w-px bg-white/20" />
          </div>
        </div>

        {/* Synthetic Index (Blue Chips) */}
        <div className="pt-2 border-t border-white/5 space-y-1 text-[14px] font-bold">
          <div className="flex justify-between uppercase tracking-tighter text-muted-foreground">
            <span>Índice Sintético Blue Chips</span>
            <span
              className={
                syntheticIndex >= 0
                  ? "text-emerald-400 text-[18px] font-bold"
                  : "text-red-400 text-[18px] font-bold"
              }
            >
              {syntheticIndex >= 0 ? "+" : ""}
              {syntheticIndex.toFixed(2)}%
            </span>
          </div>
          <div className="h-1 w-full bg-white/5 rounded-full relative overflow-hidden">
            <div
              className={`absolute top-0 bottom-0 transition-all duration-700 ${syntheticIndex >= 0 ? "bg-emerald-500/50 left-1/2" : "bg-red-500/50 right-1/2"}`}
              style={{
                width: `${Math.min(Math.abs(syntheticIndex) * 100, 50)}%`,
              }}
            />
          </div>
        </div>

        {/* Macro Sentiment (S&P 500) */}
        <div className="pt-2 border-t border-white/5 space-y-1 text-xs">
          <div className="flex justify-between uppercase tracking-tighter text-muted-foreground">
            {/* [FIX #TD-7] Typo 'font-bol' corrigido para 'font-bold' */}
            <span className="flex items-center gap-1 text-[14px] font-bold">
              <Globe className="w-3 h-3 text-blue-400 text-[18px] font-bold" />{" "}
              Macro S&P 500
            </span>
            <span
              className={
                macroIndex >= 0
                  ? "text-blue-400 text-[18px] font-bold"
                  : "text-amber-400 text-[18px] font-bold"
              }
            >
              {macroIndex >= 0 ? "+" : ""}
              {macroIndex.toFixed(2)}%
            </span>
          </div>
          <div className="h-1 w-full bg-white/5 rounded-full relative overflow-hidden">
            <div
              className={`absolute top-0 bottom-0 transition-all duration-700 ${macroIndex >= 0 ? "bg-blue-500/50 left-1/2" : "bg-amber-500/50 right-1/2"}`}
              style={{
                width: `${Math.min(Math.abs(macroIndex) * 100, 50)}%`,
              }}
            />
          </div>
        </div>

        {/* Regime */}
        <div className="pt-2 border-t border-white/5 flex items-center justify-between text-[14px]">
          <span className="text-muted-foreground uppercase tracking-tighter">
            Regime de Mercado
          </span>
          <span
            key={regime} // Força re-render para disparar animações CSS se houver
            className={cn(
              "px-3 py-1 rounded-lg font-black transition-all duration-700 animate-in fade-in zoom-in slide-in-from-right-1",
              regime === 2
                ? "bg-red-500/20 text-red-400 border border-red-500/40 shadow-[0_0_20px_rgba(239,68,68,0.3)] animate-pulse"
                : regime === 1
                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-[0_0_20px_rgba(16,185,129,0.3)]"
                  : "bg-blue-500/20 text-blue-400 border border-blue-500/40 shadow-[0_0_20px_rgba(59,130,246,0.3)]",
            )}
          >
            {getRegimeLabel(regime)}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
