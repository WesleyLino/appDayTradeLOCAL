"use client";

import React, { useMemo } from "react";
import { Zap, Activity, Info, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface ConfluenceGaugeProps {
  score: number;
  direction: string;
  obi: number;
  sentiment: number;
  syntheticIndex: number;
  className?: string;
}

export function ConfluenceGauge({
  score = 0,
  direction = "NEUTRAL",
  obi = 0,
  sentiment = 0,
  syntheticIndex = 0,
  className,
}: ConfluenceGaugeProps) {
  // Configuração do arco do velocímetro
  const radius = 80;
  const stroke = 12;
  const normalizedRadius = radius - stroke * 2;
  const circumference = normalizedRadius * 2 * Math.PI;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  // Cores dinâmicas baseadas na confluência
  const confluenceColor = useMemo(() => {
    if (score >= 85) return "text-emerald-400";
    if (score <= 15) return "text-red-400";
    if (score >= 50) return "text-blue-400";
    return "text-gray-400";
  }, [score]);

  const glowColor = useMemo(() => {
    if (score >= 85) return "rgba(52, 211, 153, 0.5)";
    if (score <= 15) return "rgba(248, 113, 113, 0.5)";
    return "rgba(59, 130, 246, 0.5)";
  }, [score]);

  return (
    <div
      className={cn(
        "flex flex-col gap-4 p-6 glass-heavy rounded-3xl relative overflow-hidden",
        className,
      )}
    >
      {/* Background Glow */}
      <div
        className="absolute -top-10 -right-10 w-32 h-32 blur-[80px] rounded-full transition-colors duration-1000"
        style={{ backgroundColor: glowColor }}
      />

      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-400 fill-amber-400" />
          Confluência SOTA
        </h3>
        <span
          className={cn(
            "px-2 py-0.5 rounded text-[10px] font-bold border border-white/5 bg-white/5",
            confluenceColor,
          )}
        >
          {score >= 85 || score <= 15 ? "PRECISÃO EXTREMA" : "SCORE NORMAL"}
        </span>
      </div>

      <div className="relative flex items-center justify-center py-4">
        {/* SVG Gauge */}
        <svg
          height={radius * 2}
          width={radius * 2}
          className="transform -rotate-90 transition-all duration-1000"
        >
          {/* Background circle */}
          <circle
            stroke="rgba(255,255,255,0.05)"
            fill="transparent"
            strokeWidth={stroke}
            r={normalizedRadius}
            cx={radius}
            cy={radius}
          />
          {/* Progress circle */}
          <circle
            stroke="currentColor"
            fill="transparent"
            strokeWidth={stroke}
            strokeDasharray={circumference + " " + circumference}
            style={{
              strokeDashoffset,
              transition: "stroke-dashoffset 0.8s ease-out",
            }}
            r={normalizedRadius}
            cx={radius}
            cy={radius}
            className={confluenceColor}
            strokeLinecap="round"
          />
        </svg>

        {/* Central Display */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className={cn(
              "text-4xl font-black tracking-tighter tabular-nums",
              confluenceColor,
            )}
          >
            {score.toFixed(0)}
          </span>
          <span className="text-[10px] font-medium text-muted-foreground uppercase">
            Score
          </span>
        </div>
      </div>

      {/* Sensor Fusion Breakdown */}
      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-white/5">
        <div className="flex flex-col gap-1">
          <span className="text-[8px] uppercase text-muted-foreground font-bold">
            Fluxo (OFI)
          </span>
          <div className="flex items-center gap-1">
            {obi >= 0.2 ? (
              <TrendingUp className="w-3 h-3 text-emerald-400" />
            ) : (
              <TrendingDown className="w-3 h-3 text-red-400" />
            )}
            <span className="text-xs font-mono font-bold">
              {(obi * 100).toFixed(0)}
            </span>
          </div>
        </div>
        <div className="flex flex-col gap-1 items-center">
          <span className="text-[8px] uppercase text-muted-foreground font-bold">
            IA (PatchTST)
          </span>
          <div className="flex items-center gap-1">
            <Activity className="w-3 h-3 text-blue-400" />
            <span className="text-xs font-mono font-bold">
              {direction === "BUY"
                ? "COMPRA"
                : direction === "SELL"
                  ? "VENDA"
                  : direction}
            </span>
          </div>
        </div>
        <div className="flex flex-col gap-1 items-end">
          <span className="text-[8px] uppercase text-muted-foreground font-bold">
            Sentimento
          </span>
          <div className="flex items-center gap-1">
            <span
              className={cn(
                "text-xs font-mono font-bold",
                sentiment >= 0 ? "text-emerald-400" : "text-red-400",
              )}
            >
              {sentiment >= 0 ? "+" : ""}
              {sentiment.toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* SOTA Requirement Info */}
      <div className="bg-white/5 border border-white/5 p-3 rounded-2xl flex items-start gap-3">
        <Info className="w-4 h-4 text-primary shrink-0 mt-0.5" />
        <p className="text-[10px] leading-relaxed text-muted-foreground">
          O modo autônomo requer{" "}
          <span className="text-white font-bold ">SCORE &gt; 85</span> e
          confluência positiva entre fluxo de ordens e predição de IA.
        </p>
      </div>
    </div>
  );
}
