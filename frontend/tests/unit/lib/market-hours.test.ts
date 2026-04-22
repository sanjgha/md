import { describe, it, expect } from "vitest";
import { isMarketOpen } from "~/lib/market-hours";

describe("isMarketOpen", () => {
  it("returns true during regular hours on weekday", () => {
    const dt = new Date("2026-04-22T10:00:00-04:00"); // Tue 10am ET
    expect(isMarketOpen(dt)).toBe(true);
  });

  it("returns false before market open", () => {
    const dt = new Date("2026-04-22T09:00:00-04:00"); // Tue 9am ET
    expect(isMarketOpen(dt)).toBe(false);
  });

  it("returns false after market close", () => {
    const dt = new Date("2026-04-22T17:00:00-04:00"); // Tue 5pm ET
    expect(isMarketOpen(dt)).toBe(false);
  });

  it("returns false on weekends", () => {
    const dt = new Date("2026-04-19T10:00:00-04:00"); // Sat 10am ET
    expect(isMarketOpen(dt)).toBe(false);
  });

  it("returns true exactly at market open", () => {
    const dt = new Date("2026-04-20T09:30:00-04:00"); // Mon 9:30am ET
    expect(isMarketOpen(dt)).toBe(true);
  });

  it("returns false exactly at market close", () => {
    const dt = new Date("2026-04-20T16:00:00-04:00"); // Mon 4pm ET
    expect(isMarketOpen(dt)).toBe(false);
  });
});
