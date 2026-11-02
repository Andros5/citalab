import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";

/** Carga cancelable para vistas de lectura, con vacío, error y reintento explícitos. */
export function useResource<T>(
  path: string | null,
  validate?: (value: unknown) => value is T,
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(!!path);
  const [revision, setRevision] = useState(0);
  const retry = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError("");
    setLoading(!!path);
    if (path)
      api<T>(path, "GET", undefined, { signal: controller.signal })
        .then((value) => {
          if (validate && !validate(value))
            throw new Error(
              "La respuesta recibida no tiene el formato esperado. Puedes volver a consultar.",
            );
          if (!controller.signal.aborted) setData(value);
        })
        .catch((e) => {
          if (!controller.signal.aborted) setError(e.message);
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    return () => controller.abort();
  }, [path, revision, validate]);
  return { data, error, loading, retry };
}
