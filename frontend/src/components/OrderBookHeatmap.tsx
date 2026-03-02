"use client";

import React, { useEffect, useState } from "react";
import { useTradingStore } from "@/hooks/use-trading-ws";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface OrderLevel {
  price: number;
  volume: number;
}

interface OrderBook {
  bids: OrderLevel[];
  asks: OrderLevel[];
}

export function OrderBookHeatmap() {
  const { data, connected } = useTradingStore();
  const [simulatedBook, setSimulatedBook] = useState<OrderBook>({
    bids: [],
    asks: [],
  });
  const [isSimulated, setIsSimulated] = useState(true);

  // Fallback Simulation Logic (Só roda se não houver MT5)
  useEffect(() => {
    if (
      connected &&
      data?.book &&
      (data.book.bids.length > 0 || data.book.asks.length > 0)
    ) {
      setIsSimulated(false);
      return;
    }

    setIsSimulated(true);
    const interval = setInterval(() => {
      const basePrice = data?.price || 115000;
      const newBids = Array.from({ length: 10 }).map((_, i) => ({
        price: basePrice - i * 5,
        volume: Math.floor(Math.random() * 100) + 10,
      }));
      const newAsks = Array.from({ length: 10 }).map((_, i) => ({
        price: basePrice + (i + 1) * 5,
        volume: Math.floor(Math.random() * 100) + 10,
      }));
      setSimulatedBook({ bids: newBids, asks: newAsks });
    }, 1000);

    return () => clearInterval(interval);
  }, [connected, data?.book, data?.price]);

  // Derived Data (Heatmap)
  const { book, maxVol } = React.useMemo(() => {
    const currentBook =
      !isSimulated && data?.book
        ? {
            bids: data.book.bids.slice(0, 10),
            asks: data.book.asks.slice(0, 10),
          }
        : simulatedBook;

    const maxV = Math.max(
      ...currentBook.bids.map((b) => b.volume),
      ...currentBook.asks.map((a) => a.volume),
      10,
    );

    return { book: currentBook, maxVol: maxV };
  }, [isSimulated, data?.book, simulatedBook]);

  const getIntensity = (vol: number) => {
    const opacity = 0.2 + (vol / maxVol) * 0.8;
    return opacity;
  };

  return (
    <Card className="border-white/5 bg-black/20 backdrop-blur-xl shadow-2xl">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-zinc-400 flex justify-between items-center">
          Mapa de Calor do Order Book (L2)
          {isSimulated ? (
            <Badge variant="outline" className="text-xs bg-zinc-950/50">
              Simulado (MT5 Off)
            </Badge>
          ) : (
            <Badge
              variant="default"
              className="text-xs bg-emerald-500/20 text-emerald-400 border-emerald-500/50"
            >
              Dados em Tempo Real
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex gap-4">
          {/* Lado da Compra (Bids) - Verde */}
          <div className="flex-1 flex flex-col gap-0.5">
            <div className="text-xs text-center text-emerald-500 mb-1 font-bold">
              COMPRA
            </div>
            {book.bids.map((level, i) => (
              <div
                key={`bid-${i}`}
                className="flex justify-between text-xs px-2 py-1 rounded relative overflow-hidden"
              >
                {/* Barra de Fundo (Heatmap) */}
                <div
                  className="absolute inset-0 bg-emerald-500/30 z-0 transition-all duration-300"
                  style={{
                    width: `${(level.volume / maxVol) * 100}%`,
                    opacity: getIntensity(level.volume),
                  }}
                />

                <span className="z-10 font-mono text-zinc-300">
                  {level.volume}
                </span>
                <span className="z-10 font-mono text-emerald-400 font-bold">
                  {level.price}
                </span>
              </div>
            ))}
          </div>

          {/* Lado da Venda (Asks) - Vermelho */}
          <div className="flex-1 flex flex-col gap-0.5">
            <div className="text-xs text-center text-rose-500 mb-1 font-bold">
              VENDA
            </div>
            {book.asks.map((level, i) => (
              <div
                key={`ask-${i}`}
                className="flex justify-between text-xs px-2 py-1 rounded relative overflow-hidden"
              >
                {/* Barra de Fundo (Heatmap) */}
                <div
                  className="absolute inset-0 bg-rose-500/30 z-0 transition-all duration-300 left-0"
                  style={{
                    width: `${(level.volume / maxVol) * 100}%`,
                    opacity: getIntensity(level.volume),
                  }}
                />

                <span className="z-10 font-mono text-rose-400 font-bold">
                  {level.price}
                </span>
                <span className="z-10 font-mono text-zinc-300 text-right w-full">
                  {level.volume}
                </span>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
