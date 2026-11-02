import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Conversation } from "../../api";

const PAGE_SIZE = 20;
type Page = { items: Conversation[]; total: number };

export function useConversationSearch(
  q: string,
  architecture: string,
  status = "",
) {
  const [items, setItems] = useState<Conversation[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [hasMore, setHasMore] = useState(false);
  const [revision, setRevision] = useState(0);
  // A filter generation owns its page and synchronous request lock. Late replies
  // cannot append to a newer query, even when transport ignores cancellation.
  const session = useRef<{
    controller: AbortController;
    page: number;
    busy: boolean;
    more: boolean;
    failed: boolean;
    load: () => void;
  } | null>(null);
  const retry = useCallback(() => {
    if (session.current?.failed) session.current.load();
  }, []);
  const refresh = useCallback(() => setRevision((v) => v + 1), []);
  const loadMore = useCallback(() => {
    if (session.current?.more && !session.current.failed)
      session.current.load();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    const current = {
      controller,
      page: 1,
      busy: false,
      more: true,
      failed: false,
      load: () => {},
    };
    session.current = current;
    setItems([]);
    setTotal(0);
    setHasMore(false);
    setLoading(true);
    setError("");
    current.load = () => {
      if (current.busy || controller.signal.aborted) return;
      current.busy = true;
      current.failed = false;
      setLoading(true);
      setError("");
      const page = current.page;
      void api<Page>(
        `/conversations/page?q=${encodeURIComponent(q)}&architecture=${encodeURIComponent(architecture)}&status=${encodeURIComponent(status)}&page=${page}&page_size=${PAGE_SIZE}`,
        "GET",
        undefined,
        { signal: controller.signal },
      )
        .then((value) => {
          if (controller.signal.aborted || session.current !== current) return;
          if (
            !value ||
            !Array.isArray(value.items) ||
            !Number.isInteger(value.total) ||
            value.total < 0 ||
            value.items.some((item) => !item || typeof item.id !== "string")
          )
            throw new Error("El historial recibido no es válido.");
          setItems((previous) => {
            const seen = new Set(previous.map((item) => item.id));
            return [
              ...previous,
              ...value.items.filter((item) => {
                if (seen.has(item.id)) return false;
                seen.add(item.id);
                return true;
              }),
            ];
          });
          setTotal(value.total);
          current.page = page + 1;
          current.more =
            value.items.length === PAGE_SIZE && page * PAGE_SIZE < value.total;
          setHasMore(current.more);
        })
        .catch((e) => {
          if (controller.signal.aborted || session.current !== current) return;
          current.failed = true;
          setError(
            e instanceof Error
              ? e.message
              : "El historial recibido no es válido.",
          );
        })
        .finally(() => {
          if (controller.signal.aborted || session.current !== current) return;
          current.busy = false;
          setLoading(false);
        });
    };
    const timer = setTimeout(current.load, q ? 150 : 0);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [q, architecture, status, revision]);
  return {
    items,
    setItems,
    total,
    error,
    loading,
    hasMore,
    retry,
    refresh,
    loadMore,
  };
}
