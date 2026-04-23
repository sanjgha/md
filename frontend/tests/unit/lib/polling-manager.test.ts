import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { PollingManager } from "~/lib/polling-manager";

describe("PollingManager", () => {
  let manager: PollingManager;
  let callback: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    manager = new PollingManager();
    callback = vi.fn();
    vi.useFakeTimers();
  });

  afterEach(() => {
    manager.stop();
    vi.useRealTimers();
  });

  it("starts polling and calls callback immediately", () => {
    manager.start(callback);
    expect(callback).toHaveBeenCalledTimes(1);
  });

  it("calls callback every 30 seconds", () => {
    manager.start(callback);

    vi.advanceTimersByTime(30000); // 30s
    expect(callback).toHaveBeenCalledTimes(2);

    vi.advanceTimersByTime(30000); // 60s total
    expect(callback).toHaveBeenCalledTimes(3);
  });

  it("stops polling when stop() is called", () => {
    manager.start(callback);
    manager.stop();

    vi.advanceTimersByTime(60000);
    expect(callback).toHaveBeenCalledTimes(1); // Only initial call
  });

  it("respects market hours - no polling when closed", () => {
    vi.spyOn(manager, "isMarketOpen").mockReturnValue(false);
    manager.start(callback);

    vi.advanceTimersByTime(30000);
    expect(callback).not.toHaveBeenCalled();
  });
});
