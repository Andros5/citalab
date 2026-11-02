import { formatDate, getUiLanguage, localeTag, tx } from "./i18n";

export type User = {
  username: string;
  display_name: string;
  role: "admin" | "researcher" | "patient";
  subject_id: string | null;
};
export type Patient = { id: string; name: string; version: number };
export type PortalConfig = {
  default_architecture: string;
  default_provider: string;
  remote_enabled: boolean;
  max_calls: number;
  timeout_seconds: number;
  recovery_policy_version?: "single-attempt-v1" | "bounded-transient-v1" | "bounded-transient-v2";
  temperature: number;
  max_output_tokens: number;
  daily_call_limit: number;
  retention_days: number;
  diagnostic_days: number;
  session_minutes: number;
};
export type Bootstrap = {
  catalog?: Catalog;
  user: User;
  patients: Patient[];
  config: { version: number; config: PortalConfig };
  providers: Record<string, boolean>;
  models: Record<string, string>;
  fixed_controls: Record<string, unknown>;
};
export type Call = {
  id: string;
  agent: string;
  status: string;
  started_at: string;
  finished_at?: string;
  latency_ms?: number;
  input_tokens?: number;
  cached_input_tokens?: number | null;
  uncached_input_tokens?: number | null;
  output_tokens?: number;
  total_tokens?: number;
    quota_estimated_tokens?: number | null;
    prefix_sha256?: string | null;
    contract_sha256?: string | null;
  prompt_version: string;
  prompt_hash: string;
  system_prompt: string;
  input?: unknown;
  output?: unknown;
  schema: unknown;
  model: string;
  provider: string;
  error_type?: string;
  error_code?: string | null;
  http_status?: number | null;
  rate_limit_scope?: string | null;
  retry_after_seconds?: number | null;
  provider_request_sent?: boolean | null;
  provider_http_attempts?: number | null;
  reasoning_effort?: string | null;
  request_timeout_seconds?: number | null;
  transport_timeout_kind?: "connect" | "read" | "write" | "pool" | "unknown" | null;
  thinking_tokens?: number | null;
  logical_inference_id?: string | null;
  attempt_index?: number | null;
  max_attempts?: number | null;
  recovery_policy_version?: string | null;
  retry_scheduled?: boolean;
  retry_delay_seconds?: number;
  next_attempt_index?: number;
  retry_wait_seconds?: number;
  sdk_version?: string | null;
  api_interface?: string | null;
  provider_request_id?: string | null;
  quota_kind?: "rate-limit" | "daily" | null;
  terminal_error?: string | null;
  diagnostic_redacted?: boolean;
};
export type ExecutionSummary = {
  schema_version: "execution-summary-v1";
  inference_outcome: string;
  programmed_recovery: boolean;
  transport_recovered: boolean;
  provider_attempts: number;
  provider_attempts_complete: boolean;
};
export type Turn = {
  execution_summary?: ExecutionSummary;
  job_id?: string;
  response_language?: string | null;
  response_metadata?: {
    version: string;
    components: string[];
    validation: string;
    repair_count: number;
    recovery: boolean;
  };
  scenario?: Scenario;
  events?: { at: string; kind: string; detail: string }[];
  source_sha256?: string;
  data_before_sha256?: string;
  data_after_sha256?: string;
  id: string;
  number: number;
  request: string;
  response: string;
  status: string;
  at: string;
  calls?: Call[];
  state?: Record<string, unknown>;
};
export type Offer = {
  id?: string;
  start: string;
  end: string;
  service_display: string;
  modality_display: string;
  location_display: string;
};
export type AppointmentSummary = {
  id: string;
  status: string;
  service_code: string;
  service_display: string;
  start: string;
  end: string;
  version?: string;
  slot_id?: string;
};
export type OperationProposal = {
  proposal_id: string;
  revision: number;
  operation: "cancel" | "reschedule" | "reminder";
  subject_id: string;
  appointment_id: string;
  target_id?: string | null;
  expires_at: string;
  appointment: AppointmentSummary;
  target_offer?: Offer & { slot_version?: string };
  arguments?: { channel?: string; minutes_before?: number };
};
export type OperationReceipt = {
  status: string;
  operation: "book" | "cancel" | "reschedule" | "reminder";
  idempotency_key: string;
  result_id?: string;
};
export type Conversation = {
  welcome?: { kind: "initial_notice"; version: number; text: string } | null;
  ui_language?: "es" | "en";
  initial_response_language?: "es" | "en" | null;
  initial_response_language_source?: string;
  dialogue_state?: {
    pending_question?: { purpose: string; expected_information: string; text: string } | null;
    active_task_ids?: string[];
    constraints?: Record<string, unknown>;
    proposal_binding?: Record<string, unknown>;
    public_exchanges?: { user: string; assistant: string }[];
  };
  read_only?: boolean;
  failed_attempts?: Job[];
  provenance?: Record<string, unknown>;
  id: string;
  owner: string;
  subject_id: string;
  subject_name: string;
  title: string;
  status: string;
  architecture: string;
  provider: string;
  diagnostic: boolean;
  created_at: string;
  updated_at: string;
  turn_count: number;
  turns: Turn[];
  calls?: Call[];
  offer?: Offer;
  operation_proposal?: OperationProposal;
  appointment_results?: AppointmentSummary[];
  operation_receipt?: OperationReceipt;
  can_confirm: boolean;
  active_job: string | null;
  archived: boolean;
  total_known_tokens?: number;
  tokens_complete?: boolean;
  groq_cached_input_tokens?: number;
  groq_cache_measurement_complete?: boolean;
  groq_cache_hit_rate?: number | null;
  groq_quota_estimated_tokens?: number;
  groq_quota_estimate_complete?: boolean;
  config_version?: number;
  preferences?: ConversationPreferences;
  preference_update?: {
    scope: "turn" | "conversation" | "profile";
    persisted_to_profile: false;
    proposal_invalidated: boolean;
  };
  preference_proposal?: PreferenceProposal | null;
  profile_usage_enabled?: boolean;
};
export type ConversationPreferences = {
  schema_version: number;
  values: Record<string, string>;
  pending_turn_values?: Record<string, string>;
  effective?: Record<string, string>;
  sources: Record<string, string>;
  scope: "conversation" | "turn";
  revision: number;
  profile_opt_out: boolean;
};
export type PreferenceProposal = {
  proposal_id: string;
  subject_id: string;
  profile_version: number;
  expected_turn: number;
  values: Record<string, string>;
  profile_usage_enabled?: boolean | null;
  status: "pending" | "confirmed" | "rejected";
  stale: boolean;
};
export type Job = {
  execution_summary?: ExecutionSummary;
  id: string;
  conversation_id: string;
  status: string;
  calls?: Call[];
  events?: { at: string; kind: string; detail: string }[];
  error?: string;
  result_status?: string;
  rows?: Record<string, unknown>[];
  total?: number;
  suite?: string;
  variants?: string[];
  utility_scope?: "quick" | "full";
  call_budget?: number;
  pause_reason?: string;
  at: string;
  summary?: unknown;
};
export type Resource = {
  id: string;
  resourceType: string;
  status?: string;
  start?: string;
  end?: string;
  name?: unknown;
  schedule?: { reference: string };
  meta?: { versionId?: string };
  participant?: { actor: { reference: string } }[];
  [key: string]: unknown;
};
export type Resources = Record<string, Record<string, Resource>>;
export type Scenario = {
  id: string;
  version: string;
  sha256: string;
  require_explicit_service: boolean;
};
export type Catalog = {
  scenario: Scenario;
  services: { code: string; label: string }[];
  schedules: {
    id: string;
    label: string;
    service_code: string;
    modality_code: string;
    modality_label?: string;
    active: boolean;
  }[];
  availability?: { free_slots: number; future_free_slots: number };
};

