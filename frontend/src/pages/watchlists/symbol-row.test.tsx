/**
 * Tests for SymbolRow component
 *
 * TDD: These tests verify the symbol row rendering including IVR and regime badges
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@solidjs/testing-library";
import { SymbolRow } from "./symbol-row";
import type { QuoteResponse } from "./types";
import type { IVRData, RegimeData } from "../../lib/options-api";

const realtimeQuote: QuoteResponse = {
  symbol: "AAPL",
  last: 186.59,
  change: 9.31,
  change_pct: 5.25,
  source: "realtime",
  date: null,
};

const eodQuote: QuoteResponse = {
  symbol: "GSAT",
  last: 79.85,
  change: -0.04,
  change_pct: -0.05,
  source: "eod",
  date: "2026-04-15",
};

describe("SymbolRow", () => {
  describe("basic rendering", () => {
    it("renders symbol ticker", () => {
      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
        />
      ));
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });

    it("renders last price", () => {
      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
        />
      ));
      expect(screen.getByText("186.59")).toBeInTheDocument();
    });

    it("renders positive change in green", () => {
      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
        />
      ));
      const changeEl = screen.getByText("+9.31");
      expect(changeEl.className).toContain("positive");
    });

    it("renders negative change in red", () => {
      render(() => (
        <SymbolRow
          quote={eodQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
        />
      ));
      const changeEl = screen.getByText("-0.04");
      expect(changeEl.className).toContain("negative");
    });

    it("calls onSelect when row is clicked", () => {
      const onSelect = vi.fn();
      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={onSelect}
          onRemove={vi.fn()}
        />
      ));
      fireEvent.click(screen.getByText("AAPL"));
      expect(onSelect).toHaveBeenCalledWith("AAPL");
    });

    it("calls onRemove when remove button is clicked", () => {
      const onRemove = vi.fn();
      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={onRemove}
        />
      ));
      fireEvent.click(screen.getByRole("button", { name: /remove aapl/i }));
      expect(onRemove).toHaveBeenCalledWith("AAPL");
    });

    it("renders — for null change", () => {
      const nullQuote: QuoteResponse = { ...eodQuote, change: null, change_pct: null };
      render(() => (
        <SymbolRow
          quote={nullQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
        />
      ));
      const dashes = screen.getAllByText("—");
      expect(dashes.length).toBeGreaterThanOrEqual(1);
    });

    it("adds selected class when selected=true", () => {
      const { container } = render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={true}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
        />
      ));
      expect(container.firstChild).toHaveClass("selected");
    });
  });

  describe("IVR badge", () => {
    it("renders IVR badge with green color class for low IVR (<30)", () => {
      const ivrData: IVRData = {
        symbol: "AAPL",
        ivr: 25,
        current_value: 0.28,
        calculation_basis: "30_day_hv",
        as_of_date: "2026-04-15",
      };

      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
          ivr={ivrData}
        />
      ));

      const ivrBadge = screen.getByText(/IVR 25/);
      expect(ivrBadge).toBeInTheDocument();
      expect(ivrBadge.className).toContain("bg-green-100");
      expect(ivrBadge.className).toContain("text-green-800");
    });

    it("renders IVR badge with amber color class for mid IVR (30-70)", () => {
      const ivrData: IVRData = {
        symbol: "AAPL",
        ivr: 50,
        current_value: 0.32,
        calculation_basis: "30_day_hv",
        as_of_date: "2026-04-15",
      };

      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
          ivr={ivrData}
        />
      ));

      const ivrBadge = screen.getByText(/IVR 50/);
      expect(ivrBadge).toBeInTheDocument();
      expect(ivrBadge.className).toContain("bg-amber-100");
      expect(ivrBadge.className).toContain("text-amber-800");
    });

    it("renders IVR badge with red color class for high IVR (>70)", () => {
      const ivrData: IVRData = {
        symbol: "AAPL",
        ivr: 85,
        current_value: 0.45,
        calculation_basis: "30_day_hv",
        as_of_date: "2026-04-15",
      };

      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
          ivr={ivrData}
        />
      ));

      const ivrBadge = screen.getByText(/IVR 85/);
      expect(ivrBadge).toBeInTheDocument();
      expect(ivrBadge.className).toContain("bg-red-100");
      expect(ivrBadge.className).toContain("text-red-800");
    });

    it("renders IVR badge with amber color class for boundary value (70)", () => {
      const ivrData: IVRData = {
        symbol: "AAPL",
        ivr: 70,
        current_value: 0.35,
        calculation_basis: "30_day_hv",
        as_of_date: "2026-04-15",
      };

      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
          ivr={ivrData}
        />
      ));

      const ivrBadge = screen.getByText(/IVR 70/);
      expect(ivrBadge).toBeInTheDocument();
      expect(ivrBadge.className).toContain("bg-amber-100");
      expect(ivrBadge.className).toContain("text-amber-800");
    });

    it("renders IVR badge with green color class for boundary value (29)", () => {
      const ivrData: IVRData = {
        symbol: "AAPL",
        ivr: 29,
        current_value: 0.25,
        calculation_basis: "30_day_hv",
        as_of_date: "2026-04-15",
      };

      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
          ivr={ivrData}
        />
      ));

      const ivrBadge = screen.getByText(/IVR 29/);
      expect(ivrBadge).toBeInTheDocument();
      expect(ivrBadge.className).toContain("bg-green-100");
      expect(ivrBadge.className).toContain("text-green-800");
    });

    it("shows — when ivr prop is null (data not available)", () => {
      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
          ivr={null}
        />
      ));

      const ivrPlaceholder = screen.getByText("—");
      expect(ivrPlaceholder).toBeInTheDocument();
      expect(ivrPlaceholder.className).toContain("text-gray-400");
    });

    it("shows — when ivr prop is undefined (not provided)", () => {
      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
        />
      ));

      const ivrPlaceholder = screen.getByText("—");
      expect(ivrPlaceholder).toBeInTheDocument();
      expect(ivrPlaceholder.className).toContain("text-gray-400");
    });

    it("includes title attribute explaining IVR", () => {
      const ivrData: IVRData = {
        symbol: "AAPL",
        ivr: 50,
        current_value: 0.32,
        calculation_basis: "30_day_hv",
        as_of_date: "2026-04-15",
      };

      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
          ivr={ivrData}
        />
      ));

      const ivrBadge = screen.getByText(/IVR 50/);
      expect(ivrBadge.getAttribute("title")).toBe(
        "Implied Volatility Rank — low = cheap premium, high = expensive"
      );
    });
  });

  describe("Regime badge", () => {
    it("renders trending bullish regime with correct label and green color", () => {
      const regimeData: RegimeData = {
        symbol: "AAPL",
        regime: "trending",
        direction: "bullish",
        adx: 45.5,
        atr_pct: 0.0234,
        as_of_date: "2026-04-15",
      };

      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
          regime={regimeData}
        />
      ));

      const regimeBadge = screen.getByText(/Trending ↑/);
      expect(regimeBadge).toBeInTheDocument();
      expect(regimeBadge.className).toContain("bg-green-100");
      expect(regimeBadge.className).toContain("text-green-800");
    });

    it("renders trending bearish regime with correct label and red color", () => {
      const regimeData: RegimeData = {
        symbol: "AAPL",
        regime: "trending",
        direction: "bearish",
        adx: 42.3,
        atr_pct: 0.0198,
        as_of_date: "2026-04-15",
      };

      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
          regime={regimeData}
        />
      ));

      const regimeBadge = screen.getByText(/Trending ↓/);
      expect(regimeBadge).toBeInTheDocument();
      expect(regimeBadge.className).toContain("bg-red-100");
      expect(regimeBadge.className).toContain("text-red-800");
    });

    it("renders ranging regime with correct label and gray color", () => {
      const regimeData: RegimeData = {
        symbol: "AAPL",
        regime: "ranging",
        direction: null,
        adx: 18.7,
        atr_pct: 0.0123,
        as_of_date: "2026-04-15",
      };

      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
          regime={regimeData}
        />
      ));

      const regimeBadge = screen.getByText(/Ranging/);
      expect(regimeBadge).toBeInTheDocument();
      expect(regimeBadge.className).toContain("bg-gray-100");
      expect(regimeBadge.className).toContain("text-gray-700");
    });

    it("renders transitional regime with correct label and amber color", () => {
      const regimeData: RegimeData = {
        symbol: "AAPL",
        regime: "transitional",
        direction: null,
        adx: 28.5,
        atr_pct: 0.0189,
        as_of_date: "2026-04-15",
      };

      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
          regime={regimeData}
        />
      ));

      const regimeBadge = screen.getByText(/Transitional/);
      expect(regimeBadge).toBeInTheDocument();
      expect(regimeBadge.className).toContain("bg-amber-100");
      expect(regimeBadge.className).toContain("text-amber-800");
    });

    it("does not render regime badge when regime prop is null", () => {
      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
          regime={null}
        />
      ));

      // Should not render any regime badges
      expect(screen.queryByText(/Trending/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Ranging/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Transitional/)).not.toBeInTheDocument();
    });

    it("does not render regime badge when regime prop is undefined", () => {
      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
        />
      ));

      // Should not render any regime badges
      expect(screen.queryByText(/Trending/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Ranging/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Transitional/)).not.toBeInTheDocument();
    });

    it("includes title attribute with ADX and ATR values", () => {
      const regimeData: RegimeData = {
        symbol: "AAPL",
        regime: "trending",
        direction: "bullish",
        adx: 45.5,
        atr_pct: 0.0234,
        as_of_date: "2026-04-15",
      };

      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
          regime={regimeData}
        />
      ));

      const regimeBadge = screen.getByText(/Trending ↑/);
      expect(regimeBadge.getAttribute("title")).toBe("ADX 45.5 | ATR% 2.34%");
    });
  });

  describe("combined IVR and regime badges", () => {
    it("renders both IVR and regime badges when both props are provided", () => {
      const ivrData: IVRData = {
        symbol: "AAPL",
        ivr: 55,
        current_value: 0.32,
        calculation_basis: "30_day_hv",
        as_of_date: "2026-04-15",
      };

      const regimeData: RegimeData = {
        symbol: "AAPL",
        regime: "trending",
        direction: "bullish",
        adx: 45.5,
        atr_pct: 0.0234,
        as_of_date: "2026-04-15",
      };

      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
          ivr={ivrData}
          regime={regimeData}
        />
      ));

      expect(screen.getByText(/IVR 55/)).toBeInTheDocument();
      expect(screen.getByText(/Trending ↑/)).toBeInTheDocument();
    });

    it("renders IVR badge but not regime when only IVR is provided", () => {
      const ivrData: IVRData = {
        symbol: "AAPL",
        ivr: 55,
        current_value: 0.32,
        calculation_basis: "30_day_hv",
        as_of_date: "2026-04-15",
      };

      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
          ivr={ivrData}
        />
      ));

      expect(screen.getByText(/IVR 55/)).toBeInTheDocument();
      // Should not render any regime badges (trending, ranging, transitional)
      expect(screen.queryByText(/Trending/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Ranging/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Transitional/)).not.toBeInTheDocument();
    });

    it("renders regime badge but shows IVR placeholder when only regime is provided", () => {
      const regimeData: RegimeData = {
        symbol: "AAPL",
        regime: "trending",
        direction: "bullish",
        adx: 45.5,
        atr_pct: 0.0234,
        as_of_date: "2026-04-15",
      };

      render(() => (
        <SymbolRow
          quote={realtimeQuote}
          selected={false}
          onSelect={vi.fn()}
          onRemove={vi.fn()}
          regime={regimeData}
        />
      ));

      expect(screen.getByText(/Trending ↑/)).toBeInTheDocument();
      // Should have IVR placeholder —
      expect(screen.getByText("—")).toBeInTheDocument();
    });
  });
});
