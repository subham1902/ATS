import type { StreamEvent } from "./types";

export type SseStatus = "connecting" | "connected" | "disconnected" | "error";

export interface ParsedSseEvent {
  id: string;
  event: string;
  data: StreamEvent;
  raw: string;
}

/** Parse a single SSE frame (id/event/data) as emitted by backend serialize_sse. */
export function parseSseFrame(frame: string): ParsedSseEvent | null {
  const lines = frame.split("\n");
  let id = "";
  let event = "";
  let dataStr = "";
  for (const line of lines) {
    if (line.startsWith("id: ")) id = line.slice(4).trim();
    else if (line.startsWith("event: ")) event = line.slice(7).trim();
    else if (line.startsWith("data: ")) dataStr = line.slice(6);
  }
  if (!dataStr) return null;
  try {
    const data = JSON.parse(dataStr) as StreamEvent;
    return { id, event, data, raw: frame };
  } catch {
    return null;
  }
}

/** Minimal SSE client using fetch + ReadableStream for Node/tests; browser uses EventSource externally. */
export async function* iterateSseResponse(response: Response): AsyncGenerator<ParsedSseEvent> {
  const text = await response.text();
  const frames = text.split("\n\n").filter(Boolean);
  for (const f of frames) {
    const parsed = parseSseFrame(f);
    if (parsed) yield parsed;
  }
}
