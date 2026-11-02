import { CheckCircle2, ClipboardCheck, Keyboard, PlugZap, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Empty, Notice, Skeleton } from "../../components";
import { tx } from "../../i18n";

// La revisión humana usa la app del jurado (python -m citalab_judge review), no la
// API del portal: es la que fija la muestra de 60 + 12, muestra la misma vista
// ciega que el juez y guarda en judge/reviews-v1.jsonl, que lee el informe de
// concordancia y la estimación PPI. Las notas del jurado no llegan nunca aquí.
export const REVIEW_API = "http://127.0.0.1:8766";
const REVIEW_COMMAND = "python -m citalab_judge review --campaign";

type Score = "0" | "1" | "2" | "3" | "NA";
const SCORES: Score[] = ["0", "1", "2", "3", "NA"];
type Rubric = {
  assistant: Record<string, { label: string; anchors: string[] }>;
  simulator: Record<string, { label: string; good: string; bad: string }>;
};
type PassProgress = { total: number; done: number; pending_results: number; available?: number };
export type ReviewStatus = {
  campaign: string;
  progress: Record<"1" | "2", PassProgress>;
  rubric: Rubric;
  second_pass_delay_hours: number;
};
type View = {
  sample_id: string;
  reference_time: string;
  conversation_language: string;
  user: { goal: string; style: string; instructions: string[]; confirm_button: string };
  profile: string[];
  agenda: { own_appointments_before: string[]; free_slots_before: string[]; observed_effects: string[] };
  messages: { n: number; role: string; text: string }[];
};
type Next = { done: boolean; pass?: number; view?: View; progress: Record<"1" | "2", PassProgress> };
type Draft = { assistant: Record<string, Score>; simulator: Record<string, Score>; evidence: number[]; notes: string };
const EMPTY: Draft = { assistant: {}, simulator: {}, evidence: [], notes: "" };

async function reviewApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(REVIEW_API + path, init);
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

export function useReviewStatus() {
  const [status, setStatus] = useState<ReviewStatus | null>(null);
  const [offline, setOffline] = useState(false);
  const [checking, setChecking] = useState(true);
  const check = useCallback(() => {
    setChecking(true);
    reviewApi<ReviewStatus>("/api/status")
      .then((value) => {
        setStatus(value);
        setOffline(false);
      })
      .catch(() => setOffline(true))
      .finally(() => setChecking(false));
  }, []);
  useEffect(check, [check]);
  return { status, offline, checking, check };
}

function draftKey(pass: number, sample: string) {
  return `citalab.review-draft.${pass}.${sample}`;
}

function readDraft(pass: number, sample: string): Draft {
  try {
    const raw = localStorage.getItem(draftKey(pass, sample));
    return raw ? { ...EMPTY, ...JSON.parse(raw) } : EMPTY;
  } catch {
    return EMPTY;
  }
}

