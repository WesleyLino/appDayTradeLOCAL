"use client";

import { useEffect, useCallback, useRef } from "react";
import { create } from "zustand";
import { API_CONFIG } from "@/lib/api-config";

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
  logs?: {
    id: string;
    time: string;
    msg: string;
    type: string;
  }[];
  ai_confidence?: number;
  // [FIX #TD-9] 'regime' raiz removido — o backend envia em risk_status.regime
  // regime nunca aparece na raiz do packet
  latency_ms: number;
  synthetic_index?: number;
  macro?: {
    score: number;
    reason: string;
  };
  ai_prediction?: {
    forecast: number;
    confidence?: number;
    score?: number;
    direction?: string;
    lot_multiplier?: number;
    veto?: string;
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
    allow_autonomous: boolean;
    profit_day: number;
    atr: number;
    performance?: {
      total_trades: number;
      win_rate: number;
      profit_factor: number;
      gross_profit: number;
      gross_loss: number;
      net_profit: number;
    };
    ai_score?: number;
    ai_direction?: string;
    uncertainty_range?: number;
    lower_bound?: number;
    upper_bound?: number;
    weighted_ofi?: number;
    synthetic_index?: number;
    bluechips?: Record<string, number>;
    psr?: number;
    regime?: number;
    order_status?: string;
    ticket?: number;
    limits?: {
      lower: number;
      upper: number;
      ref: number;
    };
    sniper?: {
      running: boolean;
      consecutive_wins: number;
      trade_count: number;
      last_trade_time: string | null;
    };
  };
  account: {
    balance: number;
    equity: number;
  };
  timestamp: number;
  dry_run?: boolean;
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

// [ANTIVIBE-CODING] - Resolução dinâmica de URL para evitar "Failed to fetch" no Windows
export function useTradingWebSocket(url: string = API_CONFIG.ws) {
  const setData = useTradingStore((state) => state.setData);
  const setConnected = useTradingStore((state) => state.setConnected);
  // [FIX #WS-1] connectRef garante referência estável para o onclose,
  // evitando o acesso de closure antes da declaração (ESLint: immutability)
  const connectRef = useRef<() => void>(() => {});
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
      // [FIX #WS-1] Usa connectRef para evitar closure com acesso antes da declaração
      setTimeout(() => connectRef.current(), 3000);
    };

    socket.onerror = (error) => {
      console.error("WS Error:", error);
      socket.close();
    };
  }, [url, setConnected, setData]);

  // Mantém connectRef sempre sincronizado com a versão atual de connect
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    connect();
    return () => {
      socketRef.current?.close();
    };
  }, [connect]);

  const sendOrder = async (side: string, volume: number = 1.0) => {
    try {
      // [ANTIVIBE-CODING] - Endpoint de envio de ordens
      const response = await fetch(`${API_CONFIG.http}/order`, {
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

  const  setAutonomous = async (enabled: boolean) => {
    try {
      const response = await fetch(
        `${API_CONFIG.http}/config/autonomous?enabled=${enabled}`,
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

  const startSniper = async () => {
    try {
      const response = await fetch(`${API_CONFIG.http}/config/sniper/start`, {
        method: "POST",
      });
      return await response.json();
    } catch (error) {
      console.error("Sniper Start Error:", error);
      return { status: "error", message: "Falha na rede" };
    }
  };

  const stopSniper = async () => {
    try {
      const response = await fetch(`${API_CONFIG.http}/config/sniper/stop`, {
        method: "POST",
      });
      return await response.json();
    } catch (error) {
      console.error("Sniper Stop Error:", error);
      return { status: "error", message: "Falha na rede" };
    }
  };

  const toggleNewsFilter = async (enabled: boolean) => {
    try {
      const response = await fetch(
        `${API_CONFIG.http}/config/filters/news?enabled=${enabled}`,
        { method: "POST" },
      );
      return await response.json();
    } catch (error) {
      console.error("News Filter Config Error:", error);
      return { status: "error", message: "Falha na rede" };
    }
  };

  const toggleCalendarFilter = async (enabled: boolean) => {
    try {
      const response = await fetch(
        `${API_CONFIG.http}/config/filters/calendar?enabled=${enabled}`,
        { method: "POST" },
      );
      return await response.json();
    } catch (error) {
      console.error("Calendar Filter Config Error:", error);
      return { status: "error", message: "Falha na rede" };
    }
  };

  const toggleMacroFilter = async (enabled: boolean) => {
    try {
      const response = await fetch(
        `${API_CONFIG.http}/config/filters/macro?enabled=${enabled}`,
        { method: "POST" },
      );
      return await response.json();
    } catch (error) {
      console.error("Macro Filter Config Error:", error);
      return { status: "error", message: "Falha na rede" };
    }
  };

  return {
    sendOrder,
    setAutonomous,
    startSniper,
    stopSniper,
    toggleNewsFilter,
    toggleCalendarFilter,
    toggleMacroFilter,
  };
}
