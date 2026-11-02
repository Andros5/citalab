import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, type Conversation } from "../../api";
import { useConversationSearch } from "./useConversationSearch";

vi.mock("../../api", () => ({ api: vi.fn() }));
const request = vi.mocked(api);
const rows = (start = 0, length = 20) =>
  Array.from({ length }, (_, i) => ({ id: `c${start + i}` }) as Conversation);
const page = (start = 0, length = 20, total = 45) => ({
  items: rows(start, length),
  total,
});
const deferred = () => {
  let resolve!: (value: unknown) => void;
  let reject!: (value: unknown) => void;
  const promise = new Promise((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
};

beforeEach(() => request.mockReset());
afterEach(() => vi.useRealTimers());

describe("Historial progresivo", () => {
  it("solo carga la primera página hasta que se solicitan más filas", async () => {
    request.mockResolvedValueOnce(page()).mockResolvedValueOnce(page(20));
    const { result } = renderHook(() => useConversationSearch("", ""));
    await waitFor(() => expect(result.current.items).toHaveLength(20));
    expect(request).toHaveBeenCalledTimes(1);
    expect(result.current.hasMore).toBe(true);
    act(() => result.current.loadMore());
    await waitFor(() => expect(result.current.items).toHaveLength(40));
    expect(request.mock.calls[1][0]).toContain("page=2&page_size=20");
  });

  it("bloquea solicitudes simultáneas y conserva la lista durante la carga", async () => {
    const next = deferred();
    request.mockResolvedValueOnce(page()).mockReturnValueOnce(next.promise);
    const { result } = renderHook(() => useConversationSearch("", ""));
    await waitFor(() => expect(result.current.items).toHaveLength(20));
    act(() => {
      result.current.loadMore();
      result.current.loadMore();
    });
    expect(request).toHaveBeenCalledTimes(2);
    expect(result.current.items).toHaveLength(20);
    expect(result.current.loading).toBe(true);
    await act(async () => next.resolve(page(20, 5, 25)));
    expect(result.current.items).toHaveLength(25);
    expect(result.current.hasMore).toBe(false);
    act(() => result.current.loadMore());
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("conserva filas ante un error, no reintenta automáticamente y reintenta la misma página", async () => {
    request
      .mockResolvedValueOnce(page())
      .mockRejectedValueOnce(new Error("Sin conexión"))
      .mockResolvedValueOnce(page(20, 5, 25));
    const { result } = renderHook(() => useConversationSearch("", ""));
    await waitFor(() => expect(result.current.items).toHaveLength(20));
    act(() => result.current.loadMore());
    await waitFor(() => expect(result.current.error).toBe("Sin conexión"));
    expect(result.current.items).toHaveLength(20);
    act(() => result.current.loadMore());
    expect(request).toHaveBeenCalledTimes(2);
    act(() => result.current.retry());
    await waitFor(() => expect(result.current.items).toHaveLength(25));
    expect(request.mock.calls[2][0]).toContain("page=2");
    expect(result.current.error).toBe("");
  });

  it("cancela y descarta respuestas antiguas al cambiar los filtros", async () => {
    const old = deferred();
    request
      .mockReturnValueOnce(old.promise)
      .mockResolvedValueOnce(page(100, 1, 1));
    const { result, rerender } = renderHook(
      ({ q, architecture, status }) =>
        useConversationSearch(q, architecture, status),
      { initialProps: { q: "", architecture: "M5", status: "" } },
    );
    await waitFor(() => expect(request).toHaveBeenCalledTimes(1));
    const signal = request.mock.calls[0][3]?.signal;
    rerender({ q: "familia", architecture: "S1", status: "COMPLETED" });
    expect(signal?.aborted).toBe(true);
    await waitFor(() => expect(result.current.items[0]?.id).toBe("c100"));
    await act(async () => old.resolve(page()));
    expect(result.current.items).toHaveLength(1);
    expect(request.mock.calls[1][0]).toContain(
      "q=familia&architecture=S1&status=COMPLETED&page=1",
    );
  });

  it("deduplica identificadores entre páginas y dentro de una página", async () => {
    request
      .mockResolvedValueOnce(page())
      .mockResolvedValueOnce({
        items: [...rows(19, 2), ...rows(20, 1)],
        total: 23,
      });
    const { result } = renderHook(() => useConversationSearch("", ""));
    await waitFor(() => expect(result.current.items).toHaveLength(20));
    act(() => result.current.loadMore());
    await waitFor(() => expect(result.current.items).toHaveLength(21));
    expect(new Set(result.current.items.map((item) => item.id)).size).toBe(21);
    expect(result.current.hasMore).toBe(false);
  });

  it("detiene la carga ante una página vacía aunque el total haya quedado obsoleto", async () => {
    request
      .mockResolvedValueOnce(page())
      .mockResolvedValueOnce(page(20, 0, 45));
    const { result } = renderHook(() => useConversationSearch("", ""));
    await waitFor(() => expect(result.current.items).toHaveLength(20));
    act(() => result.current.loadMore());
    await waitFor(() => expect(result.current.hasMore).toBe(false));
    expect(result.current.items).toHaveLength(20);
  });

  it("rechaza contratos inválidos sin convertirlos en una lista vacía válida", async () => {
    request.mockResolvedValue({ items: [{ id: null }], total: -1 });
    const { result } = renderHook(() => useConversationSearch("", ""));
    await waitFor(() => expect(result.current.error).toContain("no es válido"));
    expect(result.current.hasMore).toBe(false);
  });

  it("actualizar vuelve a la primera página y aborta una carga anterior", async () => {
    const old = deferred();
    request
      .mockResolvedValueOnce(page())
      .mockReturnValueOnce(old.promise)
      .mockResolvedValueOnce(page(100, 1, 1));
    const { result } = renderHook(() => useConversationSearch("", ""));
    await waitFor(() => expect(result.current.items).toHaveLength(20));
    act(() => result.current.loadMore());
    act(() => result.current.refresh());
    await waitFor(() => expect(result.current.items[0]?.id).toBe("c100"));
    await act(async () => old.reject(new Error("Fallo tardío")));
    expect(result.current.error).toBe("");
  });

  it("agrupa las ediciones rápidas de búsqueda y libera el temporizador al desmontar", async () => {
    vi.useFakeTimers();
    request.mockResolvedValue(page(0, 0, 0));
    const { rerender, unmount } = renderHook(
      ({ q }) => useConversationSearch(q, ""),
      { initialProps: { q: "fa" } },
    );
    rerender({ q: "familia" });
    await act(async () => {
      vi.advanceTimersByTime(150);
    });
    expect(request).toHaveBeenCalledTimes(1);
    expect(request.mock.calls[0][0]).toContain("q=familia");
    rerender({ q: "pediatría" });
    unmount();
    await act(async () => {
      vi.advanceTimersByTime(150);
    });
    expect(request).toHaveBeenCalledTimes(1);
  });
});
