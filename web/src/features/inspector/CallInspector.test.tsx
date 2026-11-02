import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import type { Call } from "../../api";
import { CallInspector } from "./CallInspector";

it("muestra parámetros efectivos y tokens de razonamiento numéricos sin cadena interna", () => {
  const call = { id: "effective", agent: "context", status: "success", started_at: "2026-10-13T10:00:00Z",
    model: "gemini-3.5-flash-lite", provider: "google", prompt_version: "v1", prompt_hash: "hash",
    system_prompt: "synthetic", schema: {}, reasoning_effort: "low", request_timeout_seconds: 60,
    thinking_tokens: 0, provider_http_attempts: 1 } as Call;
  render(<CallInspector calls={[call]} />);
  fireEvent.click(screen.getByRole("button", { name: /Contexto/ }));
  const facts = screen.getByLabelText("Datos de la llamada");
  expect(screen.getByText("Razonamiento configurado").nextSibling).toHaveTextContent("low");
  expect(screen.getByText("Tokens de razonamiento").nextSibling).toHaveTextContent("0");
  expect(screen.getByText("Intentos HTTP observados").nextSibling).toHaveTextContent("1");
  expect(facts).not.toHaveTextContent("No documentado");
});

it("oculta lo que el portal no registra y muestra la espera real del reintento", () => {
  const call = { id: "retry", agent: "profile", status: "error", started_at: "2026-11-02T23:26:00Z",
    model: "gemini-3.5-flash-lite", provider: "google", prompt_version: "v3.0", prompt_hash: "hash",
    system_prompt: "", schema: {}, http_status: 429, error_type: "HTTPStatusError", error_code: "429",
    quota_kind: "rate-limit", attempt_index: 1, max_attempts: 4, latency_ms: 152, retry_scheduled: true,
    retry_delay_seconds: 2, diagnostic_redacted: true } as Call;
  render(<CallInspector calls={[call]} />);
  fireEvent.click(screen.getByRole("button", { name: /Perfiles/ }));
  const facts = screen.getByLabelText("Datos de la llamada");
  expect(facts).toHaveTextContent("1 / 4");
  expect(facts).toHaveTextContent("tras 2 s");
  expect(facts).not.toHaveTextContent("Razonamiento");
  expect(screen.queryByText(/No documentado|n\/d|No aplicable/)).not.toBeInTheDocument();
  expect(screen.getByText(/Límite por minuto/)).toBeInTheDocument();
  expect(screen.getByText(/Capturar diagnóstico de entradas y salidas/)).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "Prompt efectivo" })).not.toBeInTheDocument();
});

it("muestra la fase registrada del timeout sin atribuirla a una cuota", () => {
  const call = { id: "timeout", agent: "context", status: "error", started_at: "2026-10-14T14:00:00Z",
    model: "gemini-3.5-flash-lite", provider: "google", prompt_version: "v1", prompt_hash: "hash",
    system_prompt: "synthetic", schema: {}, error_type: "APITimeoutError",
    request_timeout_seconds: 60, transport_timeout_kind: "read", provider_http_attempts: 1 } as Call;
  render(<CallInspector calls={[call]} />);
  fireEvent.click(screen.getByRole("button", { name: /Contexto/ }));
  expect(screen.getByText("Fase del timeout").nextSibling).toHaveTextContent("Lectura de respuesta");
  expect(screen.getByText("Timeout de red").nextSibling).toHaveTextContent("60 s");
  expect(screen.queryByText(/Límite del proveedor:/)).not.toBeInTheDocument();
});

it("distingue tokens brutos, cacheados y estimación de cuota solo al inspeccionar la llamada", () => {
  const call = {
    id: "call-1",
    agent: "context",
    status: "success",
    started_at: "2026-09-28T10:00:00Z",
    input_tokens: 100,
    cached_input_tokens: 60,
    uncached_input_tokens: 40,
    output_tokens: 10,
    total_tokens: 110,
    quota_estimated_tokens: 50,
    prompt_version: "context-v11",
    prompt_hash: "hash",
    system_prompt: "stable instructions",
    schema: {},
    model: "openai/gpt-oss-20b",
    provider: "groq",
  } as Call;
  render(<CallInspector calls={[call]} />);
  fireEvent.click(screen.getByRole("button", { name: /Contexto/ }));

  const breakdown = screen.getByLabelText("Consumo de tokens");
  expect(breakdown).toHaveTextContent("Entrada");
  expect(breakdown).toHaveTextContent("100");
  expect(breakdown).toHaveTextContent("60");
  expect(breakdown).toHaveTextContent("40");
  expect(breakdown).toHaveTextContent("Total");
  expect(breakdown).toHaveTextContent("110");
  expect(breakdown).toHaveTextContent("Estimación de cuota Groq");
  expect(breakdown).toHaveTextContent("50");
});

it("distingue un bloqueo local de una cuota diaria confirmada", () => {
  const call = {id: "quota-call", agent: "context", status: "error", model: "gemini-3.6-flash",
    provider: "google", started_at: "2026-10-13T13:45:00Z", prompt_version: "v1",
    prompt_hash: "hash", system_prompt: "safe", schema: {}, error_type: "ProviderQuotaExceeded",
    error_code: "provider-quota-unknown", rate_limit_scope: "UNKNOWN", provider_request_sent: false} as Call;
  render(<CallInspector calls={[call]} />);
  fireEvent.click(screen.getByRole("button", {name: /Contexto/}));
  expect(screen.getByText(/no se puede asegurar que sea un límite diario/)).toBeInTheDocument();
  expect(screen.getByText(/esta llamada no se envió/)).toBeInTheDocument();
});

it("no inventa caché ni cuota cuando el proveedor no comunica el desglose", () => {
  const call = {
    id: "call-2",
    agent: "context",
    status: "success",
    started_at: "2026-09-28T10:00:00Z",
    input_tokens: 100,
    cached_input_tokens: null,
    uncached_input_tokens: null,
    output_tokens: 10,
    total_tokens: 110,
    quota_estimated_tokens: null,
    prompt_version: "context-v11",
    prompt_hash: "hash",
    system_prompt: "stable instructions",
    schema: {},
    model: "model",
    provider: "groq",
  } as Call;
  render(<CallInspector calls={[call]} />);
  fireEvent.click(screen.getByRole("button", { name: /Contexto/ }));

  const breakdown = screen.getByLabelText("Consumo de tokens");
  expect(breakdown).not.toHaveTextContent("cacheada");
  expect(breakdown).not.toHaveTextContent("Estimación de cuota");
  expect(breakdown).toHaveTextContent("110");
});
