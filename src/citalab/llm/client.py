"""Cliente LLM único (API compatible con OpenAI) para Groq y Google Gemini.

- Salida estructurada con JSON Schema estricto y validación Pydantic local.
- Llamadas a herramientas (function calling) para el agente único S1.
- Reintentos acotados ante 429/5xx/timeout respetando `Retry-After`.
- Cada intento queda registrado como traza para el inspector de CitaLab.

Un fallo agotado lanza `LLMError`; las arquitecturas lo convierten en una
respuesta segura. El arnés de evaluación conserva el episodio como incidente.
Una cuota diaria explícita o un 429 persistente abre el circuito compartido.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from citalab.config import ProviderConfig, Settings

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


class LLMError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def quota_kind(status: int, body: str) -> str | None:
    """Un 429 por sí solo no demuestra agotamiento diario."""
    if status != 429:
        return None
    text = body.casefold()
    daily = ("perday", "per_day", "per day", "daily", "requests/day", "rpd", "tokens/day", "tpd")
    return "daily" if any(marker in text for marker in daily) else "rate-limit"


class RequestGate:
    """Ritmo y circuito compartidos por modelo entre todos los hilos de una campaña."""

    def __init__(self, interval: float = 0, pause_on_quota: bool = True) -> None:
        self.interval = interval
        self.pause_on_quota = pause_on_quota
        self._lock = threading.Lock()
        self._last = 0.0
        self.pause_code: str | None = None

    def pause(self, code: str) -> None:
        with self._lock:
            if self.pause_on_quota:
                self.pause_code = self.pause_code or code

    def enter(self, sleep: Callable[[float], None]) -> None:
        with self._lock:
            if self.pause_code:
                raise LLMError(self.pause_code, "cola pausada; reanudar en otra ejecución")
            wait = self._last + self.interval - time.monotonic()
            if wait > 0:
                sleep(wait)
            self._last = time.monotonic()


@dataclass
class TraceSink:
    """Recoge las trazas de un turno; el portal y el runner las persisten."""

    calls: list[dict] = field(default_factory=list)

    def add(self, trace: dict) -> None:
        self.calls.append(trace)


def strict_schema(model: type[BaseModel]) -> dict:
    """JSON Schema plano y estricto: sin $ref, todos los campos requeridos."""
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(copy.deepcopy(defs[node["$ref"].split("/")[-1]]))
            node = {k: walk(v) for k, v in node.items() if k not in ("title", "default")}
            if node.get("type") == "object" or "properties" in node:
                node["type"] = "object"
                node["required"] = list(node.get("properties", {}))
                node["additionalProperties"] = False
            return node
        if isinstance(node, list):
            return [walk(item) for item in node]
        return node

    return walk(raw)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


class ChatClient:
    """Cliente HTTP para un proveedor; seguro entre hilos."""

    def __init__(self, provider: ProviderConfig, settings: Settings,
                 sink: TraceSink | None = None, sleep: Callable[[float], None] = time.sleep,
                 gate: RequestGate | None = None) -> None:
        if not provider.api_key:
            raise LLMError("missing-api-key", provider.name)
        self.provider = provider
        self.settings = settings
        self.sink = sink or TraceSink()
        self._sleep = sleep
        self._http = httpx.Client(timeout=httpx.Timeout(settings.timeout_seconds, connect=15))
        # La pausa de una cola pertenece a la campaña. Un cliente interactivo
        # sin gate compartido debe poder volver a probar en un turno posterior.
        self.gate = gate or RequestGate(float(os.getenv(f"{provider.name.upper()}_MIN_INTERVAL_SECONDS", "0")),
                                        pause_on_quota=False)

    @property
    def model(self) -> str:
        return self.provider.model

    def close(self) -> None:
        self._http.close()

    def with_sink(self, sink: TraceSink) -> ChatClient:
        clone = copy.copy(self)
        clone.sink = sink
        return clone

    # ------------------------------------------------------------- transporte
    def _post(self, agent: str, payload: dict, trace_input: Any, system: str,
              schema: Any, prompt_version: str) -> dict:
        logical_id = uuid.uuid4().hex[:12]
        max_attempts = self.settings.max_attempts
        last_kind = None
        for attempt in range(1, max_attempts + 1):
            self.gate.enter(self._sleep)
            started = datetime.now(UTC)
            clock = time.perf_counter()
            trace = {
                "id": uuid.uuid4().hex[:12], "agent": agent, "provider": self.provider.name,
                "model": self.provider.model, "started_at": started.isoformat(),
                "prompt_version": prompt_version, "prompt_hash": _hash(system),
                "system_prompt": system, "input": trace_input, "schema": schema,
                "logical_inference_id": logical_id, "attempt_index": attempt,
                "max_attempts": max_attempts, "provider_request_sent": True,
            }
            retry_after = None
            try:
                response = self._http.post(
                    f"{self.provider.base_url}/chat/completions", json=payload,
                    headers={"Authorization": f"Bearer {self.provider.api_key}"})
                trace["http_status"] = response.status_code
                if response.status_code == 200:
                    body = response.json()
                    usage = body.get("usage") or {}
                    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
                    trace.update(status="success", input_tokens=usage.get("prompt_tokens"),
                                 output_tokens=usage.get("completion_tokens"),
                                 total_tokens=usage.get("total_tokens"),
                                 cached_input_tokens=cached,
                                 output={k: v for k, v in body["choices"][0]["message"].items()
                                         if k not in ("reasoning", "reasoning_content")})
                    return body
                text = response.text[:2000]
                error_code = None
                try:
                    parsed = response.json()
                    parsed = parsed[0] if isinstance(parsed, list) and parsed else parsed
                    error = parsed.get("error") if isinstance(parsed, dict) else None
                    error_code = error.get("code") if isinstance(error, dict) else None
                    error_code = str(error_code) if error_code is not None else None
                except ValueError:
                    pass
                trace.update(status="error", error_type="HTTPStatusError", error_code=error_code,
                             output={"error": text})
                last_kind = quota_kind(response.status_code, response.text)
                trace["quota_kind"] = last_kind
                if last_kind == "daily":
                    trace["terminal_error"] = "provider-daily-quota"
                    self.gate.pause("provider-daily-quota")
                    raise LLMError("provider-daily-quota", self.provider.name)
                if response.status_code not in RETRYABLE_STATUS:
                    trace["terminal_error"] = f"http-{response.status_code}"
                    raise LLMError(f"http-{response.status_code}", error_code or text[:200])
                header = response.headers.get("retry-after")
                if header:
                    try:
                        retry_after = min(float(header), 90.0)
                    except ValueError:
                        retry_after = None
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_kind = None
                trace.update(status="error", error_type=type(exc).__name__,
                             transport_timeout_kind="read" if isinstance(exc, httpx.ReadTimeout) else None,
                             output={"error": str(exc)[:500]})
            finally:
                finished = datetime.now(UTC)
                trace["finished_at"] = finished.isoformat()
                trace["latency_ms"] = round((time.perf_counter() - clock) * 1000)
                if trace.get("status") != "success":
                    trace.setdefault("status", "error")
                    if attempt == max_attempts and "terminal_error" not in trace:
                        trace["terminal_error"] = ("provider-rate-limit-exhausted" if last_kind == "rate-limit"
                                                   else "provider-unavailable")
                    trace["retry_scheduled"] = attempt < max_attempts and "terminal_error" not in trace
                self.sink.add(trace)
            if attempt < max_attempts:
                delay = retry_after if retry_after is not None else min(2.0 * 2 ** (attempt - 1), 30.0)
                trace["retry_delay_seconds"] = delay
                self._sleep(delay)
        code = "provider-rate-limit-exhausted" if last_kind == "rate-limit" else "provider-unavailable"
        if last_kind == "rate-limit":
            self.gate.pause(code)
        raise LLMError(code, f"{self.provider.name} tras {max_attempts} intentos")

    def _base(self, messages: list[dict]) -> dict:
        payload: dict[str, Any] = {"model": self.provider.model, "messages": messages,
                                   "temperature": self.settings.temperature,
                                   "max_tokens": self.settings.max_output_tokens}
        if self.provider.reasoning_effort:
            payload["reasoning_effort"] = self.provider.reasoning_effort
        return payload

    # ------------------------------------------------------------- interfaz
    def structured(self, agent: str, system: str, payload: Any, schema: type[BaseModel],
                   prompt_version: str = "v1") -> BaseModel:
        """Devuelve una instancia válida de `schema` o lanza `LLMError`."""
        user = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, default=str)
        json_schema = strict_schema(schema)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        request = self._base(messages)
        request["response_format"] = {"type": "json_schema", "json_schema": {
            "name": schema.__name__, "schema": json_schema, "strict": True}}
        try:
            body = self._post(agent, request, payload, system, json_schema, prompt_version)
        except LLMError as exc:
            if not exc.code.startswith("http-400"):
                raise
            # Algunos modelos rechazan la gramática estricta: modo JSON + validación local.
            request["response_format"] = {"type": "json_object"}
            request["messages"] = [{"role": "system", "content": system + "\n\nResponde SOLO con un objeto JSON "
                                    "con exactamente estos campos (usa null, no el texto \"null\"):\n"
                                    + _field_guide(json_schema)},
                                   {"role": "user", "content": user}]
            body = self._post(agent, request, payload, system, json_schema, prompt_version)
        content = body["choices"][0]["message"].get("content") or ""
        try:
            return schema.model_validate_json(_strip_fences(content))
        except ValidationError as exc:
            # Una única reparación con el error concreto; si falla, el llamante decide.
            request["messages"] = [*request["messages"], {"role": "assistant", "content": content},
                                   {"role": "user", "content": "El JSON no es válido: "
                                    f"{exc.errors()[:3]}. Devuelve el objeto corregido."}]
            body = self._post(f"{agent}:repair", request, payload, system, json_schema, prompt_version)
            content = body["choices"][0]["message"].get("content") or ""
            try:
                return schema.model_validate_json(_strip_fences(content))
            except ValidationError as again:
                raise LLMError("invalid-structured-output", str(again)[:300]) from again

    def chat(self, agent: str, messages: list[dict], tools: list[dict] | None = None,
             prompt_version: str = "v1") -> dict:
        """Una vuelta de conversación; devuelve el mensaje del asistente."""
        request = self._base(messages)
        if tools:
            request["tools"] = tools
            request["tool_choice"] = "auto"
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        visible = [m for m in messages if m["role"] != "system"]
        body = self._post(agent, request, visible[-6:], system, tools, prompt_version)
        return body["choices"][0]["message"]


def _field_guide(schema: dict) -> str:
    lines = []
    for name, spec in schema.get("properties", {}).items():
        options = spec.get("enum") or [v for alt in spec.get("anyOf", []) for v in alt.get("enum", [])]
        kind = spec.get("type") or "/".join(str(alt.get("type")) for alt in spec.get("anyOf", []))
        lines.append(f"- {name}: {kind}" + (f" uno de {options}" if options else ""))
    return "\n".join(lines)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if start >= 0 and end > start else text


class ScriptedClient:
    """Doble de pruebas: devuelve respuestas predefinidas por agente, sin red."""

    def __init__(self, script: dict[str, list[Any]] | None = None, sink: TraceSink | None = None,
                 provider: str = "scripted", model: str = "scripted") -> None:
        self.script = {key: list(values) for key, values in (script or {}).items()}
        self.sink = sink or TraceSink()
        self.provider = ProviderConfig(provider, "", "x", model)
        self.model = model

    def with_sink(self, sink: TraceSink) -> ScriptedClient:
        clone = copy.copy(self)
        clone.sink = sink
        return clone

    def _next(self, agent: str) -> Any:
        queue = self.script.get(agent)
        if not queue:
            raise LLMError("script-exhausted", agent)
        value = queue.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def _trace(self, agent: str, payload: Any, output: Any) -> None:
        self.sink.add({"id": uuid.uuid4().hex[:12], "agent": agent, "provider": self.provider.name,
                       "model": self.model, "status": "success", "started_at": datetime.now(UTC).isoformat(),
                       "latency_ms": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
                       "prompt_version": "scripted", "prompt_hash": "", "system_prompt": "",
                       "input": payload, "output": output, "schema": None, "attempt_index": 1})

    def structured(self, agent: str, system: str, payload: Any, schema: type[BaseModel],
                   prompt_version: str = "v1") -> BaseModel:
        value = self._next(agent)
        if callable(value):
            value = value(payload)
        result = value if isinstance(value, BaseModel) else schema.model_validate(value)
        self._trace(agent, payload, result.model_dump(mode="json"))
        return result

    def chat(self, agent: str, messages: list[dict], tools: list[dict] | None = None,
             prompt_version: str = "v1") -> dict:
        value = self._next(agent)
        if callable(value):
            value = value(messages)
        self._trace(agent, messages[-1:], value)
        return value
