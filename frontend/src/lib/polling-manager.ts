/**
 * Polling manager for periodic data updates.
 * Singleton pattern - use the exported instance.
 */

import { isMarketOpen } from "./market-hours";

export class PollingManager {
  private interval: number | null = null;
  private callback: (() => void) | null = null;

  /**
   * Start polling with given callback.
   * Calls callback immediately, then every 30s during market hours.
   *
   * @param callback - Function to call on each poll
   */
  start(callback: () => void): void {
    if (this.interval !== null) {
      return; // Already polling
    }

    this.callback = callback;

    // Immediate first call
    this.poll();

    // Set up recurring timer
    this.interval = window.setInterval(() => {
      this.poll();
    }, 30000); // 30 seconds
  }

  /**
   * Stop polling.
   */
  stop(): void {
    if (this.interval !== null) {
      clearInterval(this.interval);
      this.interval = null;
    }
    this.callback = null;
  }

  /**
   * Check if currently polling.
   */
  isPolling(): boolean {
    return this.interval !== null;
  }

  /**
   * Check if market is open (delegates to market-hours utility).
   */
  isMarketOpen(): boolean {
    return isMarketOpen();
  }

  /**
   * Execute callback if market is open.
   */
  private poll(): void {
    if (this.callback && this.isMarketOpen()) {
      this.callback();
    }
  }
}

// Singleton instance
export const pollingManager = new PollingManager();
