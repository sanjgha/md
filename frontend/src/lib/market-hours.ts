/**
 * Market hours detection for US equity markets.
 * Mon-Fri 9:30 AM - 4:00 PM ET.
 */

/**
 * Convert Date to US/Eastern timezone.
 */
function toET(date: Date): Date {
  // Create a new date in ET by using the timezone offset
  const tz = "America/New_York";
  const et = new Date(date.toLocaleString("en-US", { timeZone: tz }));
  return et;
}

/**
 * Check if US market is currently open.
 * Mon-Fri 9:30 AM - 4:00 PM ET.
 *
 * @param date - Date to check (defaults to now)
 * @returns true if market is open, false otherwise
 */
export function isMarketOpen(date: Date = new Date()): boolean {
  const et = toET(date);

  // Check weekend (0=Sunday, 6=Saturday)
  const day = et.getDay();
  if (day === 0 || day === 6) {
    return false;
  }

  const hour = et.getHours();
  const minute = et.getMinutes();

  // Before 9:30 AM or after 4:00 PM
  if (hour < 9 || hour >= 16) {
    return false;
  }

  // Between 9:00-9:30 AM
  if (hour === 9 && minute < 30) {
    return false;
  }

  return true;
}
