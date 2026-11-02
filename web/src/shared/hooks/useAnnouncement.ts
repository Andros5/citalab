import { useCallback, useEffect, useState } from "react";

/** Success announcements are transient; errors remain next to their operation. */
export function useAnnouncement() {
  const [message, setMessage] = useState("");
  const [paused, setPaused] = useState(false);
  const notify = useCallback((value: string) => setMessage(value), []);
  const dismiss = useCallback(() => setMessage(""), []);
  useEffect(() => {
    if (!message || paused) return;
    const timer = setTimeout(() => setMessage(""), 12000);
    return () => clearTimeout(timer);
  }, [message, paused]);
  return { message, notify, dismiss, setPaused };
}
