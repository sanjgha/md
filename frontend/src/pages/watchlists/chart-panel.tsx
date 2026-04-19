/**
 * Single chart panel unit.
 * Owns its own resolution, dailyRange, and candles data.
 */

import { createEffect, createSignal, onCleanup, Show } from "solid-js";
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickSeries,
  AreaSeries,
  HistogramSeries,
} from "lightweight-charts";
import { stocksAPI, type CandleResponse } from "../../lib/stocks-api";
import {
  type DailyRange,
  type Resolution,
  getDateRange,
} from "../../lib/chart-utils";

interface QuoteData {
  last: number;
  change: number;
  change_pct: number;
}

interface Props {
  symbol: string;
  quote: QuoteData | null;
  selectedSymbol: () => string | null;
  defaultResolution?: Resolution;
}

interface ChartSeries {
  price: ISeriesApi<"Candlestick" | "Area">;
  volume: ISeriesApi<"Histogram">;
}

export function ChartPanel(props: Props) {
  // State
  const [resolution, setResolution] = createSignal<Resolution>(
    props.defaultResolution ?? "D"
  );
  const [dailyRange, setDailyRange] = createSignal<DailyRange>("3M");
  const [chartType, setChartType] = createSignal<"candle" | "area">("candle");
  const [candles, setCandles] = createSignal<CandleResponse[]>([]);
  const [isLoading, setIsLoading] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);

  // Chart refs
  let chartContainer: HTMLDivElement | undefined;
  let chart: IChartApi | undefined;
  let series: ChartSeries | undefined;

  // Fetch candles
  const fetchCandles = async () => {
    if (!props.symbol) return;

    setIsLoading(true);
    setError(null);

    try {
      const { from, to } = getDateRange(resolution(), dailyRange());
      const data = await stocksAPI.getCandles(props.symbol, resolution(), from, to);
      setCandles(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load chart";
      setError(message);
      setCandles([]);
    } finally {
      setIsLoading(false);
    }
  };

  // Initialize chart
  const initChart = () => {
    if (!chartContainer) return;

    const newChart = createChart(chartContainer, {
      width: chartContainer.clientWidth,
      height: 400,
      layout: {
        background: { color: "#0f1117" },
        textColor: "#94a3b8",
      },
    });
    chart = newChart;

    // Price series (candlestick or area)
    const priceSeries =
      chartType() === "candle"
        ? chart.addSeries(CandlestickSeries, {
            upColor: "#4ade80",
            downColor: "#ef4444",
            borderDownColor: "#ef4444",
            borderUpColor: "#4ade80",
            wickDownColor: "#ef4444",
            wickUpColor: "#4ade80",
          })
        : chart.addSeries(AreaSeries, {
            lineColor: "#4ade80",
            topColor: "rgba(74, 222, 128, 0.4)",
            bottomColor: "rgba(74, 222, 128, 0.0)",
          });

    // Volume series on its own scale so it doesn't crush the price axis
    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: "#334155",
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    series = { price: priceSeries, volume: volumeSeries };

    // Handle resize
    const resizeObserver = new ResizeObserver(() => {
      if (chart && chartContainer) {
        chart.applyOptions({
          width: chartContainer.clientWidth,
          height: 400,
        });
      }
    });
    resizeObserver.observe(chartContainer);

    onCleanup(() => {
      resizeObserver.disconnect();
      if (chart) chart.remove();
    });
  };

  // Convert ISO datetime string to the format lightweight-charts expects.
  // Daily: "YYYY-MM-DD"; intraday: Unix seconds.
  const toChartTime = (isoStr: string, res: Resolution): any => {
    if (res === "D") return isoStr.split("T")[0];
    return Math.floor(new Date(isoStr).getTime() / 1000);
  };

  // Update chart data
  const updateChart = () => {
    if (!chart || !series || candles().length === 0) return;

    const res = resolution();
    const candleData = candles().map((c) => ({
      time: toChartTime(c.time, res),
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    const volumeData = candles().map((c) => ({
      time: toChartTime(c.time, res),
      value: c.volume,
      color: c.close >= c.open ? "#4ade80" : "#ef4444",
    }));

    series.price?.setData(candleData);
    series.volume?.setData(volumeData);
  };

  // Effects
  createEffect(() => {
    initChart();
  });

  createEffect(() => {
    if (props.symbol) {
      fetchCandles();
    }
  });

  createEffect(() => {
    if (candles().length > 0) {
      updateChart();
    }
  });

  // Handlers
  const handleResolutionChange = (newRes: Resolution) => {
    setResolution(newRes);
  };

  const handleDailyRangeChange = (newRange: DailyRange) => {
    setDailyRange(newRange);
  };

  const handleChartTypeToggle = () => {
    setChartType(chartType() === "candle" ? "area" : "candle");
  };

  return (
    <div class="chart-panel">
      {/* Symbol Header */}
      <Show when={props.symbol}>
        <div class="chart-header">
          <span class="symbol-name">{props.symbol}</span>
          <span class="symbol-price">
            {props.quote?.last.toFixed(2)}
            <Show when={props.quote}>
              <span class={`symbol-change ${props.quote!.change >= 0 ? "positive" : "negative"}`}>
                {props.quote!.change >= 0 ? "+" : ""}{props.quote!.change.toFixed(2)} ({props.quote!.change_pct.toFixed(2)}%)
              </span>
            </Show>
          </span>
        </div>
      </Show>

      {/* Stats Bar */}
      <Show when={candles().length > 0}>
        <div class="stats-bar">
          <span>O {candles()[0].open.toFixed(2)}</span>
          <span>H {Math.max(...candles().map((c) => c.high)).toFixed(2)}</span>
          <span>L {Math.min(...candles().map((c) => c.low)).toFixed(2)}</span>
          <span>Vol {(candles().reduce((sum, c) => sum + c.volume, 0) / 1000000).toFixed(1)}M</span>
        </div>
      </Show>

      {/* Controls */}
      <div class="chart-controls">
        <div class="timeframe-selector">
          {(["5m", "15m", "1h", "D"] as Resolution[]).map((res) => (
            <button
              class={resolution() === res ? "active" : ""}
              onClick={() => handleResolutionChange(res)}
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
                  onClick={() => handleDailyRangeChange(range)}
                >
                  {range}
                </button>
              ))}
            </>
          </Show>
        </div>
        <button class="chart-type-toggle" onClick={handleChartTypeToggle}>
          {chartType() === "candle" ? "Candle" : "Area"}
        </button>
      </div>

      {/* Chart Canvas */}
      <div class="chart-container" ref={chartContainer!}>
        <Show when={isLoading()}>
          <div class="loading-skeleton">Loading chart...</div>
        </Show>
        <Show when={error()}>
          <div class="error-message">
            {error()}
            <button onClick={() => fetchCandles()}>↻ Retry</button>
          </div>
        </Show>
      </div>
    </div>
  );
}
