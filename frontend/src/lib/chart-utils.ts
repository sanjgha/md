/**
 * Chart utilities for timeframe date calculations.
 */

export type Resolution = "5m" | "15m" | "1h" | "D";
export type DailyRange = "1M" | "3M" | "1Y";

/**
 * Calculate date range for a given resolution
 */
export function getDateRange(
  resolution: Resolution,
  dailyRange?: DailyRange
): { from: string; to: string } {
  const now = new Date();
  const to = formatDate(now);

  let from: Date;

  if (resolution === "D") {
    // Daily timeframe with sub-range selector
    const days = dailyRange ? {
      "1M": 30,
      "3M": 90,
      "1Y": 360,
    }[dailyRange] : 90;  // Default to 3M if not specified
    from = addDays(now, -days);
  } else {
    // Intraday timeframes
    const days = {
      "5m": 0,  // today only
      "15m": 5,  // last 5 trading days
      "1h": 5,  // last 5 trading days
    }[resolution];
    from = addDays(now, -days);
  }

  return { from: formatDate(from), to };
}

/**
 * Add days to a date (handles negative days)
 */
function addDays(date: Date, days: number): Date {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

/**
 * Format date as YYYY-MM-DD
 */
function formatDate(date: Date): string {
  return date.toISOString().split("T")[0];
}

/**
 * Get default resolution for panel 2 based on panel 1 resolution
 */
export function getDefaultPanel2Resolution(panel1Resolution: Resolution): Resolution {
  const mapping: Record<Resolution, Resolution> = {
    "5m": "1h",
    "15m": "1h",
    "1h": "D",
    "D": "1h",
  };
  return mapping[panel1Resolution];
}
