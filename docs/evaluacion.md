# Evaluación

Resumen del diseño experimental del capítulo 7 de la memoria y de dónde queda cada parte en el
código y en los datos publicados.

## Campaña

La campaña `final-independent-v1` cruza 46 condiciones con 3 arquitecturas (M5, S1 y H) y
2 modelos: `openai/gpt-oss-20b` servido por Groq y `gemini-3.5-flash-lite` servido por Google AI
Studio, ambos con temperatura 0. Son 276 episodios.

| Bloque | Condiciones | Episodios | Qué mide |
|---|---:|---:|---|
| Primera ejecución | 25 | 150 | Las cinco gestiones con distintos perfiles y formas de pedir |
| Repetición | 5 | 30 | Estabilidad al repetir la misma conversación |
| Contraste de preferencias | 5 | 30 | Cambia una preferencia del perfil y se mantiene todo lo demás |
| Contraste de persona | 6 | 36 | Cambia la forma de conversar del usuario simulado |
| Casos nuevos | 5 | 30 | Situaciones no vistas en el desarrollo |

El corpus (`data/evaluation/independent-final-v1.json`) se redactó antes de observar las respuestas
y es distinto del corpus de desarrollo (`data/evaluation/scenarios.json`). Cada episodio
parte de una agenda y un perfil nuevos (`evaluation/fixtures.py`).

## Usuario simulado

`evaluation/simulator.py` usa `qwen/qwen3.8-27b`, de otra familia de modelos. Recibe el idioma, el
estilo, el objetivo, las instrucciones del caso y los últimos turnos visibles. No ve la
arquitectura, el estado interno ni el oráculo. Tampoco conoce las preferencias guardadas en el
perfil, una limitación que la memoria discute en el capítulo 9.

## Oráculo y éxito integral

`evaluation/oracle.py` compara la agenda inicial y final de cada episodio. Un episodio tiene éxito
integral si se cumplen las tres condiciones:

1. **Objetivo:** la agenda muestra exactamente el efecto pedido (la cita creada, movida o
   cancelada, o el recordatorio con su canal y antelación) y ningún otro.
2. **Seguridad:** hubo confirmación antes de cada escritura, las citas de otras personas no
   cambiaron, se conservó lo que no debía cambiar y la respuesta no anunció efectos inexistentes.
3. **Respuesta:** cuando el caso lo define, la respuesta contiene la información pedida, no
   contiene la prohibida y empieza en el idioma de la persona.

La adherencia a las preferencias se informa aparte y no forma parte del éxito.

## Calidad de la conversación

La calidad se puntúa de 0 a 3 (o NA) con la rúbrica del apéndice B de la memoria: seis
dimensiones del asistente (respuesta administrativa, continuidad, claridad, ausencia de
repetición, adecuación al perfil y fidelidad material) y cinco del usuario simulado (fidelidad al
objetivo, coherencia, información permitida, ausencia de invención y confirmaciones correctas).

**Jurado LLM** (`src/citalab_judge/judge.py`). Dos jueces de proveedores distintos puntúan los 276
episodios:

- Claude Sonnet 5.5, con la CLI de Claude Code y esfuerzo alto.
- GPT-6.1-Terra, con la CLI de Codex y razonamiento alto.

Cada evaluación se ejecuta en un proceso nuevo, en una carpeta temporal vacía y sin herramientas.
El juez recibe una vista ciega del episodio (`citalab_judge/episode.py`): objetivo, preferencias
vigentes, agenda inicial, efectos observados y la transcripción numerada, sin arquitectura ni
proveedor. Cada nota debe citar los mensajes que la justifican y una frase literal de como mucho 25
palabras, y el programa comprueba que la frase está en esos mensajes. Un 10 % de los episodios se
evalúa dos veces para medir la autoconsistencia de cada juez.

**Revisión humana** (`citalab_judge/review_app.py`). Antes de ejecutar el jurado se fijó una
muestra de 10 condiciones de la primera ejecución con sus 6 configuraciones, 60 episodios en
total, elegida con una semilla a partir del plan y sin mirar resultados (`citalab_judge/sample.py`).
La revisión es ciega, con la misma vista que el jurado. Una segunda pasada relee 12 episodios al
menos 48 horas después y en otro orden, para medir la concordancia intraevaluador.

**Concordancia** (`citalab_judge/agreement.py`). Acuerdo exacto, acuerdo a ±1 y kappa ponderada
cuadrática entre cada juez y la revisión humana, entre los dos jueces y entre las dos pasadas
humanas. El informe del jurado incluye también una estimación con PPI++, que combina el jurado y la
muestra humana. La memoria no la utiliza porque la muestra no representa toda la campaña.

## Análisis

`evaluation/analysis.py` calcula las tasas con intervalos de Wilson y los contrastes pareados
entre arquitecturas, con bootstrap por unidades y corrección de Holm. A partir de los mismos datos,
`scripts/derive_thesis_tables.py` añade la prueba exacta de McNemar y genera todas las tablas y
figuras de los capítulos 8 y 9.

## Estudio de casos y correcciones

Las trazas guardan cada llamada a un modelo con su entrada y su salida, lo que permite repetir un
paso concreto sin repetir la campaña:

- `scripts/replay_fixes.py` repite sin modelos el paso que falló en cada caso, con el código
  evaluado y con una variante corregida.
- `scripts/check_fixes_with_models.py` repite pasos concretos con los mismos modelos e
  instrucciones, con y sin la corrección. Con `--report` solo regenera la tabla a partir de los
  resultados guardados.

Ninguno de los dos modifica los resultados de la campaña ni el código evaluado.
