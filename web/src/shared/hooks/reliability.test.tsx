import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, type Conversation, type Job } from "../../api";
import { useConversation } from "../../features/conversations/useConversation";
import { useJobPolling } from "./useJobPolling";

const response = (data: unknown, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => data,
});
const conversation: Conversation = {
  id: "c1",
  owner: "investigador",
  subject_id: "patient-ana",
  subject_name: "Ana",
  title: "Prueba",
  architecture: "M5",
  provider: "offline",
  diagnostic: false,
  status: "READY",
  created_at: "",
  updated_at: "",
  turn_count: 0,
  turns: [],
  can_confirm: false,
  active_job: null,
  archived: false,
};
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("Cliente HTTP", () => {
  it.each([401, 403, 404, 409, 429, 500])(
    "conserva el estado %i sin reintentar",
    async (status) => {
      const fetch = vi
        .fn()
        .mockResolvedValue(response({ detail: "No disponible" }, status));
      vi.stubGlobal("fetch", fetch);
      await expect(api("/test")).rejects.toMatchObject({
        status,
        message: "No disponible",
      });
      expect(fetch).toHaveBeenCalledTimes(1);
    },
  );
  it("rechaza un JSON ilegible como contrato, no como éxito vacío", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => {
          throw new SyntaxError();
        },
      }),
    );
    await expect(api("/test")).rejects.toMatchObject({ kind: "contract" });
  });
  it("distingue red, cancelación y timeout", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await expect(api("/test")).rejects.toMatchObject({ kind: "network" });
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url, init) =>
          new Promise((_resolve, reject) =>
            init.signal.addEventListener("abort", () =>
              reject(new DOMException("aborted", "AbortError")),
            ),
          ),
      ),
    );
    const controller = new AbortController();
    const cancelled = api("/test", "GET", undefined, {
      signal: controller.signal,
    });
    controller.abort();
    await expect(cancelled).rejects.toMatchObject({ name: "AbortError" });
    await expect(
      api("/test", "GET", undefined, { timeoutMs: 5 }),
    ).rejects.toMatchObject({ kind: "timeout" });
  });
});

