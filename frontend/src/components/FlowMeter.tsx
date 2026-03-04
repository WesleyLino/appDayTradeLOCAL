"use client";

import { useTradingStore } from "@/hooks/use-trading-ws";
import { cn } from "@/lib/utils";

export function FlowMeter() {
  const { data } = useTradingStore();
  const obi = data?.obi ?? 0.5;

  // Converter OBI (-1 a 1) para percentual (0 a 100)
  const percentage = ((obi + 1) / 2) * 100;

  return (
    <div className="flex flex-col items-center p-4 bg-zinc-900/60 backdrop-blur-xl rounded-2xl border border-white/10 shadow-lg min-h-[120px] justify-center">
      <span className="text-[14px] text-muted-foreground uppercase tracking-widest font-bold mb-4">
        Fluxo OBI (Microestrutura)
      </span>
      <div className="relative w-full h-4 bg-black/40 rounded-full overflow-hidden border border-white/5">
        <div
          className={cn(
            "absolute top-0 left-0 h-full transition-all duration-500 ease-out",
            obi > 0.6 ? "bg-profit" : obi < -0.6 ? "bg-loss" : "bg-neutral",
          )}
          style={{ width: `${percentage}%` }}
        />
        <div className="absolute top-0 left-1/2 w-0.5 h-full bg-foreground/20" />
      </div>
      <div className="flex justify-between w-full mt-2 text-2xl font-mono">
        <span className="text-loss">Venda</span>
        <span className="font-bold">{obi.toFixed(2)}</span>
        <span className="text-profit">Compra</span>
      </div>
    </div>
  );
}
