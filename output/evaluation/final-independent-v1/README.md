# Campaña final `final-independent-v1`

Resultados completos de la campaña que analizan los capítulos 8 y 9 de la memoria: 276 episodios
completados en 278 intentos. Los dos intentos que interrumpió la cuota diaria de Gemini se
repitieron y se conservan como incidentes. Todos los datos son sintéticos.

## Ejecución

| Fichero | Contenido |
|---|---|
| `manifest.json` | Configuración congelada: hash SHA-256 de cada fichero de código y del corpus, hash de las instrucciones, modelos, temperatura, límites y bloques. La ruta del corpus se publica relativa |
| `scenarios.json` | Copia congelada del corpus con la que se ejecutó la campaña |
| `plan.json` | Las 276 celdas planificadas (`cell_id` = proveedor:arquitectura:unidad:bloque) |
| `results.jsonl` | Un registro por intento (ver campos abajo). Si una celda tiene varios, vale el último |
| `traces/` | Cada llamada a un modelo de cada episodio: instrucciones, entrada, salida, tokens, latencia y estado HTTP. Hay un fichero por intento y otro con el último intento de cada celda |
| `summary.md`, `summary.json` | Tasas por configuración y gestión, contrastes pareados y fallos |
| `configurations.csv` | Las mismas tasas en formato tabla, para las figuras |
| `progress.json` | Estado final de la ejecución |

Campos principales de `results.jsonl`:

- **Identificación:** `cell_id`, `provider`, `model`, `architecture`, `unit_id`, `operation`,
  `block`, `language`.
- **Resultado:** `success` (éxito integral), `goal`, `safety`, `checks` (cada comprobación del
  oráculo con su motivo), `effects` (citas creadas, movidas o canceladas y recordatorios),
  `preference_adherence`.
- **Conversación:** `transcript`, `turns`, `end_reason`, `simulator_valid` y `simulator_flags`
  (comprobaciones del usuario simulado).
- **Coste:** `assistant_calls`, `simulator_calls`, `input_tokens`, `output_tokens`,
  `llm_latency_s`, `fallbacks` (textos fijos usados cuando falla un modelo).
- **Agenda:** `initial_state` y `final_state` con los recursos FHIR.

## Jurado y revisión humana (`judge/`)

| Fichero | Contenido |
|---|---|
| `sample-v1.json` | Muestra humana fijada antes del jurado: semilla, reglas, hash del plan y del corpus, y los 60 episodios |
| `judgments-claude-v1.jsonl` | Evaluaciones de Claude Sonnet 5.5: nota de 0 a 3 o NA por dimensión, mensajes de evidencia, cita literal y justificación |
| `judgments-codex-v1.jsonl` | Las mismas evaluaciones de GPT-6.1-Terra |
| `runs.jsonl` | Cada ejecución del jurado: modelo, esfuerzo, versión de la CLI y hash de las instrucciones |
| `reviews-v1.jsonl` | Revisión humana ciega, con notas, evidencia y pasada |
| `report.md`, `report.json`, `tables.tex` | Concordancia entre jueces y con la revisión humana, y estimación con PPI++, que la memoria no utiliza |

Cada evaluación guarda el hash de su entrada, la versión de las instrucciones, los intentos y el
consumo.

## Cifras derivadas (`derived/`)

| Fichero | Contenido |
|---|---|
| `resumen-derivado.json` | Todas las cifras de los capítulos 8 y 9, generadas por `scripts/derive_thesis_tables.py` |
| `reproduccion-correcciones.json` | Repetición sin modelos de cada fallo con el código evaluado y con su corrección (`scripts/replay_fixes.py`) |
| `comprobaciones-modelos.jsonl` | Repeticiones de pasos concretos con los mismos modelos, con y sin corrección (`scripts/check_fixes_with_models.py`) |
| `comprobaciones-modelos-resumen.json` | Resumen de esas repeticiones |

`python scripts/reproduce.py` regenera `derived/` y los informes de `judge/` y comprueba que
coinciden con los publicados.

Licencia: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.es).
