"use client";

import { useEffect, useState } from "react";
import {
  TrendingUp,
  Target,
  Activity,
  DollarSign,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface PerformanceData {
  total_trades: number;
  win_rate: number;
  profit_factor: number;
  gross_profit: number;
  gross_loss: number;
  net_profit: number;
}

export function PerformanceWidget() {
  const [data, setData] = useState<PerformanceData>({
    total_trades: 0,
    win_rate: 0.0,
    profit_factor: 0.0,
    gross_profit: 0.0,
    gross_loss: 0.0,
    net_profit: 0.0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPerformance = async () => {
    try {
      setLoading(true);
      setError(null);
      // Backend roda na 8000
      const response = await fetch("http://localhost:8000/performance");
      const result = await response.json();

      if (result.status === "success" && result.data) {
        setData(result.data);
      } else {
        setError(result.message || "Erro ao carregar dados");
      }
    } catch (err) {
      console.error("Falha ao buscar performance", err);
      setError("Falha na conexão com backend");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPerformance();
    // Atualiza a cada 30 segundos
    const interval = setInterval(fetchPerformance, 30000);
    return () => clearInterval(interval);
  }, []);

  const isProfit = data.net_profit >= 0;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 flex flex-col gap-4 text-zinc-100 shadow-xl overflow-hidden relative">
      {/* Canto de Atualização */}
      <button
        onClick={fetchPerformance}
        disabled={loading}
        className="absolute top-4 right-4 text-zinc-500 hover:text-zinc-300 transition-colors"
        title="Refresh Data"
      >
        <RefreshCw size={16} className={cn(loading && "animate-spin")} />
      </button>

      <div className="flex items-center gap-2 mb-1">
        <Activity size={18} className="text-zinc-400" />
        <h3 className="font-bold text-sm tracking-wider text-zinc-400">
          PERFORMANCE DO DIA
        </h3>
      </div>

      {error ? (
        <div className="text-sm text-red-500 bg-red-500/10 p-2 rounded border border-red-500/20">
          {error}
        </div>
      ) : (
        <>
          {/* Main Profit Display */}
          <div className="flex flex-col">
            <span className="text-xs text-zinc-500 uppercase font-semibold">
              Net Profit (MT5 History)
            </span>
            <div
              className={cn(
                "text-3xl font-black tabular-nums tracking-tight flex items-baseline gap-1",
                isProfit ? "text-emerald-400" : "text-rose-500",
              )}
            >
              <span className="text-lg opacity-70">R$</span>
              {data.net_profit.toLocaleString("pt-BR", {
                minimumFractionDigits: 2,
              })}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 mt-2">
            {/* Win Rate */}
            <div className="bg-zinc-950/50 rounded p-3 border border-zinc-800/50">
              <div className="flex items-center gap-1.5 text-zinc-400 mb-1">
                <Target size={14} />
                <span className="text-xs font-semibold uppercase">
                  Win Rate
                </span>
              </div>
              <div className="text-lg font-bold tabular-nums">
                {data.win_rate.toFixed(1)}%
              </div>
              {/* Progress Bar Miniature */}
              <div className="w-full h-1.5 bg-zinc-800 rounded-full mt-2 overflow-hidden flex">
                <div
                  className="h-full bg-emerald-500"
                  style={{ width: `${data.win_rate}%` }}
                />
                <div
                  className="h-full bg-rose-500"
                  style={{ width: `${100 - data.win_rate}%` }}
                />
              </div>
            </div>

            {/* Profit Factor */}
            <div className="bg-zinc-950/50 rounded p-3 border border-zinc-800/50">
              <div className="flex items-center gap-1.5 text-zinc-400 mb-1">
                <TrendingUp size={14} />
                <span className="text-xs font-semibold uppercase">
                  Profit Factor
                </span>
              </div>
              <div className="text-lg font-bold tabular-nums">
                {data.profit_factor > 0
                  ? data.profit_factor.toFixed(2)
                  : "0.00"}
              </div>
              <div className="text-[10px] text-zinc-500 mt-1 uppercase">
                {data.total_trades} Operações
              </div>
            </div>
          </div>

          {/* Gross Info (Subtle) */}
          <div className="flex justify-between text-xs pt-2 border-t border-zinc-800/50 mt-1">
            <div className="flex flex-col">
              <span className="text-zinc-500">Gross Profit</span>
              <span className="text-emerald-500 font-medium tabular-nums">
                R$ {data.gross_profit.toFixed(2)}
              </span>
            </div>
            <div className="flex flex-col text-right">
              <span className="text-zinc-500">Gross Loss</span>
              <span className="text-rose-500 font-medium tabular-nums">
                R$ {data.gross_loss.toFixed(2)}
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
