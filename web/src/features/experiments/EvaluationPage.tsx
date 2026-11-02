import { EyeOff } from "lucide-react";
import { useEffect, useState } from "react";
import { downloadJSON } from "../../api";
import { Empty, ErrorState, Field, PageHeader, Skeleton, Tabs } from "../../components";
import { tx } from "../../i18n";
import { useResource } from "../../shared/hooks/useResource";
import { BlindReview, useReviewStatus } from "./BlindReview";
import "./evaluation.css";

type Campaign = { id: string; episodes: number; manifest: Record<string, unknown> };
type Row = {
  provider: string;
  architecture: string;
  episodes: number;
  incidents: number;
  success: number | null;
  success_ci: [number, number];
  goal: number | null;
  safety: number | null;
  preference: number | null;
  calls: number | null;
  tokens: number | null;
  llm_latency_s: number | null;
  fallbacks_per_episode: number | null;
  by_operation: Record<string, number | null>;
};
type Contrast = { n_units?: number; diff?: number; ci_low?: number; ci_high?: number; p_value?: number; p_holm?: number };
type Episode = {
  cell_id: string;
  provider: string;
  architecture: string;
  unit_id: string;
  operation: string;
  block: string;
  status: string;
  success: boolean | null;
  user_turns?: number;
  assistant_calls?: number;
  fallback_count?: number;
  end_reason?: string;
};
type CampaignDetail = {
  id: string;
  summary: { table: Row[]; contrasts: Record<string, Record<string, Contrast>>; episodes: number; completed: number };
  episodes: Episode[];
};

const pct = (value: number | null | undefined) =>
  value === null || value === undefined ? "—" : `${Math.round(value * 100)} %`;
const num = (value: number | null | undefined, digits = 1) =>
  value === null || value === undefined ? "—" : value.toFixed(digits);


// La campaña final es la que se informa en la memoria. Cualquier otra ejecución
// local se muestra aparte y no se abre por defecto.
function campaignKind(id: string): "final" | "pilot" | "smoke" {
  if (id.startsWith("final")) return "final";
  if (id.startsWith("smoke")) return "smoke";
  return "pilot";
}

export function EvaluationPage() {
  const campaigns = useResource<Campaign[]>("/evaluation/campaigns");
  const [selected, setSelected] = useState("");
  const [tab, setTab] = useState("results");
  useEffect(() => {
    if (selected || !campaigns.data?.length) return;
    const finals = campaigns.data.filter((item) => campaignKind(item.id) === "final");
    setSelected((finals.length ? finals : campaigns.data)[(finals.length ? finals : campaigns.data).length - 1].id);
  }, [campaigns.data, selected]);
  const groups = [
    { kind: "final", label: tx("Campaña final") },
    { kind: "pilot", label: tx("Pilotos de desarrollo") },
    { kind: "smoke", label: tx("Pruebas de humo") },
  ] as const;
  return (
    <div className="evaluation-page">
      <PageHeader
        eyebrow="LABORATORIO / EVALUACIÓN"
        title="Evaluación"
        description="Resultados del oráculo por configuración, episodios y revisión humana ciega de la muestra fijada."
      />
      {campaigns.loading && <Skeleton label="Cargando campañas…" />}
      {campaigns.error && <ErrorState message={campaigns.error} retry={campaigns.retry} />}
      {campaigns.data && !campaigns.data.length && (
        <Empty title="Sin campañas">
          Ejecuta una campaña con python -m citalab.evaluation.runner para ver aquí sus resultados.
        </Empty>
      )}
      {!!campaigns.data?.length && (
        <>
          <div className="campaign-picker">
            <Field label="Campaña">
              <select value={selected} onChange={(e) => setSelected(e.target.value)}>
                {groups.map(({ kind, label }) => {
                  const items = campaigns.data!.filter((item) => campaignKind(item.id) === kind);
                  return items.length ? (
                    <optgroup key={kind} label={label}>
                      {items.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.id} · {item.episodes} {tx("episodios")}
                        </option>
                      ))}
                    </optgroup>
                  ) : null;
                })}
              </select>
            </Field>
            {selected && (
              <span className={`campaign-kind campaign-kind-${campaignKind(selected)}`}>
                {groups.find((group) => group.kind === campaignKind(selected))?.label}
              </span>
            )}
          </div>
          <Tabs
            label="Secciones de evaluación"
            value={tab}
            onChange={setTab}
            items={[
              { value: "results", label: "Resultados" },
              { value: "episodes", label: "Episodios" },
              { value: "review", label: "Revisión humana ciega" },
            ]}
          >
            {selected && tab === "results" && <Results campaign={selected} />}
            {selected && tab === "episodes" && <BlindingGate campaign={selected} onReview={() => setTab("review")} />}
            {selected && tab === "review" && <BlindReview campaign={selected} />}
          </Tabs>
        </>
      )}
    </div>
  );
}

