/**
 * Single chart panel unit.
 * Owns its own resolution, dailyRange, and candles data.
 */

import { createEffect, createSignal, onCleanup, onMount, Show, untrack } from "solid-js";
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickSeries,
  AreaSeries,
  BaselineSeries,
  HistogramSeries,
  LineSeries,
  PriceLineOptions,
} from "lightweight-charts";
import { SMA, EMA } from "lightweight-charts-indicators";
import type { Bar } from "oakscriptjs";
import { stocksAPI, type CandleResponse } from "../../lib/stocks-api";
import {
  type DailyRange,
  type Resolution,
  getDateRange,
} from "../../lib/chart-utils";
import { pollingManager } from "~/lib/polling-manager";
import { isMarketOpen } from "~/lib/market-hours";

interface QuoteData {
  last: number;
  change: number;
  change_pct: number;
}

interface IndicatorConfig {
  type: "sma" | "ema";
  period: number;
  enabled: boolean;
}

interface Props {
  symbol: string;
  quote: QuoteData | null;
  selectedSymbol: () => string | null;
  defaultResolution?: Resolution;
}

export function ChartPanel(props: Props) {
  const [resolution, setResolution] = createSignal<Resolution>(props.defaultResolution ?? "D");
  const [dailyRange, setDailyRange] = createSignal<DailyRange>("3M");
  const [chartType, setChartType] = createSignal<"candle" | "area" | "baseline">("candle");
  const [candles, setCandles] = createSignal<CandleResponse[]>([]);
  const [currentDayCandle, setCurrentDayCandle] = createSignal<CandleResponse | null>(null);
  const [isLoading, setIsLoading] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);
  const [indicators, setIndicators] = createSignal<IndicatorConfig[]>([
    { type: "sma", period: 20, enabled: false },
    { type: "ema", period: 20, enabled: false },
  ]);
  const [priceLines, setPriceLines] = createSignal<number[]>([]);

  let chartContainer: HTMLDivElement | undefined;
  let chart: IChartApi | undefined;
  let priceSeries: ISeriesApi<"Candlestick" | "Area" | "Baseline"> | undefined;
  let volumeSeries: ISeriesApi<"Histogram"> | undefined;
  let indicatorSeries: ISeriesApi<"Line">[] = [];
  let priceLineRefs: ReturnType<ISeriesApi<"Candlestick">["createPriceLine"]>[] = [];

  // Build (or rebuild) the price series for the current chartType
  const buildPriceSeries = () => {
    if (!chart) return;
    if (priceSeries) chart.removeSeries(priceSeries);

    if (chartType() === "baseline") {
      // Calculate baseline from data (average of visible candles)
      const data = candles();
      const basePrice = data.length > 0
        ? data.reduce((sum, c) => sum + c.close, 0) / data.length
        : 100;

      priceSeries = chart.addSeries(BaselineSeries, {
        baseValue: { type: "price", price: basePrice },
        topLineColor: "#4ade80",
        topFillColor1: "rgba(74, 222, 128, 0.28)",
        topFillColor2: "rgba(74, 222, 128, 0.05)",
        bottomLineColor: "#ef4444",
        bottomFillColor1: "rgba(239, 68, 68, 0.05)",
        bottomFillColor2: "rgba(239, 68, 68, 0.28)",
      });
    } else if (chartType() === "candle") {
      priceSeries = chart.addSeries(CandlestickSeries, {
        upColor: "#4ade80",
        downColor: "#ef4444",
        borderDownColor: "#ef4444",
        borderUpColor: "#4ade80",
        wickDownColor: "#ef4444",
        wickUpColor: "#4ade80",
      });
    } else {
      priceSeries = chart.addSeries(AreaSeries, {
        lineColor: "#4ade80",
        topColor: "rgba(74, 222, 128, 0.25)",
        bottomColor: "rgba(74, 222, 128, 0.0)",
      });
    }
  };

  // Convert candles to Bar format for indicators
  const toBars = (data: CandleResponse[]): Bar[] => {
    return data.map((c) => ({
      time: new Date(c.time).getTime() / 1000,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
      volume: c.volume,
    }));
  };

  // Clear and rebuild indicator series
  const updateIndicators = (data: CandleResponse[]) => {
    if (!chart || !priceSeries) return;

    // Remove existing indicator series
    indicatorSeries.forEach((s) => chart?.removeSeries(s));
    indicatorSeries = [];

    const enabledIndicators = indicators().filter((i) => i.enabled);
    if (enabledIndicators.length === 0 || data.length < 2) return;

    const bars = toBars(data);
    const colors = ["#f59e0b", "#8b5cf6", "#06b6d4", "#ec4899"];

    enabledIndicators.forEach((ind, idx) => {
      const color = colors[idx % colors.length];
      let result;

      if (ind.type === "sma") {
        result = SMA.calculate(bars, { len: ind.period, src: "close" });
      } else {
        result = EMA.calculate(bars, { len: ind.period, src: "close" });
      }

      if (result.plots.plot0 && result.plots.plot0.length > 0) {
        const lineSeries = chart!.addSeries(LineSeries, {
          color,
          lineWidth: 2,
          title: `${ind.type.toUpperCase()}${ind.period}`,
        });
        indicatorSeries.push(lineSeries);

        const plotData = result.plots.plot0
          .filter((p: any) => p !== null && !isNaN(p.value))
          .map((p: any) => ({
            time: p.time as number,
            value: p.value as number,
          }));
        lineSeries.setData(plotData);
      }
    });
  };

  // Update price lines
  const updatePriceLines = (currentPrice: number) => {
    if (!priceSeries) return;

    // Remove existing price lines
    priceLineRefs.forEach((line) => priceSeries?.removePriceLine(line));
    priceLineRefs = [];

    priceLines().forEach((price, idx) => {
      const lineOptions: PriceLineOptions = {
        price,
        color: idx === 0 ? "#4ade80" : "#f59e0b",
        lineWidth: 1,
        lineStyle: 2, // Dashed
        axisLabelVisible: true,
        title: idx === 0 ? "S" : "R",
      };
      const line = priceSeries.createPriceLine(lineOptions);
      priceLineRefs.push(line);
    });
  };

  onMount(() => {
    if (!chartContainer) return;

    chart = createChart(chartContainer, {
      autoSize: true,
      layout: {
        background: { color: "#0f1117" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" },
      },
      crosshair: {
        mode: 0, // Normal mode - free movement, doesn't snap to candles
        vertLine: { color: "#475569", labelBackgroundColor: "#1e293b" },
        horzLine: { color: "#475569", labelBackgroundColor: "#1e293b" },
      },
      rightPriceScale: { borderColor: "#1e293b" },
      timeScale: { borderColor: "#1e293b", timeVisible: true },
    });

    buildPriceSeries();

    volumeSeries = chart.addSeries(HistogramSeries, {
      color: "#334155",
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
    });

    // Fetch current day candle if applicable
    fetchCurrentDayCandle();

    // Start polling for updates
    pollingManager.start(() => {
      if (resolution() === "D") {
        fetchCurrentDayCandle();
      }
    });

    onCleanup(() => {
      pollingManager.stop();
      chart?.remove();
    });
  });

  const toChartTime = (isoStr: string, res: Resolution): any =>
    res === "D" ? isoStr.split("T")[0] : Math.floor(new Date(isoStr).getTime() / 1000);

  const fetchCandles = async (sym: string, res: Resolution, range: DailyRange) => {
    setIsLoading(true);
    setError(null);
    try {
      const { from, to } = getDateRange(res, range);
      const data = await stocksAPI.getCandles(sym, res, from, to);
      setCandles(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load chart");
      setCandles([]);
    } finally {
      setIsLoading(false);
    }
  };

  async function fetchCurrentDayCandle() {
    if (resolution() !== "D") {
      setCurrentDayCandle(null);
      return;
    }

    if (!isMarketOpen()) {
      setCurrentDayCandle(null);
      return;
    }

    try {
      setIsLoading(true);
      const response = await fetch(
        `/api/stocks/${props.symbol}/candles/intraday?resolution=1h`
      );
      const data = await response.json();

      if (data.intraday && data.intraday.length > 0 && data.realtime) {
        const latestIntraday = data.intraday[data.intraday.length - 1];
        const currentCandle: CandleResponse = {
          time: latestIntraday.time,
          open: latestIntraday.open,
          high: Math.max(latestIntraday.high, data.realtime.last || latestIntraday.high),
          low: Math.min(latestIntraday.low, data.realtime.last || latestIntraday.low),
          close: data.realtime.last || latestIntraday.close,
          volume: latestIntraday.volume,
        };
        setCurrentDayCandle(currentCandle);
      }
    } catch (err) {
      console.error("Error fetching current day candle:", err);
    } finally {
      setIsLoading(false);
    }
  }

  const paintData = (data: CandleResponse[], res: Resolution) => {
    if (!chart || !priceSeries || !volumeSeries) return;
    if (data.length === 0) {
      priceSeries.setData([]);
      volumeSeries.setData([]);
      return;
    }
    priceSeries.setData(
      data.map((c) => ({
        time: toChartTime(c.time, res),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        value: c.close, // For baseline series
      }))
    );
    volumeSeries.setData(
      data.map((c) => ({
        time: toChartTime(c.time, res),
        value: c.volume,
        color: c.close >= c.open ? "rgba(74,222,128,0.4)" : "rgba(239,68,68,0.4)",
      }))
    );
    chart.timeScale().fitContent();
  };

  // Re-fetch whenever symbol, resolution, or dailyRange changes
  createEffect(() => {
    const sym = props.symbol;
    const res = resolution();
    const range = dailyRange();
    if (sym) fetchCandles(sym, res, range);
  });

  // Paint data whenever candles arrive
  createEffect(() => {
    const data = candles();
    const current = currentDayCandle();
    const res = untrack(resolution);

    const allCandles = current ? [...data, current] : data;
    paintData(allCandles, res);

    // Update indicators when data changes
    updateIndicators(allCandles);

    // Update price lines based on latest close
    if (allCandles.length > 0) {
      updatePriceLines(allCandles[allCandles.length - 1].close);
    }
  });

  // Rebuild price series when chart type toggles, then repaint
  createEffect(() => {
    chartType(); // track
    if (!chart) return;
    buildPriceSeries();
    untrack(() => paintData(candles(), resolution()));
  });

  // Toggle indicator
  const toggleIndicator = (idx: number) => {
    setIndicators((prev) => {
      const updated = [...prev];
      updated[idx].enabled = !updated[idx].enabled;
      return updated;
    });
  };

  // Add price line
  const addPriceLine = () => {
    const currentPrice = candles()[candles().length - 1]?.close;
    if (currentPrice) {
      setPriceLines((prev) => [...prev, currentPrice]);
    }
  };

  // Clear price lines
  const clearPriceLines = () => {
    setPriceLines([]);
  };

  return (
    <div class="chart-panel">
      <Show when={props.symbol}>
        <div class="chart-header">
          <span class="symbol-name">{props.symbol}</span>
          <span class="symbol-price">
            {props.quote?.last.toFixed(2)}
            <Show when={props.quote}>
              <span class={`symbol-change ${props.quote!.change >= 0 ? "positive" : "negative"}`}>
                {props.quote!.change >= 0 ? "+" : ""}
                {props.quote!.change.toFixed(2)} ({props.quote!.change_pct.toFixed(2)}%)
              </span>
            </Show>
          </span>
        </div>
      </Show>

      <Show when={candles().length > 0}>
        <div class="stats-bar">
          <span>O {candles()[0].open.toFixed(2)}</span>
          <span>H {Math.max(...candles().map((c) => c.high)).toFixed(2)}</span>
          <span>L {Math.min(...candles().map((c) => c.low)).toFixed(2)}</span>
          <span>Vol {(candles().reduce((s, c) => s + c.volume, 0) / 1_000_000).toFixed(1)}M</span>
        </div>
      </Show>

      <div class="chart-controls">
        <div class="timeframe-selector">
          {(["5m", "15m", "1h", "D"] as Resolution[]).map((res) => (
            <button
              class={resolution() === res ? "active" : ""}
              onClick={() => setResolution(res)}
            >
              {res}
            </button>
          ))}
          <Show when={resolution() === "D"}>
            <>
              <span class="divider">|</span>
              {(["1M", "3M", "1Y"] as DailyRange[]).map((range) => (
                <button
                  class={dailyRange() === range ? "active" : ""}
                  onClick={() => setDailyRange(range)}
                >
                  {range}
                </button>
              ))}
            </>
          </Show>
        </div>

        <div class="indicator-selector">
          {indicators().map((ind, idx) => (
            <button
              class={() => (indicators()[idx].enabled ? "active" : "")}
              onClick={() => toggleIndicator(idx)}
            >
              {ind.type.toUpperCase()} {ind.period}
            </button>
          ))}
          <button
            class="secondary"
            onClick={addPriceLine}
            title="Add price line at current price"
          >
            + Line
          </button>
          <Show when={priceLines().length > 0}>
            <button
              class="secondary"
              onClick={clearPriceLines}
            >
              Clear Lines
            </button>
          </Show>
        </div>

        <div class="chart-type-selector">
          <button
            class={chartType() === "candle" ? "active" : ""}
            onClick={() => setChartType("candle")}
          >
            Candle
          </button>
          <button
            class={chartType() === "area" ? "active" : ""}
            onClick={() => setChartType("area")}
          >
            Area
          </button>
          <button
            class={chartType() === "baseline" ? "active" : ""}
            onClick={() => setChartType("baseline")}
          >
            Base
          </button>
        </div>
      </div>

      <div class="chart-container" ref={chartContainer!}>
        <Show when={isLoading()}>
          <div class="loading-skeleton">Loading chart...</div>
        </Show>
        <Show when={error()}>
          <div class="error-message">
            {error()}
            <button onClick={() => fetchCandles(props.symbol, resolution(), dailyRange())}>
              ↻ Retry
            </button>
          </div>
        </Show>
      </div>
    </div>
  );
}
