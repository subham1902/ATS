/**
 * Indian Exchange Market Hours and Session Evaluator.
 *
 * Supports:
 * - NSE / BSE (Cash Equity, Equity Derivatives, NIFTY 50, BANKNIFTY, FINNIFTY, SENSEX)
 *   Trading Hours: Monday to Friday 09:15 to 15:30 IST.
 * - MCX (Commodities: GOLDM, SILVERM, CRUDEOIL, NATURALGAS, COPPER)
 *   Trading Hours: Monday to Friday 09:00 to 23:30 IST (extended to 23:55 IST in winter).
 *
 * Accurately handles IST timezone conversion regardless of local browser timezone.
 */

export interface MarketSessionInfo {
  isOpen: boolean;
  exchange: "NSE" | "MCX" | "BSE";
  statusText: string; // "MARKET LIVE" | "MARKET CLOSED" | "WEEKEND CLOSED"
  badgeColor: string; // Hex color for status dot/pill
  badgeBackground: string;
  badgeBorder: string;
  sessionDetail: string; // Descriptive trading hours
  nextOpen: string; // Next scheduled session opening
}

/**
 * Returns the current date converted to Indian Standard Time (IST, UTC+5:30).
 */
export function getNowInIST(date: Date = new Date()): Date {
  const utcMs = date.getTime() + date.getTimezoneOffset() * 60000;
  const istOffsetMs = 5.5 * 60 * 60 * 1000;
  return new Date(utcMs + istOffsetMs);
}

/**
 * Evaluates whether an exchange is currently open for trading.
 */
export function getMarketSessionInfo(symbol: string, date: Date = new Date()): MarketSessionInfo {
  const istDate = getNowInIST(date);
  const day = istDate.getDay(); // 0 = Sun, 1 = Mon, ..., 6 = Sat
  const hours = istDate.getHours();
  const minutes = istDate.getMinutes();
  const timeInMinutes = hours * 60 + minutes;

  const upper = symbol.toUpperCase();
  const isMcx =
    upper.includes("MCX") ||
    upper.includes("GOLD") ||
    upper.includes("SILVER") ||
    upper.includes("CRUDE") ||
    upper.includes("NATURALGAS") ||
    upper.includes("NATGAS") ||
    upper.includes("COPPER");

  const exchange: "NSE" | "MCX" | "BSE" = isMcx ? "MCX" : upper.includes("SENSEX") ? "BSE" : "NSE";

  // 1. Weekend Check (Saturday & Sunday are exchange holidays for both NSE and MCX)
  if (day === 0 || day === 6) {
    return {
      isOpen: false,
      exchange,
      statusText: "WEEKEND CLOSED",
      badgeColor: "#94a3b8",
      badgeBackground: "rgba(148, 163, 184, 0.12)",
      badgeBorder: "rgba(148, 163, 184, 0.25)",
      sessionDetail: isMcx
        ? "MCX is closed on weekends (Trading: Mon-Fri 09:00 - 23:30 IST)"
        : "NSE is closed on weekends (Trading: Mon-Fri 09:15 - 15:30 IST)",
      nextOpen: isMcx ? "Opens Mon 09:00 IST" : "Opens Mon 09:15 IST",
    };
  }

  // 2. MCX Commodities (Monday to Friday, 09:00 to 23:30 IST)
  if (isMcx) {
    const mcxOpenMin = 9 * 60; // 09:00
    const mcxCloseMin = 23 * 60 + 30; // 23:30
    const isOpen = timeInMinutes >= mcxOpenMin && timeInMinutes <= mcxCloseMin;

    if (isOpen) {
      return {
        isOpen: true,
        exchange: "MCX",
        statusText: "MCX LIVE",
        badgeColor: "#4ade80",
        badgeBackground: "rgba(34, 197, 94, 0.15)",
        badgeBorder: "rgba(34, 197, 94, 0.35)",
        sessionDetail: "MCX Trading Active (09:00 - 23:30 IST)",
        nextOpen: "Closes 23:30 IST",
      };
    } else {
      return {
        isOpen: false,
        exchange: "MCX",
        statusText: "MCX CLOSED",
        badgeColor: "#f87171",
        badgeBackground: "rgba(239, 68, 68, 0.15)",
        badgeBorder: "rgba(239, 68, 68, 0.35)",
        sessionDetail: "MCX session is closed. Trading hours: 09:00 - 23:30 IST.",
        nextOpen: "Opens 09:00 IST",
      };
    }
  }

  // 3. NSE / BSE Indices (NIFTY 50, BANKNIFTY, FINNIFTY, SENSEX)
  // Monday to Friday, 09:15 to 15:30 IST
  const nseOpenMin = 9 * 60 + 15; // 09:15
  const nseCloseMin = 15 * 60 + 30; // 15:30
  const isOpen = timeInMinutes >= nseOpenMin && timeInMinutes <= nseCloseMin;

  if (isOpen) {
    return {
      isOpen: true,
      exchange,
      statusText: `${exchange} LIVE`,
      badgeColor: "#4ade80",
      badgeBackground: "rgba(34, 197, 94, 0.15)",
      badgeBorder: "rgba(34, 197, 94, 0.35)",
      sessionDetail: `${exchange} Normal Trading Active (09:15 - 15:30 IST)`,
      nextOpen: "Closes 15:30 IST",
    };
  } else {
    const isPostClose = timeInMinutes > nseCloseMin;
    return {
      isOpen: false,
      exchange,
      statusText: `${exchange} CLOSED`,
      badgeColor: "#f87171",
      badgeBackground: "rgba(239, 68, 68, 0.15)",
      badgeBorder: "rgba(239, 68, 68, 0.35)",
      sessionDetail: `${exchange} session closed. Trading hours: 09:15 - 15:30 IST. Price locked to closing quote.`,
      nextOpen: isPostClose ? "Opens Tomorrow 09:15 IST" : "Opens 09:15 IST",
    };
  }
}
