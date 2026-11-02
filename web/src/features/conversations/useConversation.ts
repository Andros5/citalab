import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type Conversation, type Job } from "../../api";
import { useJobPolling } from "../../shared/hooks/useJobPolling";

export type OutgoingMessage = {
  request_id: string; message: string; expected_turn: number; job_id?: string;
  status: "sending" | "processing" | "uncertain" | "failed";
};

export function useConversation(id?: string) {
  const [outgoing, setOutgoing] = useState<OutgoingMessage | null>(null);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(!!id);
  const [posting, setPosting] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const live = useRef(true);
  const controller = useRef<AbortController | null>(null);
  const submitting = useRef(false);
  const pending = useRef<{
    action: string;
    message: string;
    request_id: string;
    expected_turn: number;
  } | null>(null);
  const refresh = useCallback(async () => {
    if (!id) return;
    controller.current?.abort();
    const request = new AbortController();
    controller.current = request;
    setLoading(true);
    setError("");
    try {
      const value = await api<Conversation>(
        `/conversations/${id}`,
        "GET",
        undefined,
        { signal: request.signal },
      );
      if (
        !value ||
        value.id !== id ||
        !Array.isArray(value.turns) ||
        typeof value.turn_count !== "number"
      )
        throw new ApiError(
          "La conversación recibida no tiene un formato válido.",
          200,
          "contract",
        );
      if (request.signal.aborted || !live.current) return;
      setConversation(value);
      setOutgoing(previous => previous && value.turns.some(turn =>
        previous.job_id && turn.job_id ? turn.job_id === previous.job_id : turn.number > previous.expected_turn
      ) ? null : previous);
      if (pending.current && value.turn_count > pending.current.expected_turn) {
        pending.current = null;
        setUncertain(false);
      }
      if (value.active_job) {
        const active = await api<Job>(
          `/jobs/${value.active_job}`,
          "GET",
          undefined,
          { signal: request.signal },
        );
        if (!request.signal.aborted && live.current) {
          setJob(active);
          setOutgoing(previous => previous ? { ...previous, job_id: active.id,
            status: ["queued", "running"].includes(active.status) ? "processing" : "failed" } : null);
          pending.current = null;
          setUncertain(false);
        }
      }
    } catch (e) {
      if (!request.signal.aborted && live.current)
        setError(
          e instanceof ApiError && e.status === 404
            ? "Esta conversación ya no está disponible."
            : (e as Error).message,
        );
    } finally {
      if (!request.signal.aborted && live.current) setLoading(false);
    }
  }, [id]);
  useEffect(() => {
    live.current = true;
    void refresh();
    return () => {
      live.current = false;
      controller.current?.abort();
    };
  }, [refresh]);
  const updateJob = useCallback(
    (value: Job) => {
      setJob(value);
      if (!["queued", "running"].includes(value.status)) {
        if (value.status !== "completed") {
          setOutgoing(previous => previous ? { ...previous, status: "failed" } : null);
        }
        void refresh();
        if (value.error) setError(value.error);
      }
    },
    [refresh],
  );
  const polling = useJobPolling(
    job && ["queued", "running"].includes(job.status)
      ? job.id
      : conversation?.active_job,
    updateJob,
  );
  const send = useCallback(
    async (
      action: "message" | "confirm" | "discard",
      message: string,
    ): Promise<boolean> => {
      if (
        !conversation ||
        conversation.active_job ||
        submitting.current ||
        (job && ["queued", "running"].includes(job.status)) ||
        uncertain
      )
        return false;
      const body = {
        action,
        message,
        request_id: crypto.randomUUID(),
        expected_turn: conversation.turn_count,
      };
      pending.current = body;
      setOutgoing(action === "message" ? { ...body, status: "sending" } : null);
      submitting.current = true;
      setPosting(true);
      setJob(null);
      setError("");
      try {
        const value = await api<Job>(
          `/conversations/${conversation.id}/turns`,
          "POST",
          body,
        );
        if (
          !value ||
          typeof value.id !== "string" ||
          typeof value.status !== "string"
        )
          throw new ApiError(
            "Respuesta de ejecución no válida. Comprueba el estado.",
            200,
            "contract",
          );
        if (!live.current) return false;
        pending.current = null;
        setOutgoing(previous => previous ? { ...previous, job_id: value.id, status: "processing" } : null);
        setJob(value);
        if (!["queued", "running"].includes(value.status)) await refresh();
        return true;
      } catch (e) {
        if (!live.current) return false;
        const ambiguous =
          !(e instanceof ApiError) ||
          e.status === 0 ||
          e.status >= 500 ||
          e.kind === "contract";
        setUncertain(ambiguous);
        setOutgoing(previous => previous ? { ...previous, status: ambiguous ? "uncertain" : "failed" } : null);
        if (!ambiguous) pending.current = null;
        setError((e as Error).message);
        return false;
      } finally {
        submitting.current = false;
        if (live.current) setPosting(false);
      }
    },
    [conversation, job, uncertain, refresh],
  );
  const retryPending = async () => {
    const body = pending.current;
    if (!body || !id || submitting.current) return;
    submitting.current = true;
    setPosting(true);
    setJob(null);
    setOutgoing(previous => previous ? { ...previous, status: "sending" } : null);
    try {
      const value = await api<Job>(`/conversations/${id}/turns`, "POST", body);
      if (!live.current) return;
      if (
        !value ||
        typeof value.id !== "string" ||
        typeof value.status !== "string"
      )
        throw new Error("Respuesta de ejecución no válida.");
      setJob(value);
      setOutgoing(previous => previous ? { ...previous, job_id: value.id, status: "processing" } : null);
      pending.current = null;
      setUncertain(false);
      setError("");
      if (!["queued", "running"].includes(value.status)) await refresh();
    } catch (e) {
      if (live.current) {
        setError((e as Error).message);
        setOutgoing(previous => previous ? { ...previous, status: "uncertain" } : null);
      }
    } finally {
      submitting.current = false;
      if (live.current) setPosting(false);
    }
  };
  return {
    outgoing,
    conversation,
    job,
    error,
    loading,
    posting,
    uncertain,
    refresh,
    send,
    retryPending,
    polling,
    busy:
      posting ||
      outgoing?.status === "processing" ||
      uncertain ||
      !!conversation?.active_job ||
      !!(job && ["queued", "running"].includes(job.status)),
  };
}
