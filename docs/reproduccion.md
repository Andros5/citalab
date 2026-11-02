# Reproducción

## Entorno de referencia

- Python 3.13 con las versiones exactas de `requirements.txt`. La integración continua lo
  comprueba en Linux y en Windows.
- Node.js 22 y pnpm 11, solo para la interfaz.
- [Tectonic](https://tectonic-typesetting.github.io), solo para compilar la memoria.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install --no-deps -e .
```

En Windows, las trazas de la campaña tienen rutas largas. Si Git avisa de `Filename too long`,
clona el repositorio en una carpeta más corta (por ejemplo `C:\citalab`) o activa
`git config --global core.longpaths true`.

## Nivel 1. Consultar

No hace falta instalar nada:

- La memoria está en `memoria/memoria-tfm.pdf`.
- Los resultados de la campaña final están en `output/evaluation/final-independent-v1/`.
  Su README describe cada fichero.
- `summary.md` resume las tasas por configuración y `judge/report.md` la concordancia del jurado
  con la revisión humana.

## Nivel 2. Verificar sin claves

```bash
python scripts/reproduce.py --tests
```

Tarda alrededor de un minuto y no llama a ningún modelo. Hace cuatro comprobaciones:

1. **Código evaluado.** El manifiesto de la campaña guarda el hash SHA-256 de cada fichero de
   `src/citalab/`, del perfil sintético, de los scripts de la campaña, del corpus y de las
   instrucciones de los agentes. El comando comprueba que los publicados son exactamente esos.
2. **Tablas de la memoria.** Regenera las tablas de los capítulos 8 y 9
   (`memoria/generated/`) y los resúmenes de `derived/`, y los compara con los publicados.
3. **Informe del jurado.** Recalcula la concordancia entre el jurado y la revisión humana y la
   compara con `judge/report.json`.
4. **Pruebas automáticas.** Ejecuta `pytest`, sin red.

La salida termina con `Resultado: todo coincide con lo publicado`. Los ficheros regenerados se
comparan sin tener en cuenta los finales de línea y, si coinciden, se dejan como estaban.

Los mismos pasos se pueden ejecutar por separado:

```bash
export PYTHONPATH=src            # Windows (PowerShell): $env:PYTHONPATH = "src"
python scripts/derive_thesis_tables.py
python scripts/replay_fixes.py
python scripts/check_fixes_with_models.py --report
python -m citalab_judge report --campaign final-independent-v1
```

Los ficheros cuyo hash fija el manifiesto se publican con los mismos bytes que tenían al ejecutar
la campaña, finales de línea de Windows incluidos. `.gitattributes` impide que Git los convierta.

## Nivel 3. Usar CitaLab

```bash
cp .env.example .env             # añade GROQ_API_KEY o GEMINI_API_KEY
cd web
pnpm install --frozen-lockfile
pnpm build
cd ..
python -m citalab.portal.app     # http://127.0.0.1:8765
```

- El primer arranque crea las cuentas `investigador` (administración), `revisor` (equipo
  investigador), `ana` y `bruno` (pacientes) y `lucia` (representante de Ana). Sus códigos de
  acceso se guardan en `output/portal/accesos-iniciales.txt`.
- Sin claves, el portal arranca igualmente y la pestaña de evaluación muestra la campaña final
  publicada, con cada episodio, su transcripción y sus comprobaciones (cuenta `investigador`).
- Cada conversación elige arquitectura (M5, S1 o H) y modelo (Groq o Gemini). El inspector muestra
  en cada turno las llamadas a los modelos, las decisiones de política y las operaciones sobre la
  agenda.
- Todos los datos son sintéticos. No introduzcas información personal real.

## Nivel 4. Repetir la campaña, el jurado o la revisión

### Campaña

Hacen falta las dos claves: Groq sirve GPT-OSS 20B y el usuario simulado, y Google AI Studio
sirve Gemini. Copia `.env.example` como `.env`, porque fija el tiempo máximo de 20 segundos por
llamada que usó la campaña. Usa otro nombre para no mezclar los resultados con los publicados:

```bash
python scripts/run_independent_campaign.py --campaign mi-repeticion --dry-run
python scripts/run_independent_campaign.py --campaign mi-repeticion
```

- **Coste.** Contando los dos intentos interrumpidos, la campaña original hizo 1501 envíos del
  asistente y 868 del usuario simulado. El asistente consumió unos 1,9 millones de tokens conocidos
  y el simulador unos 0,4 millones.
- **Interrupciones.** Si se agota la cuota de un modelo, el runner pausa solo su cola. El mismo
  comando continúa lo pendiente sin repetir lo hecho y rechaza mezclar versiones de código, corpus
  o configuración.
- **Resultados distintos.** Los modelos no son deterministas aunque la temperatura sea 0, y los
  proveedores pueden actualizarlos. Una repetición puede dar tasas distintas.
- **Análisis.** Al terminar, el script escribe `summary.md` en la carpeta de la nueva campaña.

### Jurado LLM

Los jueces se ejecutan con las CLI de Claude Code y de Codex, con la sesión iniciada en cada una.
El modelo y el esfuerzo están fijados en `src/citalab_judge/judge.py`.

```bash
python -m citalab_judge sample --campaign mi-repeticion        # fija la muestra humana, una vez
python -m citalab_judge judge --judge claude --campaign mi-repeticion
python -m citalab_judge judge --judge codex --campaign mi-repeticion
```

Si una CLI llega a su límite de uso, el juez se detiene. Al relanzar el mismo comando continúa sin
repetir lo evaluado.

### Revisión humana

```bash
python -m citalab_judge review --campaign mi-repeticion        # http://127.0.0.1:8766
python -m citalab_judge report --campaign mi-repeticion
```

La página presenta los episodios de la muestra en orden aleatorio, sin arquitectura ni modelo, y
nunca muestra las notas del jurado, para no condicionar las revisiones siguientes. La segunda
pasada se habilita 48 horas después de la primera revisión de cada episodio.

### Memoria

```bash
python scripts/build_thesis.py   # memoria/build/main.pdf
```
