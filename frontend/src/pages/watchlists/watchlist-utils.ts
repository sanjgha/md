/**
 * Utility functions for watchlist navigation
 */

import type { QuoteResponse } from "./types";

/**
 * Navigate through a list of quotes with keyboard direction.
 * Handles wraparound at edges and returns the next symbol to select.
 *
 * @param quotes - Array of quote responses to navigate through
 * @param currentSymbol - Currently selected symbol (null for no selection)
 * @param direction - "up" for ArrowUp, "down" for ArrowDown
 * @returns Next symbol to select, or null if quotes array is empty
 */
export function navigateQuotes(
  quotes: QuoteResponse[],
  currentSymbol: string | null,
  direction: "up" | "down",
): string | null {
  // Return null for empty array
  if (quotes.length === 0) {
    return null;
  }

  // Return first symbol when current is null or unknown
  if (currentSymbol === null) {
    return quotes[0].symbol;
  }

  const currentIndex = quotes.findIndex((q) => q.symbol === currentSymbol);

  // If current symbol is not found, return first symbol
  if (currentIndex === -1) {
    return quotes[0].symbol;
  }

  // Calculate next index with wraparound
  if (direction === "down") {
    const nextIndex = (currentIndex + 1) % quotes.length;
    return quotes[nextIndex].symbol;
  } else {
    // direction === "up"
    const prevIndex = (currentIndex - 1 + quotes.length) % quotes.length;
    return quotes[prevIndex].symbol;
  }
}
