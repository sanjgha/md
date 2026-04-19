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

export function ChartPanel(props: Props) {
  const [resolution, setResolution] = createSignal<Resolution>(props.defaultResolution ?? "D");
  const [dailyRange, setDailyRange] = createSignal<DailyRange>("3M");
  const [chartType, setChartType] = createSignal<"candle" | "area">("candle");
  const [candles, setCandles] = createSignal<CandleResponse[]>([]);
  const [isLoading, setIsLoading] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);

  let chartContainer: HTMLDivElement | undefined;
  let chart: IChartApi | undefined;
  let priceSeries: ISeriesApi<"Candlestick" | "Area"> | undefined;
  let volumeSeries: ISeriesApi<"Histogram"> | undefined;

  // Build (or rebuild) the price series for the current chartType
  const buildPriceSeries = () => {
    if (!chart) return;
    if (priceSeries) chart.removeSeries(priceSeries);
    priceSeries =
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
            topColor: "rgba(74, 222, 128, 0.25)",
            bottomColor: "rgba(74, 222, 128, 0.0)",
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

    onCleanup(() => chart?.remove());
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

  const paintData = (data: CandleResponse[], res: Resolution) => {
    if (!chart || !priceSeries || !volumeSeries || data.length === 0) return;
    priceSeries.setData(
      data.map((c) => ({
        time: toChartTime(c.time, res),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
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
    const res = untrack(resolution);
    paintData(data, res);
  });

  // Rebuild price series when chart type toggles, then repaint
  createEffect(() => {
    chartType(); // track
    if (!chart) return;
    buildPriceSeries();
    untrack(() => paintData(candles(), resolution()));
  });

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
        <button
          class="chart-type-toggle"
          onClick={() => setChartType(chartType() === "candle" ? "area" : "candle")}
        >
          {chartType() === "candle" ? "Candle" : "Area"}
        </button>
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
