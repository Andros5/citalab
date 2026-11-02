# Guía del código

Esta guía sigue una petición desde la interfaz hasta la agenda y de vuelta, y después recorre los
módulos de la evaluación. Los capítulos 5 y 6 de la memoria explican el diseño y sus motivos.

## Recorrido de una petición

```text
web (React) ─► portal/app.py (FastAPI) ─► portal/service.py ─► assistant/engine.py
                                                                     │  M5 · S1 · H
                                                                     ▼
                                     assistant/tools.py ─► domain/policy.py ─► domain/agenda.py
                                                                     │
                                                                     ▼
                                     assistant/respond.py (hechos fijados por código + redacción)
```

1. **Interfaz.** `web/src/api.ts` es la única puerta HTTP. La conversación está en
   `web/src/features/conversations/`.
2. **API.** `src/citalab/portal/app.py` define las rutas (`/api/conversations/{id}/turns`, entre
   otras), autentica la sesión y delega en `portal/service.py`, que crea un trabajo por turno y
   guarda el historial en SQLite (`portal/storage.py`).
3. **Motor.** `Assistant.turn` (`assistant/engine.py`) recibe la acción (`message`, `confirm` o
   `discard`) y ejecuta la arquitectura de la conversación:
   - **H** (`_run_h`): el agente de contexto interpreta el mensaje y `_programmed_flow` decide en
     código qué herramienta usar.
   - **M5** (`_build_m5_graph`): un grafo de LangGraph con los nodos contexto → cumplimiento →
     perfiles → (orquestar ⇄ actuar) → personalización. El orquestador solo puede elegir entre las
     acciones que permite el estado (`_m5_allowed`).
   - **S1** (`_run_s1`): un único agente con llamadas nativas a herramientas, limitado a
     `MAX_TOOL_ROUNDS` rondas.
4. **Herramientas.** `Toolbox` (`assistant/tools.py`) es la única vía por la que los modelos piden
   datos o cambios. Las escrituras siempre pasan por una propuesta (`propose_*`) y por `confirm`.
   Además, el código prepara para los agentes un resumen con las citas del paciente de la sesión
   (`Toolbox.context_summary`) y lee del perfil su estilo de respuesta (`Assistant._style`), sin
   pasar por las herramientas.
5. **Políticas.** `domain/policy.py` comprueba identidad, representación, finalidad del perfil y
   confirmación (`check_access`, `check_profile`, `check_write`). Ningún modelo puede ampliar
   estas reglas.
6. **Agenda.** `domain/agenda.py` simula un sistema de información hospitalario con recursos
   `Slot`, `Appointment` y `CommunicationRequest` de FHIR R4. Las reservas, los cambios y las
   cancelaciones revalidan la versión del hueco y de la cita antes de escribir.
7. **Respuesta.** `assistant/respond.py` construye un plan con los hechos que puede decir la
   respuesta (citas, horas, propuestas, recibos) y un modelo solo los redacta. `check_draft`
   sustituye la redacción por un texto fijo si pierde una hora o la pregunta del plan, añade horas
   ajenas o parece anunciar un efecto que no se ha producido.

Las instrucciones de cada agente están en `assistant/prompts.py` y sus salidas estructuradas en
`assistant/schemas.py`. El estado de la conversación (tarea, propuesta, preferencias del turno) está
en `assistant/state.py`.

## Módulos

| Módulo | Contenido |
|---|---|
| `config.py` | Configuración leída del entorno y de `.env` |
| `domain/agenda.py` | Agenda FHIR simulada |
| `domain/policy.py` | Motor de políticas determinista |
| `domain/profiles.py` | Perfil con procedencia, confianza, vigencia y finalidad de cada atributo |
| `domain/text.py` | Fechas, horas e idioma (zona Europe/Madrid) |
| `assistant/engine.py` | Las tres arquitecturas |
| `assistant/tools.py` | Herramientas compartidas, propuestas y confirmación |
| `assistant/respond.py` | Planes de respuesta y comprobación de la redacción |
| `assistant/prompts.py`, `schemas.py`, `state.py` | Instrucciones, contratos de salida y estado |
| `llm/client.py` | Cliente único compatible con OpenAI para Groq y Gemini, con reintentos y trazas |
| `evaluation/fixtures.py` | Agenda y perfil aislados para cada episodio |
| `evaluation/simulator.py` | Usuario simulado |
| `evaluation/oracle.py` | Oráculo que compara la agenda inicial y final |
| `evaluation/runner.py` | Planificación, ejecución y reanudación de la campaña |
| `evaluation/analysis.py` | Tasas, contrastes pareados y coste |
| `evaluation/review.py` | Rúbrica y concordancia de la revisión humana |
| `portal/` | API, servicio y almacenamiento del portal |
| `citalab_judge/` | Jurado LLM, revisión humana ciega y concordancia (ver [evaluación](evaluacion.md)) |

## Pruebas

Todas se ejecutan sin red con `python -m pytest`. Los modelos se sustituyen por respuestas
guionizadas.

| Fichero | Qué comprueba |
|---|---|
| `tests/test_domain.py` | Agenda FHIR, perfiles y políticas |
| `tests/test_adversarial.py` | Casos adversariales sobre las herramientas compartidas |
| `tests/test_architectures.py` | M5, S1 y H producen los mismos efectos con decisiones distintas |
| `tests/test_requirements.py` | Requisitos del capítulo 3 y del apéndice A |
| `tests/test_evaluation.py` | Oráculo, planificación, runner y análisis |
| `tests/test_campaign_recovery.py` | Fallos de los proveedores y reanudación de la campaña |
| `tests/test_judge.py` | Vista ciega, validación del jurado, muestra, kappa y PPI |
| `tests/test_portal.py` | API del portal |

La interfaz tiene sus propias pruebas (`pnpm test` en `web/`).

## Interfaz

`web/src/features/` agrupa las pantallas: conversación, agenda, perfiles, administración, ayuda,
inspector de turnos y evaluación. El servidor es siempre quien decide permisos y estado, y la
interfaz solo presenta lo que recibe. Los textos se traducen al inglés con `web/src/i18n.tsx`, y
`pnpm run i18n:check` comprueba que no falte ninguno.