export function BlindReview({ campaign }: { campaign: string }) {
  const { status, offline, checking, check } = useReviewStatus();
  const [reviewPass, setReviewPass] = useState(1);
  const [next, setNext] = useState<Next | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [active, setActive] = useState(0);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(0);
  const cards = useRef<(HTMLFieldSetElement | null)[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const value = await reviewApi<Next>(`/api/next?review_pass=${reviewPass}`);
      setNext(value);
      setDraft(value.view ? readDraft(reviewPass, value.view.sample_id) : EMPTY);
      setActive(0);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [reviewPass]);
  useEffect(() => {
    if (status) void load();
  }, [status, load]);

  const rubric = status?.rubric;
  const dimensions = useMemo(
    () =>
      rubric
        ? [
            ...Object.keys(rubric.assistant).map((key) => ({ group: "assistant" as const, key })),
            ...Object.keys(rubric.simulator).map((key) => ({ group: "simulator" as const, key })),
          ]
        : [],
    [rubric],
  );
  const view = next?.view;
  const update = useCallback(
    (change: (current: Draft) => Draft) => {
      setDraft((current) => {
        const value = change(current);
        if (view)
          try {
            localStorage.setItem(draftKey(reviewPass, view.sample_id), JSON.stringify(value));
          } catch {
            // Sin almacenamiento local el borrador solo vive en memoria.
          }
        return value;
      });
    },
    [reviewPass, view],
  );
  const setScore = useCallback(
    (index: number, value: Score) => {
      const dimension = dimensions[index];
      if (!dimension) return;
      update((current) => ({ ...current, [dimension.group]: { ...current[dimension.group], [dimension.key]: value } }));
      const following = Math.min(index + 1, dimensions.length - 1);
      setActive(following);
      cards.current[following]?.focus({ preventScroll: false });
    },
    [dimensions, update],
  );
  const filled = dimensions.filter(({ group, key }) => draft[group][key] !== undefined).length;
  const complete = dimensions.length > 0 && filled === dimensions.length;

  const save = useCallback(async () => {
    if (!view || !complete || saving) return;
    setSaving(true);
    setError("");
    try {
      await reviewApi("/api/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sample_id: view.sample_id,
          pass: reviewPass,
          scores: draft.assistant,
          simulator_scores: draft.simulator,
          evidence: draft.evidence.join(", "),
          notes: draft.notes,
        }),
      });
      try {
        localStorage.removeItem(draftKey(reviewPass, view.sample_id));
      } catch {
        // Nada que limpiar.
      }
      setSaved((value) => value + 1);
      await load();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }, [view, complete, saving, reviewPass, draft, load]);

  if (checking && !status) return <Skeleton label="Conectando con la revisión ciega…" />;
  if (offline || !status)
    return (
      <section className="panel review-offline">
        <PlugZap size={28} aria-hidden />
        <h2>{tx("La revisión ciega no está abierta")}</h2>
        <p>
          {tx(
            "La revisión humana se hace con la muestra fijada del jurado (60 episodios y 12 de segunda pasada), con la misma vista ciega que reciben los jueces. Ábrela en una terminal desde la raíz del proyecto:",
          )}
        </p>
        <pre className="command">
          {REVIEW_COMMAND} {campaign}
        </pre>
        <p className="muted">
          {tx("Tus notas se guardan en judge/reviews-v1.jsonl y alimentan el informe de concordancia y la estimación PPI.")}
        </p>
        <button type="button" className="primary" onClick={check}>
          <RefreshCw size={16} /> {tx("Comprobar de nuevo")}
        </button>
      </section>
    );

  const progress = next?.progress ?? status.progress;
  const current = progress[String(reviewPass) as "1" | "2"];
  const percent = current.total ? Math.round((current.done / current.total) * 100) : 0;

  return (
    <div className="review">
      {status.campaign !== campaign && (
        <Notice>
          {tx("El servidor de revisión está abierto para la campaña")} <strong>{status.campaign}</strong>.{" "}
          {tx("Las notas se guardan en esa campaña, no en la seleccionada arriba.")}
        </Notice>
      )}
      <section className="review-head panel">
        <div className="review-pass" role="radiogroup" aria-label={tx("Pasada de revisión")}>
          {[1, 2].map((value) => {
            const item = progress[String(value) as "1" | "2"];
            return (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={reviewPass === value}
                className={reviewPass === value ? "active" : ""}
                onClick={() => setReviewPass(value)}
              >
                <span>{value === 1 ? tx("Primera pasada") : tx("Segunda pasada")}</span>
                <strong>
                  {item.done}/{item.total}
                </strong>
              </button>
            );
          })}
        </div>
        <div className="review-progress" aria-label={tx("Progreso de la pasada")}>
          <div className="bar">
            <span style={{ width: `${percent}%` }} />
          </div>
          <small>
            {percent} % · {current.pending_results ? `${current.pending_results} ${tx("episodios aún sin resultado")} · ` : ""}
            {reviewPass === 2
              ? tx("Cada episodio se habilita 48 h después de su primera revisión.")
              : tx("Orden aleatorio fijo; arquitectura, proveedor y notas del jurado ocultos.")}
          </small>
        </div>
        <details className="review-keys">
          <summary>
            <Keyboard size={16} /> {tx("Atajos")}
          </summary>
          <p>
            <kbd>0</kbd>–<kbd>3</kbd> {tx("puntúa")} · <kbd>N</kbd> NA · <kbd>↑</kbd>
            <kbd>↓</kbd> {tx("cambia de dimensión")} · <kbd>Ctrl</kbd>+<kbd>Enter</kbd> {tx("guarda")}
          </p>
        </details>
      </section>

      {saved > 0 && !view && <Notice tone="success">{tx("Revisión guardada.")}</Notice>}
      {error && <Notice tone="error">{error}</Notice>}
      {loading && !view && <Skeleton label="Cargando episodio…" />}
      {next?.done && (
        <Empty title={tx("No hay episodios disponibles en esta pasada")}>
          {reviewPass === 2
            ? tx("La segunda pasada se abre 48 h después de revisar cada episodio por primera vez.")
            : tx("Has revisado todos los episodios disponibles. Los que faltan llegarán cuando termine la campaña.")}
        </Empty>
      )}

      {view && rubric && (
        <div className="review-grid">
          <section className="panel review-episode" aria-label={tx("Episodio")}>
            <header className="review-episode-head">
              <span className="review-id">{view.sample_id}</span>
              <span className="muted">
                {view.reference_time} · {view.conversation_language}
              </span>
            </header>
            <div className="review-goal">
              <p className="eyebrow">{tx("Usuario simulado")}</p>
              <p>
                <strong>{view.user.goal}</strong>
              </p>
              <p className="muted">{view.user.style}</p>
              <ul>
                {view.user.instructions.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <small className="muted">{view.user.confirm_button}</small>
            </div>
            <div className="review-facts">
              <Facts title={tx("Perfil vigente")} items={view.profile} />
              <Facts title={tx("Citas propias antes")} items={view.agenda.own_appointments_before} />
              <Facts title={tx("Huecos libres antes")} items={view.agenda.free_slots_before} />
              <Facts title={tx("Efectos observados")} items={view.agenda.observed_effects} tone="effects" />
            </div>
            <p className="eyebrow">{tx("Transcripción")}</p>
            <ol className="review-transcript">
              {view.messages.map((message) => {
                const cited = draft.evidence.includes(message.n);
                return (
                  <li key={message.n} className={`msg ${message.role}${cited ? " cited" : ""}`}>
                    <button
                      type="button"
                      className="msg-number"
                      aria-pressed={cited}
                      title={tx("Marcar como evidencia")}
                      onClick={() =>
                        update((value) => ({
                          ...value,
                          evidence: cited
                            ? value.evidence.filter((n) => n !== message.n)
                            : [...value.evidence, message.n].sort((a, b) => a - b),
                        }))
                      }
                    >
                      {message.n}
                    </button>
                    <div>
                      <span className="msg-role">{message.role}</span>
                      <p>{message.text}</p>
                    </div>
                  </li>
                );
              })}
            </ol>
          </section>

          <form
            className="panel review-rubric"
            onSubmit={(event) => {
              event.preventDefault();
              void save();
            }}
            onKeyDown={(event) => {
              const target = event.target as HTMLElement;
              if (target.tagName === "TEXTAREA" || target.tagName === "INPUT") {
                if (event.key === "Enter" && event.ctrlKey) void save();
                return;
              }
              if (event.key === "Enter" && event.ctrlKey) {
                event.preventDefault();
                void save();
              } else if (/^[0-3]$/.test(event.key)) {
                event.preventDefault();
                setScore(active, event.key as Score);
              } else if (event.key.toLowerCase() === "n") {
                event.preventDefault();
                setScore(active, "NA");
              } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                const following = Math.max(0, Math.min(dimensions.length - 1, active + (event.key === "ArrowDown" ? 1 : -1)));
                setActive(following);
                cards.current[following]?.focus();
              }
            }}
          >
            <div className="review-rubric-head">
              <h2>{tx("Rúbrica")}</h2>
              <span className={`review-count${complete ? " done" : ""}`}>
                {filled}/{dimensions.length}
              </span>
            </div>
            {dimensions.map(({ group, key }, index) => {
              const value = draft[group][key];
              const assistant = group === "assistant" ? rubric.assistant[key] : null;
              const simulator = group === "simulator" ? rubric.simulator[key] : null;
              return (
                <fieldset
                  key={`${group}.${key}`}
                  ref={(node) => {
                    cards.current[index] = node;
                  }}
                  tabIndex={0}
                  className={`dimension${index === active ? " active" : ""}${value !== undefined ? " scored" : ""}`}
                  onFocus={() => setActive(index)}
                  onClick={() => setActive(index)}
                >
                  {(index === 0 || dimensions[index - 1].group !== group) && (
                    <p className="dimension-group">{group === "assistant" ? tx("Asistente") : tx("Usuario simulado")}</p>
                  )}
                  <legend>{assistant?.label ?? simulator?.label}</legend>
                  <div className="score-buttons">
                    {SCORES.map((score) => (
                      <button
                        key={score}
                        type="button"
                        tabIndex={-1}
                        aria-pressed={value === score}
                        className={`score score-${score.toLowerCase()}${value === score ? " selected" : ""}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          setScore(index, score);
                        }}
                      >
                        {score}
                      </button>
                    ))}
                  </div>
                  {index === active && assistant && (
                    <ol className="anchors" start={0}>
                      {assistant.anchors.map((anchor, level) => (
                        <li key={level} className={value === String(level) ? "chosen" : ""}>
                          <b>{level}</b> {anchor}
                        </li>
                      ))}
                    </ol>
                  )}
                  {index === active && simulator && (
                    <div className="anchors">
                      <p>
                        <b>✓</b> {simulator.good}
                      </p>
                      <p>
                        <b>✗</b> {simulator.bad}
                      </p>
                    </div>
                  )}
                </fieldset>
              );
            })}
            <label className="review-evidence">
              <span>{tx("Mensajes de evidencia")}</span>
              <small className="muted">{tx("Pulsa el número de un mensaje en la transcripción para citarlo.")}</small>
              <span className="chips">
                {draft.evidence.length ? (
                  draft.evidence.map((n) => <span key={n}>#{n}</span>)
                ) : (
                  <em className="muted">{tx("Ninguno")}</em>
                )}
              </span>
            </label>
            <label className="review-notes">
              <span>{tx("Notas")}</span>
              <textarea
                rows={3}
                value={draft.notes}
                onChange={(event) => update((value) => ({ ...value, notes: event.target.value }))}
              />
            </label>
            <button className="primary full" type="submit" disabled={!complete || saving}>
              {complete ? <CheckCircle2 size={17} /> : <ClipboardCheck size={17} />}
              {complete ? tx("Guardar y siguiente") : `${tx("Faltan")} ${dimensions.length - filled} ${tx("dimensiones")}`}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}

function Facts({ title, items, tone }: { title: string; items: string[]; tone?: string }) {
  return (
    <div className={`facts${tone ? ` facts-${tone}` : ""}`}>
      <p className="facts-title">{title}</p>
      {items.length ? (
        <ul>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">—</p>
      )}
    </div>
  );
}