describe("Seguimiento de trabajos", () => {
  it("no solapa GET pendientes y cancela al salir", async () => {
    vi.useFakeTimers();
    let resolve!: (value: unknown) => void;
    const fetch = vi.fn(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    vi.stubGlobal("fetch", fetch);
    const update = vi.fn();
    const { unmount } = renderHook(() => useJobPolling("j1", update));
    await act(() => vi.advanceTimersByTimeAsync(5000));
    expect(fetch).toHaveBeenCalledTimes(1);
    unmount();
    await act(async () => resolve(response({ id: "j1", status: "running" })));
    expect(update).not.toHaveBeenCalled();
    await act(() => vi.advanceTimersByTimeAsync(30000));
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("se recupera de un error transitorio con GET y termina", async () => {
    vi.useFakeTimers();
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new TypeError())
      .mockResolvedValue(response({ id: "j1", status: "completed" }));
    vi.stubGlobal("fetch", fetch);
    const update = vi.fn();
    const { result } = renderHook(() => useJobPolling("j1", update));
    await act(() => vi.advanceTimersByTimeAsync(0));
    expect(result.current.error).toBeTruthy();
    await act(() => vi.advanceTimersByTimeAsync(2000));
    expect(update).toHaveBeenCalledWith(
      expect.objectContaining({ status: "completed" }),
    );
    expect(result.current.error).toBe("");
    await act(() => vi.advanceTimersByTimeAsync(30000));
    expect(fetch).toHaveBeenCalledTimes(2);
  });
  it("no reintenta 403 al volver a la pestaña", async () => {
    vi.useFakeTimers();
    const fetch = vi
      .fn()
      .mockResolvedValue(response({ detail: "Sin permiso" }, 403));
    vi.stubGlobal("fetch", fetch);
    renderHook(() => useJobPolling("j1", vi.fn()));
    await act(() => vi.advanceTimersByTimeAsync(0));
    act(() => document.dispatchEvent(new Event("visibilitychange")));
    await act(() => vi.advanceTimersByTimeAsync(30000));
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});

describe("Turnos y respuesta incierta", () => {
  it("keeps a rejected message visible as failed without resending", async () => {
    const fetch = vi.fn(async (_url, init) => init.method === "POST"
      ? response({ detail: "Envío rechazado" }, 403) : response(conversation));
    vi.stubGlobal("fetch", fetch);
    const { result } = renderHook(() => useConversation("c1"));
    await waitFor(() => expect(result.current.conversation).not.toBeNull());
    await act(async () => { await result.current.send("message", "Mensaje rechazado"); });
    expect(result.current.outgoing).toMatchObject({ message: "Mensaje rechazado", status: "failed" });
    expect(result.current.busy).toBe(false);
    expect(result.current.uncertain).toBe(false);
    expect(fetch.mock.calls.filter(([, init]) => init.method === "POST")).toHaveLength(1);
  });
  it("no reenvía automáticamente y la recuperación manual conserva request_id y contenido", async () => {
    const posts: Record<string, unknown>[] = [];
    const fetch = vi.fn(async (_url, init) => {
      if (init.method === "POST") {
        posts.push(JSON.parse(init.body));
        if (posts.length === 1) throw new TypeError("Respuesta perdida");
        return response({
          id: "j1",
          status: "completed",
        } satisfies Partial<Job>);
      }
      return response(conversation);
    });
    vi.stubGlobal("fetch", fetch);
    const { result } = renderHook(() => useConversation("c1"));
    await waitFor(() => expect(result.current.conversation?.id).toBe("c1"));
    await act(async () => {
      await result.current.send("message", "Quiero una cita");
    });
    expect(result.current.uncertain).toBe(true);
    expect(result.current.outgoing).toMatchObject({ message: "Quiero una cita", status: "uncertain" });
    const outgoingId = result.current.outgoing?.request_id;
    expect(posts).toHaveLength(1);
    await act(async () => {
      await result.current.send("message", "No duplicar");
    });
    expect(posts).toHaveLength(1);
    await act(async () => {
      await result.current.retryPending();
    });
    expect(posts).toHaveLength(2);
    expect(posts[1]).toEqual(posts[0]);
    expect(result.current.uncertain).toBe(false);
    expect(result.current.outgoing?.request_id).toBe(outgoingId);
  });
  it("doble activación durante envío produce un único POST", async () => {
    let finish!: (data: unknown) => void;
    const fetch = vi.fn((_url, init) =>
      init.method === "POST"
        ? new Promise((resolve) => {
            finish = resolve;
          })
        : Promise.resolve(response(conversation)),
    );
    vi.stubGlobal("fetch", fetch);
    const { result } = renderHook(() => useConversation("c1"));
    await waitFor(() => expect(result.current.conversation).not.toBeNull());
    let first!: Promise<boolean>;
    act(() => {
      first = result.current.send("message", "Una cita");
      void result.current.send("message", "Otra cita");
    });
    expect(
      fetch.mock.calls.filter(([, init]) => init.method === "POST"),
    ).toHaveLength(1);
    expect(result.current.outgoing).toMatchObject({ message: "Una cita", status: "sending" });
    await act(async () => {
      finish(response({ id: "j1", status: "completed" }));
      await first;
    });
    expect(result.current.outgoing).toMatchObject({ message: "Una cita", job_id: "j1", status: "processing" });
  });
  it("removes the outgoing bubble only when its persisted turn arrives", async () => {
    let posted = false;
    vi.stubGlobal("fetch", vi.fn(async (_url, init) => {
      if (init.method === "POST") {
        posted = true;
        return response({ id: "j1", status: "completed" });
      }
      return response(posted ? { ...conversation, turn_count: 1, turns: [{
        id: "t1", job_id: "j1", number: 1, request: "Hola", response: "Respuesta",
      }] } : conversation);
    }));
    const { result } = renderHook(() => useConversation("c1"));
    await waitFor(() => expect(result.current.conversation).not.toBeNull());
    await act(async () => { await result.current.send("message", "Hola"); });
    expect(result.current.outgoing).toBeNull();
    expect(result.current.conversation?.turn_count).toBe(1);
  });
});
