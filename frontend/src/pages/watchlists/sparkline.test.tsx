/**
 * Tests for Sparkline component
 */

import { describe, it, expect } from "vitest";
import { render } from "@solidjs/testing-library";
import { Sparkline } from "./sparkline";

describe("Sparkline", () => {
  it("renders green sparkline for bullish data", () => {
    const data = [
      { time: "2026-04-23T09:30:00", close: 180 },
      { time: "2026-04-23T10:30:00", close: 182 },
      { time: "2026-04-23T11:30:00", close: 185 },
      { time: "2026-04-23T12:30:00", close: 188 },
    ];

    const { container } = render(() => (
      <Sparkline data={data} color="green" width={48} height={16} />
    ));

    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("width")).toBe("48");
    expect(svg?.getAttribute("height")).toBe("16");

    const polyline = svg?.querySelector("polyline");
    expect(polyline).not.toBeNull();
    expect(polyline?.getAttribute("stroke")).toBe("#22c55e");
  });

  it("renders red sparkline for bearish data", () => {
    const data = [
      { time: "2026-04-23T09:30:00", close: 188 },
      { time: "2026-04-23T10:30:00", close: 185 },
      { time: "2026-04-23T11:30:00", close: 182 },
      { time: "2026-04-23T12:30:00", close: 180 },
    ];

    const { container } = render(() => (
      <Sparkline data={data} color="red" width={48} height={16} />
    ));

    const svg = container.querySelector("svg");
    const polyline = svg?.querySelector("polyline");
    expect(polyline?.getAttribute("stroke")).toBe("#ef4444");
  });

  it("renders gray sparkline for neutral/no data", () => {
    const { container } = render(() => (
      <Sparkline data={[]} color="gray" width={48} height={16} />
    ));

    const svg = container.querySelector("svg");
    const polyline = svg?.querySelector("polyline");
    expect(polyline?.getAttribute("stroke")).toBe("#94a3b8");
  });

  it("normalizes data points to fit SVG viewBox", () => {
    const data = [
      { time: "2026-04-23T09:30:00", close: 100 },
      { time: "2026-04-23T10:30:00", close: 200 },
    ];

    const { container } = render(() => (
      <Sparkline data={data} color="green" width={48} height={16} />
    ));

    const polyline = container.querySelector("polyline");
    const points = polyline?.getAttribute("points");

    // Points should be normalized to 0-15 range (height - 1 for padding)
    expect(points).toContain("0");  // min value maps to bottom
    expect(points).toContain("15"); // max value maps to top
  });

  it("handles single data point", () => {
    const data = [{ time: "2026-04-23T09:30:00", close: 150 }];

    const { container } = render(() => (
      <Sparkline data={data} color="green" width={48} height={16} />
    ));

    const polyline = container.querySelector("polyline");
    expect(polyline).not.toBeNull();
    // Single point should render a dot in the middle
    const points = polyline?.getAttribute("points");
    expect(points).toContain("8"); // middle of 0-15 range
  });
});
