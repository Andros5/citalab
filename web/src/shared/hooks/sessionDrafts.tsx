import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from "react";

type DraftStore = {
  values: Map<string, unknown>;
  dirty: Set<string>;
};
const DraftContext = createContext<DraftStore | null>(null);

/** Solo memoria y sesión autenticada: ningún borrador se guarda en el navegador. */
export function SessionDraftProvider({ children }: { children: ReactNode }) {
  const store = useRef<DraftStore>({ values: new Map(), dirty: new Set() });
  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (store.current.dirty.size) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, []);
  return (
    <DraftContext.Provider value={store.current}>
      {children}
    </DraftContext.Provider>
  );
}

export function useSessionDraft<T>(
  key: string,
  initial: T,
): [T, Dispatch<SetStateAction<T>>] {
  const store = useContext(DraftContext);
  const [value, setValue] = useState<T>(() =>
    store?.values.has(key) ? (store.values.get(key) as T) : initial,
  );
  const set = useCallback<Dispatch<SetStateAction<T>>>(
    (update) => {
      setValue((current) => {
        const next =
          typeof update === "function"
            ? (update as (current: T) => T)(current)
            : update;
        store?.values.set(key, next);
        return next;
      });
    },
    [key, store],
  );
  return [value, set];
}

export function useDraftStatus(key: string, dirty: boolean) {
  const store = useContext(DraftContext);
  useEffect(() => {
    if (dirty) store?.dirty.add(key);
    else store?.dirty.delete(key);
  }, [dirty, key, store]);
}

export function useConfirmSessionExit() {
  const store = useContext(DraftContext);
  return () =>
    !store?.dirty.size ||
    window.confirm(
      "Hay cambios sin guardar. ¿Quieres cerrar sesión y descartarlos?",
    );
}
