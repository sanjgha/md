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

/**
 * Sort quotes by column with direction.
 * Returns a new sorted array without mutating the original.
 *
 * @param quotes - Array of quote responses to sort
 * @param col - Column to sort by ("ticker" | "last" | "chg_pct" | null)
 * @param dir - Sort direction ("asc" | "desc")
 * @returns New sorted array (original is unchanged)
 */
export function sortQuotes(
  quotes: QuoteResponse[],
  col: "ticker" | "last" | "chg_pct" | null,
  dir: "asc" | "desc",
): QuoteResponse[] {
  // Return copy of original when col is null
  if (col === null) {
    return [...quotes];
  }

  // Create a copy to avoid mutating the original
  const sorted = [...quotes];

  sorted.sort((a, b) => {
    let aValue: string | number;
    let bValue: string | number;

    // Extract values based on column
    if (col === "ticker") {
      aValue = a.symbol;
      bValue = b.symbol;
    } else if (col === "last") {
      // Use -Infinity for null values
      aValue = a.last ?? -Infinity;
      bValue = b.last ?? -Infinity;
    } else {
      // col === "chg_pct"
      // Use -Infinity for null values
      aValue = a.change_pct ?? -Infinity;
      bValue = b.change_pct ?? -Infinity;
    }

    // Compare values
    if (aValue < bValue) {
      return dir === "asc" ? -1 : 1;
    } else if (aValue > bValue) {
      return dir === "asc" ? 1 : -1;
    } else {
      return 0;
    }
  });

  return sorted;
}
