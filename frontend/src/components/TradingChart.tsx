"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  IChartApi,
  ISeriesApi,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  LineStyle,
  UTCTimestamp,
} from "lightweight-charts";
import { useTradingStore } from "@/hooks/use-trading-ws";

export function TradingChart() {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const forecastSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const upperSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const lowerSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  // [FIX #CHART-2] Ref para rastrear o último timestamp enviado ao chart.
  // lightweight-charts exige timestamps ESTRITAMENTE CRESCENTES.
  // Sem isso, dois ticks no mesmo segundo (ex: 10:53:57.1 e 10:53:57.9)
  // geram "Cannot update oldest data" após o Math.floor os igualar (1742xxx).
  const lastTimestampRef = useRef<number>(0);
  const { data } = useTradingStore();

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#f3f8f8ff",
        // textColor: "#a1a1aa",
        fontSize: 18,
      },
      grid: {
        vertLines: { color: "#27272a" },
        horzLines: { color: "#27272a" },
      },
      width: chartContainerRef.current.clientWidth,
      height: 400,
      timeScale: {
        timeVisible: true,
        secondsVisible: true,
      },
    });

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      // upColor: "#10b981",
      upColor: "#08c908ff",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: "#3b82f6",
      priceFormat: {
        type: "volume",
      },
      priceScaleId: "", // Overlay
    });

    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });

    // [SOTA] Uncertainty Cone Series
    const forecastSeries = chart.addSeries(LineSeries, {
      color: "#06b6d4", // Cyan (AI)
      lineWidth: 1,
      lineStyle: LineStyle.Solid,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    const upperSeries = chart.addSeries(LineSeries, {
      color: "#fbbf24", // Amber (Uncertainty)
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    const lowerSeries = chart.addSeries(LineSeries, {
      color: "#fbbf24", // Amber
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    chartRef.current = chart;
    candlestickSeriesRef.current = candlestickSeries;
    volumeSeriesRef.current = volumeSeries;
    forecastSeriesRef.current = forecastSeries;
    upperSeriesRef.current = upperSeries;
    lowerSeriesRef.current = lowerSeries;

    const handleResize = () => {
      chart.applyOptions({ width: chartContainerRef.current?.clientWidth });
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, []);

  // [SOTA] Data Update Effect
  useEffect(() => {
    if (!data || !candlestickSeriesRef.current) return;

    // [FIX #CHART-1 + #CHART-2] Tratamento completo de timestamp para lightweight-charts v5.
    // Problema: Backend envia timestamps float Python (ex: 1742389825.421).
    // Dois ticks chegando no mesmo segundo se tornam o mesmo inteiro após Math.floor,
    // causando "Cannot update oldest data" (chart exige timestamps ESTRITAMENTE CRESCENTES).
    // Solução: Rastrear último timestamp e avançar +1 se necessário.
    const rawTime = Math.floor(data.timestamp);
    let safeTime: number;
    if (rawTime > lastTimestampRef.current) {
      safeTime = rawTime;
    } else {
      // Mesmo segundo ou ordem invertida → avança +1 para manter ordem crescente
      safeTime = lastTimestampRef.current + 1;
    }
    lastTimestampRef.current = safeTime;
    const time = safeTime as UTCTimestamp;

    candlestickSeriesRef.current.update({
      time: time,
      open: data.price, // Simplificação se receber tick único. Ideal é receber OHLC.
      high: data.price,
      low: data.price,
      close: data.price,
    });

    // 2. Update SOTA Series (Uncertainty Cone)
    if (data.sota && forecastSeriesRef.current) {
      const { forecast, lower_bound, upper_bound } = data.sota;

      forecastSeriesRef.current.update({ time: time, value: forecast });

      // Limites do Cone Reais (SOTA Conformal Bound)
      upperSeriesRef.current?.update({
        time: time,
        value: upper_bound,
      });
      lowerSeriesRef.current?.update({
        time: time,
        value: lower_bound,
      });
    }
  }, [data]);

  return (
    <div className="w-full bg-black/20 backdrop-blur-xl p-4 rounded-xl border border-white/5 shadow-2xl">
      <div ref={chartContainerRef} className="w-full" />
    </div>
  );
}
