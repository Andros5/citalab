import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type Job } from "../../api";

/**
 * Observa un trabajo de uno en uno: nunca solapa solicitudes y se detiene ante
 * un estado terminal o un error que el usuario no puede resolver reintentando.
 */
export function useJobPolling(
  jobId: string | null | undefined,
  onUpdate: (job: Job) => void,
) {
  const callback = useRef(onUpdate);
  useEffect(() => {
    callback.current = onUpdate;
  }, [onUpdate]);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const retry = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    setError("");
    if (!jobId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    let terminal = false;
    let inFlight = false;
    let stopped = false;
    setError("");
    const poll = async () => {
      if (controller.signal.aborted || inFlight || terminal || stopped) return;
      inFlight = true;
      try {
        const job = await api<Job>(`/jobs/${jobId}`, "GET", undefined, {
          signal: controller.signal,
        });
        if (
          !job ||
          typeof job.id !== "string" ||
          typeof job.status !== "string"
        )
          throw new ApiError("Estado de ejecución no válido.", 200, "contract");
        if (controller.signal.aborted) return;
        callback.current(job);
        attempts = 0;
        setError("");
        terminal = !["queued", "running"].includes(job.status);
        if (!terminal) timer = setTimeout(poll, document.hidden ? 5000 : 1000);
      } catch (e) {
        if (controller.signal.aborted) return;
        setError((e as Error).message);
        attempts += 1;
        const fatal =
          e instanceof ApiError &&
          ([401, 403, 404].includes(e.status) || e.kind === "contract");
        stopped = fatal || attempts > 4;
        if (!fatal && attempts <= 4)
          timer = setTimeout(poll, Math.min(1000 * 2 ** attempts, 15000));
      } finally {
        inFlight = false;
      }
    };
    const visible = () => {
      if (!document.hidden && !terminal) {
        clearTimeout(timer);
        void poll();
      }
    };
    document.addEventListener("visibilitychange", visible);
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [jobId, revision]);
  return { error, retry };
}