let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public kind: "http" | "network" | "timeout" | "contract" = "http",
  ) {
    super(apiMessage(message));
  }
}

function apiMessage(message: string): string {
  const translated = tx(message);
  if (translated !== message) return translated;
  // Server-side validation details are currently Spanish. Do not leak mixed
  // language UI: unknown details use a localized, non-misleading fallback.
  if (getUiLanguage() === "en") return "The request could not be completed. Check the form and try again.";
  return message;
}

/**
 * Única frontera HTTP del frontend. Cada petición tiene timeout y cancelación
 * enlazada a su consumidor; las mutaciones no se reintentan automáticamente.
 */
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
  options: { signal?: AbortSignal; timeoutMs?: number } = {},
): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const abort = () => controller.abort();
  options.signal?.addEventListener("abort", abort, { once: true });
  if (options.signal?.aborted) controller.abort();
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, options.timeoutMs ?? 20000);
  try {
    const response = await fetch(`/api${path}`, {
      method,
      signal: controller.signal,
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "CitaLab",
        "X-CSRF-Token": csrf,
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    let data: unknown;
    try {
      data = response.status === 204 ? undefined : await response.json();
    } catch {
      if (response.ok)
        throw new ApiError(
          "La respuesta del servidor no tiene un formato válido.",
          response.status,
          "contract",
        );
      data = {};
    }
    if (!response.ok) {
      if (response.status === 401 && path !== "/auth/login")
        window.dispatchEvent(new Event("session-expired"));
      throw new ApiError(
        data &&
          typeof data === "object" &&
          "detail" in data &&
          typeof data.detail === "string"
          ? data.detail
          : "No se ha podido completar la operación.",
        response.status,
      );
    }
    return data as T;
  } catch (error) {
    if (options.signal?.aborted)
      throw new DOMException("Petición cancelada", "AbortError");
    if (timedOut)
      throw new ApiError(
        "El servidor tarda en responder. Consulta el estado antes de repetir una operación.",
        0,
        "timeout",
      );
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      "No se pudo conectar con CitaLab. Comprueba que el servidor sigue abierto.",
      0,
      "network",
    );
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", abort);
  }
}
export function downloadJSON(data: unknown, name: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}
export const roleLabels: Record<string, string> = {
  context: "Contexto",
  profile: "Perfiles",
  compliance: "Cumplimiento",
  personalization: "Personalización",
  orchestration: "Orquestación",
  single: "Agente único",
};
export const statusLabels: Record<string, string> = {
  READY: "Lista para empezar",
  NEEDS_CONFIRMATION: "Pendiente de confirmar",
  COMPLETED: "Gestión completada",
  NEEDS_CLARIFICATION: "Necesita aclaración",
  BLOCKED: "Operación bloqueada",
  FAILED: "Fallida",
  ESCALATED: "Atención humana",
  DISCARDED: "Propuesta descartada",
  RESTORED_DATA: "Datos restaurados",
  SCENARIO_UPDATED: "Escenario actualizado: revisar petición",
  completed: "Finalizada",
  failed: "Fallida",
  queued: "En cola",
  running: "En ejecución",
  pause_requested: "Pausa solicitada",
  paused: "Pausada",
  cancel_requested: "Cancelación solicitada",
  cancelled: "Cancelada",
  interrupted: "Interrumpida",
  success: "Correcta",
  error: "Error",
  degraded: "Con incidencias",
  recovered: "Recuperada tras reintento",
  booked: "Reservada",
  free: "Disponible",
  busy: "Reservado",
  "busy-unavailable": "No disponible",
};
export const dateTime = (value?: string) =>
  value && Number.isFinite(Date.parse(value))
    ? new Intl.DateTimeFormat(localeTag(), {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "Europe/Madrid",
      }).format(new Date(value))
    : "—";

/** Día civil de la agenda, independiente de la zona del navegador o del ISO. */
export function agendaDate(value: string): string {
  if (!Number.isFinite(Date.parse(value))) return "";
  const parts = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: "Europe/Madrid",
  }).formatToParts(new Date(value));
  const part = (type: string) =>
    parts.find((item) => item.type === type)!.value;
  return `${part("year")}-${part("month")}-${part("day")}`;
}

/** Localized display form; agendaDate remains the stable ISO key for filtering. */
export function agendaDateLabel(value: string): string {
  if (!Number.isFinite(Date.parse(value))) return "";
  return formatDate(new Date(value), {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
