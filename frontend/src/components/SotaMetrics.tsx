"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { BrainCircuit, Activity, ShieldCheck, Gauge } from "lucide-react";

interface SotaMetricsProps {
  forecast?: number;
  confidence?: number;
  uncertaintyRange?: number;
  unweightedOfi?: number;
  weightedOfi?: number;
  regime?: number;
  psr?: number;
  syntheticIndex?: number;
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
}: SotaMetricsProps) {
  // Normalizar OFI para barra de progresso (-1000 a 1000 -> 0 a 100)
  const ofiProgress = Math.min(
    Math.max(((weightedOfi + 1000) / 2000) * 100, 0),
    100,
  );

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

  // PSR Display Logic: Se for exatamente 1.0, costuma ser o estado inicial antes de 30 amostras
  const isPsrCalibrating = psr === 1.0;

  return (
    <Card className="bg-black/20 backdrop-blur-xl border-white/5 shadow-2xl">
      <CardHeader className="pb-3 pt-4">
        <CardTitle className="text-sm font-medium tracking-widest text-muted-foreground flex items-center gap-2">
          <BrainCircuit className="w-4 h-4 text-emerald-400" />
          SOTA INTELLIGENCE
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4">
        {/* PSR Reliability */}
        <div className="flex items-center justify-between text-[10px] uppercase tracking-tighter text-blue-400 font-bold bg-blue-500/10 px-2 py-1 rounded">
          <div className="flex items-center gap-1">
            <ShieldCheck className="w-3 h-3" /> PSR Reliability
          </div>
          <span>
            {isPsrCalibrating ? "CALIBRATING..." : `${(psr * 100).toFixed(2)}%`}
          </span>
        </div>

        {/* Forecast & Confidence */}
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-white/80">PatchTST Confidence</span>
            <span className="font-mono text-emerald-300">
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
          <div className="flex justify-between text-xs">
            <span className="text-white/80 flex items-center gap-1">
              <ShieldCheck className="w-3 h-3" /> Incerteza (Range)
            </span>
            <span className="font-mono text-yellow-300">
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
          <div className="flex justify-between text-xs">
            <span className="text-white/80 flex items-center gap-1">
              <Gauge className="w-3 h-3" /> OFI Ponderado
            </span>
            <span
              className={`font-mono ${weightedOfi >= 0 ? "text-emerald-400" : "text-red-400"}`}
            >
              {weightedOfi.toFixed(1)}
            </span>
          </div>
          <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden relative">
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
        <div className="pt-2 border-t border-white/5 space-y-1">
          <div className="flex justify-between text-[10px] uppercase tracking-tighter text-muted-foreground">
            <span>Blue Chips Synth Index</span>
            <span
              className={
                syntheticIndex >= 0 ? "text-emerald-400" : "text-red-400"
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
                width: `${Math.min(Math.abs(syntheticIndex) * 50, 50)}%`,
              }}
            />
          </div>
        </div>

        {/* Regime */}
        <div className="pt-2 border-t border-white/5 flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Market Regime</span>
          <span
            className={`px-2 py-0.5 rounded font-bold ${regime === 2 ? "bg-red-500/20 text-red-400" : "bg-blue-500/20 text-blue-400"}`}
          >
            {getRegimeLabel(regime)}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
