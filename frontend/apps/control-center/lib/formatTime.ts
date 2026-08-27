/**
 * Deterministic timestamp formatter for SSR and Client rendering.
 * Converts ISO timestamps to consistent, locale-independent "HH:MM:SS IST".
 * Guaranteed to produce identical strings on Server (Node.js) and Client (Browser).
 */
export function formatTimeIST(isoString?: string | null): string {
  if (!isoString) return "UNKNOWN";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return "UNKNOWN";
    // Deterministic +5:30 offset calculation
    const istMs = d.getTime() + (5 * 60 + 30) * 60 * 1000;
    const istDate = new Date(istMs);
    const hours = String(istDate.getUTCHours()).padStart(2, "0");
    const minutes = String(istDate.getUTCMinutes()).padStart(2, "0");
    const seconds = String(istDate.getUTCSeconds()).padStart(2, "0");
    return `${hours}:${minutes}:${seconds} IST`;
  } catch {
    return "UNKNOWN";
  }
}