// Episodios muestra arquitectura, proveedor y veredicto del oráculo junto a la
// transcripción. Mientras la primera pasada de la revisión ciega siga abierta para
// esta campaña, verlos podría desvelar episodios de la muestra: se pide confirmación.
function BlindingGate({ campaign, onReview }: { campaign: string; onReview: () => void }) {
  const { status } = useReviewStatus();
  const [reveal, setReveal] = useState(false);
  const pass = status?.campaign === campaign ? status.progress["1"] : null;
  if (reveal || !pass || pass.done >= pass.total) return <Episodes campaign={campaign} />;
  return (
    <section className="panel blinding-gate">
      <EyeOff size={28} aria-hidden />
      <h2>{tx("Episodios ocultos durante la revisión ciega")}</h2>
      <p>
        {tx("Llevas")} {pass.done}/{pass.total}{" "}
        {tx(
          "episodios de la primera pasada. Esta vista muestra arquitectura, proveedor y el veredicto del oráculo, y podría desvelarte episodios de la muestra antes de puntuarlos.",
        )}
      </p>
      <div className="actions">
        <button type="button" className="primary" onClick={onReview}>
          {tx("Seguir con la revisión")}
        </button>
        <button type="button" onClick={() => setReveal(true)}>
          {tx("Mostrar episodios igualmente")}
        </button>
      </div>
    </section>
  );
}

