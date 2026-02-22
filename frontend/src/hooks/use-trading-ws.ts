"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { create } from "zustand";

interface TradeData {
  symbol: string;
  price: number;
  obi: number;
  sentiment:
    | {
        score: number;
        headlines: string[];
      }
    | number; // Backward compatibility with previous simple number
  ai_confidence?: number;
  regime?: number;
  latency_ms: number;
  synthetic_index?: number;
  ai_prediction?: {
    forecast: number;
    confidence?: number;
    score?: number;
    direction?: string;
  };
  sota?: {
    forecast: number;
    confidence: number;
    uncertainty_range: number;
    lower_bound: number;
    upper_bound: number;
    weighted_ofi: number;
    synthetic_index: number;
    psr: number;
    regime: number;
  };
  book?: {
    bids: { price: number; volume: number }[];
    asks: { price: number; volume: number }[];
  };
  calendar?: {
    volatility_expected: boolean;
    reason: string;
  };
  daily_realized?: number;
  risk_status: {
    time_ok: boolean;
    loss_ok: boolean;
    profit_day: number;
    atr: number;
    ai_score?: number;
    ai_direction?: string;
    uncertainty_range?: number;
    lower_bound?: number;
    upper_bound?: number;
    weighted_ofi?: number;
    synthetic_index?: number;
    psr?: number;
    regime?: number;
    order_status?: string;
    ticket?: number;
    limits?: {
      lower: number;
      upper: number;
      ref: number;
    };
  };
  account: {
    balance: number;
    equity: number;
  };
  timestamp: number;
}

interface TradingStore {
  data: TradeData | null;
  connected: boolean;
  setData: (data: TradeData) => void;
  setConnected: (connected: boolean) => void;
}

export const useTradingStore = create<TradingStore>((set) => ({
  data: null,
  connected: false,
  setData: (data) => set({ data }),
  setConnected: (connected) => set({ connected }),
}));

export function useTradingWebSocket(url: string = "ws://localhost:8000/ws") {
  const { setData, setConnected } = useTradingStore();
  const socketRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) return;

    const socket = new WebSocket(url);
    socketRef.current = socket;

    socket.onopen = () => {
      setConnected(true);
      console.log("WS Connected");
    };

    socket.onmessage = (event) => {
      const packet = JSON.parse(event.data);
      setData(packet);
    };

    socket.onclose = () => {
      setConnected(false);
      console.log("WS Disconnected");
      // Reconectar após 3 segundos
      setTimeout(connect, 3000);
    };

    socket.onerror = (error) => {
      console.error("WS Error:", error);
      socket.close();
    };
  }, [url, setConnected, setData]);

  useEffect(() => {
    connect();
    return () => {
      socketRef.current?.close();
    };
  }, [connect]);

  const sendOrder = async (side: string, volume: number = 1.0) => {
    try {
      const response = await fetch("http://localhost:8000/order", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ side, volume }),
      });
      return await response.json();
    } catch (error) {
      console.error("Order Error:", error);
      return { status: "error", message: "Falha na rede" };
    }
  };

  const setAutonomous = async (enabled: boolean) => {
    try {
      const response = await fetch(
        `http://localhost:8000/config/autonomous?enabled=${enabled}`,
        {
          method: "POST",
        },
      );
      return await response.json();
    } catch (error) {
      console.error("Autonomous Config Error:", error);
      return { status: "error", message: "Falha na rede" };
    }
  };

  return { sendOrder, setAutonomous };
}
