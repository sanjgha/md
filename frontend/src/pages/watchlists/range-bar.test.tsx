/**
 * Tests for RangeBar component
 */

import { describe, it, expect } from "vitest";
import { render } from "@solidjs/testing-library";
import { RangeBar } from "./range-bar";

describe("RangeBar", () => {
  it("renders gradient background with position marker", () => {
    const { container } = render(() => (
      <RangeBar low={100} high={200} current={150} width={32} height={14} />
    ));

    const bar = container.querySelector(".range-bar");
    expect(bar).not.toBeNull();

    const marker = container.querySelector(".range-bar__marker");
    expect(marker).not.toBeNull();

    // Position should be 50% (150 is midpoint of 100-200)
    const style = marker?.getAttribute("style");
    expect(style).toContain("left: 50%");
  });

  it("positions marker at high end when current equals high", () => {
    const { container } = render(() => (
      <RangeBar low={100} high={200} current={200} width={32} height={14} />
    ));

    const marker = container.querySelector(".range-bar__marker");
    const style = marker?.getAttribute("style");
    expect(style).toContain("left: 100%");
  });

  it("positions marker at low end when current equals low", () => {
    const { container } = render(() => (
      <RangeBar low={100} high={200} current={100} width={32} height={14} />
    ));

    const marker = container.querySelector(".range-bar__marker");
    const style = marker?.getAttribute("style");
    expect(style).toContain("left: 0%");
  });

  it("handles null values gracefully", () => {
    const { container } = render(() => (
      <RangeBar low={null} high={null} current={150} width={32} height={14} />
    ));

    const marker = container.querySelector(".range-bar__marker");
    // Should center marker when low/high are null
    const style = marker?.getAttribute("style");
    expect(style).toContain("left: 50%");
  });

  it("handles zero range (low equals high)", () => {
    const { container } = render(() => (
      <RangeBar low={150} high={150} current={150} width={32} height={14} />
    ));

    const marker = container.querySelector(".range-bar__marker");
    const style = marker?.getAttribute("style");
    expect(style).toContain("left: 50%");
  });
});