function Results({ campaign }: { campaign: string }) {
  const detail = useResource<CampaignDetail>(`/evaluation/campaigns/${encodeURIComponent(campaign)}`);
  if (detail.loading) return <Skeleton label="Calculando resultados…" />;
  if (detail.error || !detail.data) return <ErrorState message={detail.error} retry={detail.retry} />;
  const { summary } = detail.data;
  const incidents = summary.table.reduce((total, row) => total + row.incidents, 0);
  const pooled = summary.table.filter((row) => row.success !== null);
  const meanSuccess = pooled.length
    ? pooled.reduce((total, row) => total + (row.success ?? 0) * row.episodes, 0) /
      pooled.reduce((total, row) => total + row.episodes, 0)
    : null;
  return (
    <div className="evaluation-grid">
      <div className="kpi-row">
        <div className="kpi">
          <span>{tx("Episodios completados")}</span>
          <strong>
            {summary.completed}
            <small>/{summary.episodes}</small>
          </strong>
          <div className="bar">
            <span style={{ width: `${summary.episodes ? (summary.completed / summary.episodes) * 100 : 0}%` }} />
          </div>
        </div>
        <div className="kpi">
          <span>{tx("Éxito integral medio")}</span>
          <strong>{pct(meanSuccess)}</strong>
          <small className="muted">{tx("Ponderado por episodios")}</small>
        </div>
        <div className="kpi">
          <span>{tx("Configuraciones")}</span>
          <strong>{summary.table.length}</strong>
          <small className="muted">{tx("Proveedor × arquitectura")}</small>
        </div>
        <div className={`kpi${incidents ? " kpi-warn" : ""}`}>
          <span>{tx("Incidentes")}</span>
          <strong>{incidents}</strong>
          <small className="muted">{tx("No cuentan como fallo")}</small>
        </div>
      </div>
      <section className="panel">
        <div className="section-heading">
          <h2>Éxito integral por configuración</h2>
          <span className="legend">
            <i className="legend-bar" /> {tx("Éxito")} <i className="legend-ci" /> IC95 %
          </span>
        </div>
        <div className="success-chart" role="list">
          {summary.table.map((row) => (
            <div className="success-row" role="listitem" key={`${row.provider}-${row.architecture}`}>
              <span className="success-label">
                <strong>{row.architecture}</strong> <small>{row.provider}</small>
              </span>
              <span className="success-track" aria-hidden>
                <span className={`success-fill arch-${row.architecture.toLowerCase()}`} style={{ width: `${(row.success ?? 0) * 100}%` }} />
                {row.success_ci && (
                  <span
                    className="success-ci"
                    style={{ left: `${row.success_ci[0] * 100}%`, width: `${(row.success_ci[1] - row.success_ci[0]) * 100}%` }}
                  />
                )}
              </span>
              <span className="success-value">
                {pct(row.success)} <small>n={row.episodes}</small>
              </span>
            </div>
          ))}
        </div>
      </section>
      <section className="panel">
        <div className="section-heading">
          <h2>Resultados por configuración</h2>
          <button type="button" onClick={() => downloadJSON(detail.data, `${campaign}-resumen.json`)}>
            Exportar JSON
          </button>
        </div>
        <p className="muted">
          {summary.completed} / {summary.episodes} {tx("episodios completados")}. {tx(
            "Éxito integral = objetivo alcanzado, controles respetados y respuestas fieles.",
          )}
        </p>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Proveedor</th>
                <th>Arquitectura</th>
                <th>N</th>
                <th>Éxito (IC95 %)</th>
                <th>Objetivo</th>
                <th>Seguridad</th>
                <th>Preferencia</th>
                <th>Llamadas</th>
                <th>Tokens</th>
                <th>Latencia (s)</th>
                <th>Incidentes</th>
              </tr>
            </thead>
            <tbody>
              {summary.table.map((row) => (
                <tr key={`${row.provider}-${row.architecture}`}>
                  <td>{row.provider}</td>
                  <td>
                    <strong>{row.architecture}</strong>
                  </td>
                  <td>{row.episodes}</td>
                  <td>
                    {pct(row.success)}{" "}
                    <small>
                      ({pct(row.success_ci?.[0])}–{pct(row.success_ci?.[1])})
                    </small>
                  </td>
                  <td>{pct(row.goal)}</td>
                  <td>{pct(row.safety)}</td>
                  <td>{pct(row.preference)}</td>
                  <td>{num(row.calls)}</td>
                  <td>{num(row.tokens, 0)}</td>
                  <td>{num(row.llm_latency_s)}</td>
                  <td>{row.incidents}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="panel">
        <h2>Contrastes pareados</h2>
        <p className="muted">
          Diferencia de éxito emparejada por familia, intervalo bootstrap del 95 % y corrección de Holm.
        </p>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Proveedor</th>
                <th>Contraste</th>
                <th>Unidades</th>
                <th>Diferencia</th>
                <th>IC95 %</th>
                <th>p Holm</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(summary.contrasts).flatMap(([provider, tests]) =>
                Object.entries(tests)
                  .filter(([, t]) => t.n_units)
                  .map(([key, t]) => (
                    <tr key={`${provider}-${key}`}>
                      <td>{provider}</td>
                      <td>{key}</td>
                      <td>{t.n_units}</td>
                      <td>{num((t.diff ?? 0) * 100)} pp</td>
                      <td>
                        [{num((t.ci_low ?? 0) * 100)}, {num((t.ci_high ?? 0) * 100)}]
                      </td>
                      <td>{num(t.p_holm, 3)}</td>
                    </tr>
                  )),
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Episodes({ campaign }: { campaign: string }) {
  const detail = useResource<CampaignDetail>(`/evaluation/campaigns/${encodeURIComponent(campaign)}`);
  const [filter, setFilter] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const episode = useResource<Record<string, unknown>>(
    open ? `/evaluation/campaigns/${encodeURIComponent(campaign)}/episodes/${encodeURIComponent(open)}` : null,
  );
  if (detail.loading) return <Skeleton label="Cargando episodios…" />;
  if (detail.error || !detail.data) return <ErrorState message={detail.error} retry={detail.retry} />;
  const rows = detail.data.episodes.filter((item) => item.cell_id.includes(filter));
  const transcript = (episode.data?.transcript as { role: string; text: string }[] | undefined) || [];
  const checks = (episode.data?.checks as Record<string, { pass: boolean; reason: string }> | undefined) || {};
  return (
    <div className="evaluation-grid two">
      <section className="panel">
        <Field label="Filtrar episodios">
          <input placeholder="groq:M5:B01…" value={filter} onChange={(e) => setFilter(e.target.value)} />
        </Field>
        <div className="table-scroll episode-list">
          <table>
            <thead>
              <tr>
                <th>Celda</th>
                <th>Resultado</th>
                <th>Turnos</th>
                <th>Llamadas</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((item) => (
                <tr
                  key={item.cell_id}
                  className={open === item.cell_id ? "selected" : ""}
                  onClick={() => setOpen(item.cell_id)}
                >
                  <td>
                    <button type="button" className="link" onClick={() => setOpen(item.cell_id)}>
                      {item.cell_id}
                    </button>
                  </td>
                  <td>
                    {item.status !== "completed" ? (
                      <span className="badge warn">{tx("Incidente")}</span>
                    ) : item.success ? (
                      <span className="badge ok">{tx("Éxito")}</span>
                    ) : (
                      <span className="badge bad">{tx("Fallo")}</span>
                    )}
                  </td>
                  <td>{item.user_turns ?? "—"}</td>
                  <td>{item.assistant_calls ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="panel">
        {!open && <Empty title="Selecciona un episodio">Verás la conversación y las comprobaciones del oráculo.</Empty>}
        {open && episode.loading && <Skeleton label="Cargando episodio…" />}
        {open && episode.data && (
          <>
            <h2>{open}</h2>
            <ul className="check-list">
              {Object.entries(checks).map(([key, value]) => (
                <li key={key} className={value.pass ? "ok" : "bad"}>
                  <strong>{key}</strong>: {value.reason}
                </li>
              ))}
            </ul>
            <div className="transcript">
              {transcript.map((item, index) => (
                <p key={index} className={`bubble ${item.role}`}>
                  <span>{item.role === "user" ? tx("Usuario simulado") : tx("Asistente")}</span>
                  {item.text}
                </p>
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
