import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { dateTime, roleLabels, type Call } from "../../api";
import { Empty, JsonBlock, Notice, Status, Tabs } from "../../components";
import { getUiLanguage, tx } from "../../i18n";
import { callElapsedMs, useElapsedClock } from "../../shared/hooks/useElapsedClock";

type ExecutionTrace = Record<string, unknown>;

export function CallInspector({
  calls,
  executionTrace = [],
}: {
  calls: Call[];
  executionTrace?: ExecutionTrace[];
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState("prompt");
  const now = useElapsedClock(calls.some((item) => item.status === "running"));
  const call = calls.find((item) => item.id === selected);
  const shownTab = call?.diagnostic_redacted ? "effective" : tab;
  const effectiveUse = call
    ? executionTrace.filter((item) => item.component === call.agent)
    : [];
  return (
    <div className="call-inspector">
      {!calls.length ? (
        <Empty title="Todavía no hay llamadas">
          Los controles locales pueden resolver o bloquear una petición sin
          consultar al modelo.
        </Empty>
      ) : (
        <ol className="call-list">
          {calls.map((item, index) => (
            <li key={item.id}>
              <button
                className={selected === item.id ? "selected" : ""}
                onClick={() =>
                  setSelected(selected === item.id ? null : item.id)
                }
                aria-expanded={selected === item.id}
              >
                <span className="call-number">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span>
                  <strong>{tx(roleLabels[item.agent] || item.agent)}</strong>
                  <small>{item.prompt_version}</small>
                </span>
                <span className="call-meta">
                  <Status value={item.status} />
                  <small>
                    {item.latency_ms == null
                      ? item.status === "running"
                        ? `${tx("En curso")} · ${callElapsedMs(item, now) == null ? tx("Latencia n/d") : `${(callElapsedMs(item, now)! / 1000).toFixed(1)} s`}`
                        : ""
                      : `${item.latency_ms} ms`}
                    {item.total_tokens != null
                      ? `${item.latency_ms != null ? " · " : ""}${item.total_tokens} tokens`
                      : item.http_status
                        ? ` · HTTP ${item.http_status}`
                        : ""}
                  </small>
                </span>
                <ChevronRight size={16} />
              </button>
            </li>
          ))}
        </ol>
      )}
      {call && (
        <section className="call-detail">
          <div className="section-heading">
            <h3>{tx(roleLabels[call.agent])} · {tx("detalle de llamada")}</h3>
            <code>{call.provider}</code>
          </div>
          <p className="muted">
            {call.model} · {dateTime(call.started_at)}
          </p>
          <dl className="call-facts" aria-label="Datos de la llamada">
            {call.http_status != null && (
              <div>
                <dt>Respuesta HTTP</dt>
                <dd>{call.http_status}</dd>
              </div>
            )}
            {call.attempt_index != null && (
              <div>
                <dt>Intento</dt>
                <dd>
                  {call.attempt_index}
                  {call.max_attempts != null && ` / ${call.max_attempts}`}
                </dd>
              </div>
            )}
            {call.latency_ms != null && (
              <div>
                <dt>Latencia</dt>
                <dd>{call.latency_ms} ms</dd>
              </div>
            )}
            {retryDelay(call) != null && (
              <div>
                <dt>Siguiente intento</dt>
                <dd>{`${tx("tras")} ${retryDelay(call)!.toLocaleString(locale(), { maximumFractionDigits: 1 })} s`}</dd>
              </div>
            )}
            {call.reasoning_effort && (
              <div>
                <dt>Razonamiento configurado</dt>
                <dd>{call.reasoning_effort}</dd>
              </div>
            )}
            {call.request_timeout_seconds != null && (
              <div>
                <dt>Timeout de red</dt>
                <dd>{call.request_timeout_seconds} s</dd>
              </div>
            )}
            {call.thinking_tokens != null && (
              <div>
                <dt>Tokens de razonamiento</dt>
                <dd>{formatTokens(call.thinking_tokens)}</dd>
              </div>
            )}
            {call.provider_http_attempts != null && (
              <div>
                <dt>Intentos HTTP observados</dt>
                <dd>{call.provider_http_attempts}</dd>
              </div>
            )}
            {call.transport_timeout_kind && (
              <div>
                <dt>Fase del timeout</dt>
                <dd>{tx({connect: "Conexión", read: "Lectura de respuesta",
                  write: "Envío de solicitud", pool: "Espera de conexión disponible",
                  unknown: "No determinada"}[call.transport_timeout_kind])}</dd>
              </div>
            )}
            {call.sdk_version && (
              <div>
                <dt>SDK</dt>
                <dd>{call.sdk_version}{call.api_interface ? ` · ${call.api_interface}` : ""}</dd>
              </div>
            )}
          </dl>
          {(call.http_status === 429 || call.error_code?.startsWith("provider-quota")) && (
            <Notice>
              <p key="model-limit">{tx("Límite del proveedor:")} {call.model} · {limitScope(call)}</p>
              <p key="explanation">{call.error_code === "provider-quota-unavailable"
                ? tx("El proveedor comunica una cuota de cero para este modelo. Revise la configuración; no se cambiará de modelo automáticamente.")
                : ["RPM", "TPM", "ITPM", "OTPM"].includes(call.rate_limit_scope || "") || (!call.rate_limit_scope && call.quota_kind === "rate-limit")
                  ? tx("Límite por minuto: no significa por sí solo que la cuota diaria esté agotada.")
                  : ["RPD", "TPD"].includes(call.rate_limit_scope || "") || call.quota_kind === "daily"
                    ? tx("Límite diario: no se harán reintentos automáticos.")
                    : tx("Alcance desconocido: no se puede asegurar que sea un límite diario. Compruebe las cuotas antes de reintentar.")}</p>
              {call.provider_request_sent === false && <p key="not-sent">{tx("Bloqueada localmente: esta llamada no se envió al proveedor.")}</p>}
              {call.retry_after_seconds != null && <p key="wait">{tx("Espera registrada (segundos):")} {Math.ceil(call.retry_after_seconds)}</p>}
            </Notice>
          )}
          {call.terminal_error && (
            <Notice>
              {tx("Último intento sin éxito:")} <code>{call.terminal_error}</code>
            </Notice>
          )}
          {call.input_tokens != null || call.output_tokens != null || call.total_tokens != null ? (
            <dl className="call-token-breakdown" aria-label="Consumo de tokens">
              <div>
                <dt>Entrada</dt>
                <dd>{formatTokens(call.input_tokens)}</dd>
              </div>
              {call.cached_input_tokens != null && (
                <div>
                  <dt>Entrada cacheada</dt>
                  <dd>{formatTokens(call.cached_input_tokens)}</dd>
                </div>
              )}
              {call.uncached_input_tokens != null && (
                <div>
                  <dt>Entrada no cacheada</dt>
                  <dd>{formatTokens(call.uncached_input_tokens)}</dd>
                </div>
              )}
              <div>
                <dt>Salida</dt>
                <dd>{formatTokens(call.output_tokens)}</dd>
              </div>
              <div>
                <dt>Total</dt>
                <dd>{formatTokens(call.total_tokens)}</dd>
              </div>
              {call.provider === "groq" && call.quota_estimated_tokens != null && (
                <div>
                  <dt>Estimación de cuota Groq</dt>
                  <dd>{formatTokens(call.quota_estimated_tokens)}</dd>
                </div>
              )}
            </dl>
          ) : (
            <p className="muted">
              {call.status === "error"
                ? "El proveedor no devolvió consumo de tokens porque la llamada no tuvo éxito."
                : "El proveedor no comunicó el consumo de tokens de esta llamada."}
            </p>
          )}
          {call.status === "success" && (
            <p className="muted">
              Correcta significa que el proveedor respondió y que la salida
              cumple el contrato. Los controles del sistema deciden después si
              se usa.
            </p>
          )}
          {call.diagnostic_redacted && (
            <Notice>
              Esta conversación no guarda el contenido de las llamadas (prompt,
              entrada, salida y contrato) porque se creó sin la opción «Capturar
              diagnóstico de entradas y salidas». Las métricas sí se conservan.
            </Notice>
          )}
          {(call.prefix_sha256 || call.contract_sha256) && (
            <details>
              <summary>Identidad del prefijo y contrato enviados</summary>
              <p>Prefijo: <code>{call.prefix_sha256 || "No registrado"}</code></p>
              <p>Contrato: <code>{call.contract_sha256 || "No registrado"}</code></p>
              <p className="muted">La coincidencia de huellas no garantiza un acierto de caché.</p>
            </details>
          )}
          {!(call.diagnostic_redacted && !effectiveUse.length) && (
          <Tabs
            label="Contenido de la llamada"
            value={shownTab}
            onChange={setTab}
            items={call.diagnostic_redacted
              ? [{ value: "effective", label: tx("Uso efectivo") }]
              : [
                { value: "prompt", label: tx("Prompt efectivo") },
                { value: "input", label: tx("Entrada") },
                { value: "output", label: tx("Salida") },
                { value: "effective", label: tx("Uso efectivo") },
                { value: "schema", label: tx("Contrato") },
              ]}
          >
            {shownTab === "prompt" && (
              <>
                <pre className="prompt" tabIndex={0}>
                  {call.system_prompt}
                </pre>
                <p className="hash">SHA-256 · {call.prompt_hash}</p>
              </>
            )}
            {shownTab === "input" &&
              (call.input === undefined ? (
                <Notice>
                  Contenido no capturado o eliminado por retención. Los
                  metadatos y la plantilla siguen disponibles.
                </Notice>
              ) : (
                <JsonBlock
                  data={call.input}
                  label={`${tx("Entrada de ")}${tx(roleLabels[call.agent] || call.agent)}`}
                />
              ))}
            {shownTab === "output" &&
              (call.output === undefined ? (
                <Notice>
                  {call.error_type
                    ? `${tx("Error técnico:")} ${call.error_type}. ${tx("No se conserva la respuesta bruta del proveedor.")}`
                    : "Salida estructurada no capturada o eliminada. Nunca se registra razonamiento interno."}
                </Notice>
              ) : (
                <JsonBlock
                  data={call.output}
                  label={`${tx("Salida de ")}${tx(roleLabels[call.agent] || call.agent)}`}
                />
              ))}
            {shownTab === "schema" && (
              <JsonBlock
                data={call.schema}
                label={`${tx("Contrato de ")}${tx(roleLabels[call.agent] || call.agent)}`}
              />
            )}
            {shownTab === "effective" &&
              (effectiveUse.length ? (
                <JsonBlock
                  data={effectiveUse}
                  label={`${tx("Transformación y uso de ")}${tx(roleLabels[call.agent] || call.agent)}`}
                />
              ) : (
                <Notice>
                  Este turno no conserva un delta capturado para esta llamada.
                  No se reconstruye retrospectivamente como si fuera evidencia.
                </Notice>
              ))}
          </Tabs>
          )}
        </section>
      )}
    </div>
  );
}

function locale(): string {
  return getUiLanguage() === "en" ? "en-GB" : "es-ES";
}

function formatTokens(value: number | null | undefined): string {
  return value == null ? tx("n/d") : value.toLocaleString(locale());
}

// El cliente registra `retry_delay_seconds`; `retry_wait_seconds` procede de trazas anteriores.
function retryDelay(call: Call): number | null {
  if (call.status === "success" || call.retry_scheduled === false) return null;
  return call.retry_delay_seconds ?? call.retry_wait_seconds ?? null;
}

function limitScope(call: Call): string {
  if (call.rate_limit_scope) return call.rate_limit_scope;
  if (call.quota_kind === "rate-limit") return tx("límite de ritmo");
  if (call.quota_kind === "daily") return tx("cuota diaria");
  return tx("Dimensión no determinada");
}
