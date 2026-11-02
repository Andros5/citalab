import { MotionConfig } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, setCsrf, type Bootstrap, type User } from "../api";
import { ErrorState, Notice, Skeleton } from "../components";
import { LoginPage } from "../features/auth/LoginPage";
import {
  getSavedLanguage,
  LocaleProvider,
  normalizeLanguage,
  saveLanguage,
  type UiLanguage,
} from "../i18n";
import { Shell } from "./Shell";

export function App() {
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null);
  const [language, setLanguageState] = useState<UiLanguage>(
    () =>
      getSavedLanguage() ??
      (navigator.language.toLowerCase().startsWith("en") ? "en" : "es"),
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expired, setExpired] = useState(false);
  const generation = useRef(0);
  const authenticated = useRef(false);
  const account = useRef<string | null>(null);
  const languageRef = useRef(language);
  const setLanguage = useCallback((value: UiLanguage) => {
    const next = normalizeLanguage(value);
    languageRef.current = next;
    setLanguageState(next);
    saveLanguage(next, account.current);
  }, []);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    const current = ++generation.current;
    setError("");
    const session = await api<{ user: User; csrf: string }>(
      "/auth/me",
      "GET",
      undefined,
      { signal },
    );
    if (current !== generation.current || signal?.aborted) return;
    setCsrf(session.csrf);
    const data = await api<Bootstrap>("/bootstrap", "GET", undefined, {
      signal,
    });
    if (current !== generation.current || signal?.aborted) return;
    if (
      !data?.user?.username ||
      !data.config?.config ||
      !Array.isArray(data.patients)
    )
      throw new Error("La configuración de acceso recibida no es válida.");
    account.current = data.user.username;
    const accountLanguage = getSavedLanguage(data.user.username);
    const nextLanguage = accountLanguage ?? languageRef.current;
    languageRef.current = nextLanguage;
    setLanguageState(nextLanguage);
    saveLanguage(nextLanguage, data.user.username);
    authenticated.current = true;
    setBootstrap(data);
    setExpired(false);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    refresh(controller.signal)
      .catch((e) => {
        if (!controller.signal.aborted && e.status !== 401) setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    const onExpired = () => {
      generation.current += 1;
      setBootstrap(null);
      setCsrf("");
      setExpired(authenticated.current);
      authenticated.current = false;
      account.current = null;
    };
    window.addEventListener("session-expired", onExpired);
    return () => {
      controller.abort();
      generation.current += 1;
      window.removeEventListener("session-expired", onExpired);
    };
  }, [refresh]);
  const logout = async () => {
    setError("");
    try {
      await api("/auth/logout", "POST");
      generation.current += 1;
      authenticated.current = false;
      setBootstrap(null);
      setCsrf("");
      setExpired(false);
      account.current = null;
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <LocaleProvider language={language} setLanguage={setLanguage}>
      <MotionConfig reducedMotion="user">
        {loading ? (
          <Skeleton label="Comprobando acceso…" />
        ) : (
          <>
            {expired && (
              <Notice>Tu sesión ha caducado. Vuelve a entrar para continuar.</Notice>
            )}
            {error && (
              <ErrorState
                message={error}
                retry={() => {
                  refresh().catch((e) => setError(e.message));
                }}
              />
            )}
            {bootstrap ? (
              <Shell
                key={bootstrap.user.username}
                bootstrap={bootstrap}
                refresh={refresh}
                logout={logout}
              />
            ) : (
              <LoginPage onLogin={refresh} />
            )}
          </>
        )}
      </MotionConfig>
    </LocaleProvider>
  );
}
