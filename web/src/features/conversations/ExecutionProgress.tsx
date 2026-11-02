import { roleLabels, type Call, type Job } from "../../api";
import { Status } from "../../components";
import { tx } from "../../i18n";
import { callElapsedMs, useElapsedClock } from "../../shared/hooks/useElapsedClock";

export function ExecutionProgress({ calls, job }: { calls: Call[]; job: Job | null }) {
  const now = useElapsedClock(true);
  const start = job?.at ? Date.parse(job.at) : NaN;
  const completed = calls.filter((call) => call.status === "success").length;
  const errors = calls.filter((call) => ["error", "fallback"].includes(call.status)).length;
  return (
    <section className="execution-progress" aria-live="off" aria-label={tx("Progreso de las llamadas")}>
      <p>
        {tx("Completadas:")} {completed} · {tx("Fallidas:")} {errors}
        {Number.isFinite(start) && <> · {tx("Tiempo transcurrido:")} {(Math.max(0, now - start) / 1000).toFixed(0)} s</>}
      </p>
      <ol>
        {calls.map((call) => {
          const elapsed = callElapsedMs(call, now);
          return <li key={call.id}>
            <strong>{tx(roleLabels[call.agent] || call.agent)}</strong>
            <Status value={call.status} />
            {call.attempt_index != null && (call.max_attempts ?? 1) > 1 && <small>
              {tx("Intento")} {call.attempt_index}/{call.max_attempts}
            </small>}
            <span>{elapsed == null ? tx("Latencia n/d") : `${(elapsed / 1000).toFixed(1)} s`}</span>
            {call.retry_scheduled && !calls.some(next =>
              next.logical_inference_id === call.logical_inference_id &&
              (next.attempt_index ?? 0) > (call.attempt_index ?? 0)) && <small>
              {tx("Esperando antes de reintentar:")} {(call.retry_delay_seconds ?? 0).toFixed(1)} s
            </small>}
            {call.status === "running" && elapsed !== null && elapsed >= 30000 &&
              <small>{tx("La llamada está tardando; no implica un fallo.")}</small>}
          </li>;
        })}
      </ol>
      <small>{tx("Las llamadas aparecen al iniciarse; el recorrido depende de la petición.")}</small>
      {Number.isFinite(start) && now - start >= 60000 &&
        <small>{tx("Turno prolongado: puede incluir espera de cuota y varias llamadas.")}</small>}
    </section>
  );
}
