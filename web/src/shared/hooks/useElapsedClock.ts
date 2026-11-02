import { useEffect, useState } from "react";
import type { Call } from "../../api";

/** A display clock, not an estimate of completion or an extra API poll. */
export function useElapsedClock(active: boolean) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [active]);
  return now;
}

export function callElapsedMs(call: Call, now: number): number | null {
  if (call.status !== "running") {
    if (call.latency_ms != null) return call.latency_ms;
    if (!call.finished_at) return null;
  }
  const start = Date.parse(call.started_at);
  const end = call.status === "running" ? now : Date.parse(call.finished_at!);
  return Number.isFinite(start) && Number.isFinite(end) ? Math.max(0, end - start) : null;
}
