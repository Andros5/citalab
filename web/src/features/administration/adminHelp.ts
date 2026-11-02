import { getUiLanguage, translateText, tx } from "../../i18n";
import type { FieldHelp } from "../../shared/ui/FieldInfo";

type Copy = readonly [string, string];
const pick = (copy: Copy) => copy[getUiLanguage() === "en" ? 1 : 0];
export const sectionHelp: Record<string, Copy> = {
  config: [
    "Valores predeterminados para nuevas conversaciones del portal. Las conversaciones existentes conservan su configuración; la pausa remota se comprueba antes de cada llamada. No cambia una campaña congelada.",
    "Defaults for new portal conversations. Existing conversations retain their configuration; remote pauses are checked before each call. Frozen campaigns are not changed.",
  ],
  prompts: [
    "Instrucciones adicionales versionadas del portal. No sustituyen contratos, permisos ni confirmaciones. Publicar no ejecuta inferencias ni modifica resultados históricos.",
    "Versioned additional portal instructions. They do not replace contracts, permissions or confirmations. Publishing does not run inference or alter historical results.",
  ],
  scenario: [
    "Agenda y datos del laboratorio local. Las ampliaciones requieren confirmación y pueden invalidar propuestas existentes. No son citas reales.",
    "Local laboratory schedule and data. Expansions require confirmation and may invalidate existing proposals. These are not real appointments.",
  ],
  quotas: [
    "Registro local de consumo compartido por portal y ejecutores que lo utilizan. Filtrar solo consulta; guardar controles no modifica cuotas oficiales, activa facturación ni autoriza una campaña.",
    "Local consumption ledger shared by the portal and runners using it. Filtering only reads data; saving controls does not change official quotas, enable billing or authorize a campaign.",
  ],
  observability: [
    "Lectura de trazas locales y métricas de ejecución. No sustituye el ledger, las cuotas oficiales ni la valoración humana.",
    "Read-only local traces and runtime metrics. Not a substitute for the ledger, official quotas or human assessment.",
  ],
  "conversation-evaluation": [
    "Preparación del corpus, modelos y planificación presupuestaria. Un borrador o una estimación no inicia ni autoriza una campaña; las revisiones congeladas anteriores se conservan.",
    "Corpus, model and budget planning. A draft or estimate does not start or authorize a campaign; previous frozen revisions are retained.",
  ],
  "conversation-review": [
    "Sesión de revisión humana: borrador, primera pasada, revelación y firma son pasos distintos. Una propuesta IA nunca se registra automáticamente como adjudicación humana.",
    "Human review session: draft, blind pass, disclosure and signature are distinct steps. An AI proposal is never automatically recorded as human adjudication.",
  ],
  accounts: [
    "Cuentas y roles de acceso al portal. Generar códigos modifica el acceso de la cuenta seleccionada; no cambia claves de proveedores.",
    "Portal accounts and access roles. Generating codes changes access for the selected account, not provider keys.",
  ],
  storage: [
    "Instantáneas y retención de datos locales. Restaurar o purgar requiere confirmación explícita; las copias externas y exportaciones no están incluidas.",
    "Local snapshots and data retention. Restore or purge requires explicit confirmation; external backups and exports are not included.",
  ],
  audit: [
    "Filtro de los últimos 500 eventos administrativos cargados. No cambia datos ni es el registro completo de consumo o de inferencias.",
    "Filter of the last 500 loaded administrative events. Does not change data and is not the complete consumption or inference ledger.",
  ],
};

export const fieldDescriptions: Record<string, Copy> = {
  "Recuperación de errores transitorios": [
    "Política común para Groq y Gemini en nuevas conversaciones: un intento o hasta tres con espera exponencial y variación aleatoria. Cada envío reserva cuota y presupuesto. No reintenta 429, contratos inválidos ni operaciones administrativas. Las conversaciones existentes y las campañas congeladas conservan su política.",
    "Shared Groq/Gemini policy for new conversations: one attempt or up to three with exponential backoff and jitter. Each send reserves quota and budget. Never retries 429s, invalid contracts or administrative operations. Existing conversations and frozen campaigns retain their policy.",
  ],
  "Solicitudes diarias (RPD)": [
    "Solicitudes contabilizadas en la jornada del proveedor. La ventana depende del ámbito; no es el pico de solicitudes por minuto.",
    "Requests accounted in the provider day. The window depends on scope; not the peak requests per minute.",
  ],
  "Tokens diarios (TPD)": [
    "Tokens contabilizados en la ventana diaria. Si el límite no está acreditado, no se presume ilimitado.",
    "Tokens accounted in the daily window. An unevidenced limit is not assumed unlimited.",
  ],
  "Solicitudes último minuto (RPM)": [
    "Solicitudes contabilizadas en el minuto reciente. Agotar esta ventana no implica perder toda la cuota diaria.",
    "Requests accounted in the recent minute. Exhausting this window does not mean losing all daily quota.",
  ],
  "Tokens último minuto (TPM)": [
    "Tokens sujetos a cuota en el minuto reciente, según la política del proveedor. No equivalen necesariamente a entrada más salida facturadas.",
    "Quota tokens in the recent minute according to provider policy. Not necessarily equal to billed input plus output.",
  ],
  "Entrada último minuto (ITPM)": [
    "Tokens de entrada contabilizados en el minuto. Solo se interpreta como límite separado cuando el proveedor lo acredita.",
    "Input tokens accounted in the minute. Only treated as a separate limit when evidenced by the provider.",
  ],
  "Salida último minuto (OTPM)": [
    "Tokens de salida contabilizados en el minuto. No implica que exista un límite separado acreditado.",
    "Output tokens accounted in the minute. Does not imply an evidenced separate limit exists.",
  ],
  "Modelo de conexión": [
    "Modelo configurado en el entorno local para este proveedor. Se muestra en lectura; este panel no cambia su identificador ni consulta su disponibilidad.",
    "Model configured in the local environment for this provider. Read-only here; this panel neither changes its identifier nor probes availability.",
  ],
  "Arquitectura predeterminada": [
    "Variante inicial M5, S1 o H al crear una conversación. No cambia la variante de sesiones abiertas.",
    "Initial M5, S1 or H variant for a new conversation; does not change open sessions.",
  ],
  "Proveedor predeterminado": [
    "Motor inicialmente seleccionado. Groq y Gemini son alternativas equivalentes. No hay sustitución automática si falla un proveedor.",
    "Initially selected engine. Groq and Gemini are equivalent alternatives. Provider failure does not trigger automatic switching.",
  ],
  "Permitir llamadas a proveedores externos": [
    "Autoriza al portal a utilizar las claves ya configuradas. Desactivarlo impide nuevas llamadas; no cancela las ya enviadas.",
    "Allows the portal to use configured keys. Disabling prevents new calls; it does not cancel calls already sent.",
  ],
  "Máximo de llamadas por turno (M5/S1)": [
    "Presupuesto de intentos del ciclo de agentes, incluidos fallos. No es el límite por episodio de una campaña.",
    "Agent-cycle attempt budget, including failures. Not the per-episode limit of a campaign.",
  ],
  "Límite diario de intentos remotos": [
    "Tope local por día UTC, contando fallos. Es distinto de RPM, TPM y RPD oficiales y del reinicio Pacific de Gemini.",
    "Local daily cap in UTC, including failures. Separate from official RPM, TPM and RPD and Gemini's Pacific reset.",
  ],
  "Espera máxima por llamada (segundos)": [
    "Tiempo máximo de una llamada individual, no de todo el turno. La espera de cuota y otras fases deben distinguirse en las trazas.",
    "Maximum time for an individual call, not the whole turn. Quota waits and other phases must be distinguished in traces.",
  ],
  Temperatura: [
    "Variación de generación para Groq y Gemini. Cero favorece consistencia, no garantiza determinismo ni controla el razonamiento.",
    "Generation variability for Groq and Gemini. Zero favors consistency, but does not guarantee determinism or control reasoning.",
  ],
  "Máximo de tokens de salida": [
    "Tope de salida por llamada para Groq y Gemini. No limita la entrada ni el total del turno; una salida truncada puede invalidar el contrato.",
    "Output cap per call for Groq and Gemini. Does not limit input or turn totals; truncated output can invalidate the contract.",
  ],
  "Duración del acceso (minutos)": [
    "Caducidad absoluta de nuevas sesiones de acceso. No es la duración de una conversación experimental.",
    "Absolute expiry for new sign-in sessions. Not the duration of an experimental conversation.",
  ],
  "Retención de conversaciones (días)": [
    "Antigüedad máxima del historial local sujeto a limpieza. Incluye auditoría e instantáneas caducadas; no borra la agenda vigente.",
    "Maximum age of local history subject to cleanup. Includes expired audit and snapshots; does not delete the current schedule.",
  ],
  "Retención de diagnóstico (días)": [
    "Periodo para entradas y salidas capturadas opcionalmente. Debe ser menor o igual que la retención general.",
    "Retention period for optionally captured inputs and outputs. Must not exceed general retention.",
  ],
  Rol: [
    "Función del agente cuya instrucción se edita, no el rol de una cuenta. Cada función conserva su propio borrador.",
    "Agent function whose instruction is edited, not an account role. Each function keeps its own draft.",
  ],
  "Instrucción adicional": [
    "Texto añadido a la plantilla base. Puede quedar vacío; no reemplaza salvaguardas ni el esquema de salida.",
    "Text appended to the base template. Can be empty; does not replace safeguards or the output schema.",
  ],
  "Hipótesis o motivo del cambio": [
    "Justificación registrada junto a la nueva versión del prompt; no se interpreta como una orden administrativa.",
    "Rationale stored with the new prompt version; not interpreted as an administrative instruction.",
  ],
  "Motivo de la nueva configuración": [
    "Explicación auditable de la publicación. Guardar requiere una versión vigente compatible.",
    "Auditable explanation for publishing. Saving requires a compatible current version.",
  ],
  "Confirmar ampliación": [
    "Frase exacta requerida para ampliar el escenario. No equivale a confirmar una reserva.",
    "Exact phrase required to expand the scenario. Does not confirm an appointment.",
  ],
  "Desde (UTC, incluido)": [
    "Inicio del intervalo de lectura incluido. No es una jornada Pacific ni una ventana deslizante de un minuto.",
    "Inclusive start of the reading interval. Not a Pacific day or a rolling one-minute window.",
  ],
  "Hasta (UTC, excluido)": [
    "Fin del intervalo, no incluido. Junto con Desde delimita los eventos del informe.",
    "Exclusive end of the interval. Together with From, bounds report events.",
  ],
  Proveedor: [
    "Filtra los registros por Groq o Gemini, sin cambiar el motor predeterminado del portal.",
    "Filters records by Groq or Gemini without changing the default portal engine.",
  ],
  Modelo: [
    "Identificador exacto del modelo para filtrar su consumo. Modelos del mismo proveedor pueden tener cuotas distintas.",
    "Exact model identifier for filtering consumption. Models from the same provider can have different quotas.",
  ],
  "Origen exacto (opcional)": [
    "Coincidencia con el origen registrado, como portal o runtime. Vacío incluye todos los orígenes.",
    "Matches the recorded source, such as portal or runtime. Empty includes all sources.",
  ],
  Estado: [
    "Filtra el estado de los registros de esta sección. No modifica el estado ni la selección de otras secciones.",
    "Filters record status in this section. Does not change status or selections in other sections.",
  ],
  "Proveedor, ámbito y modelo": [
    "Selecciona el control concreto. Gemini utiliza ámbito de proyecto; Groq, de organización. Un control no se traslada a otro modelo.",
    "Selects the specific control. Gemini uses project scope; Groq uses organization scope. A control is not transferred to another model.",
  ],
  Acción: [
    "Elige lectura de consola, controles/tarifa o pausa. Revisa y confirma antes de guardar cualquier cambio.",
    "Choose console reading, controls/rates or pause. Review and confirm before saving changes.",
  ],
  "Fecha y hora de lectura (hora local del equipo; se guarda en UTC)": [
    "Momento real de la observación, no la fecha de registro. Se convierte de hora local a UTC.",
    "Actual observation time, not registration time. Converted from local time to UTC.",
  ],
  "Procedencia de la lectura": [
    "Fuente utilizada para observar el consumo; distingue una consola oficial de una estimación o lectura local.",
    "Source used to observe consumption; distinguishes an official console from an estimate or local reading.",
  ],
  "Métrica observada": [
    "RPD, RPM, TPM u otra métrica acreditada. No son intercambiables; un pico de RPM no implica agotar el día.",
    "RPD, RPM, TPM or another evidenced metric. They are not interchangeable; an RPM peak does not imply daily exhaustion.",
  ],
  "Valor de la métrica (no el límite ni el saldo)": [
    "Cantidad consumida u observada que muestra la fuente. No introduzca el denominador del límite ni el remanente.",
    "Consumed or observed quantity shown by the source. Do not enter the limit denominator or remaining balance.",
  ],
  "Periodo exacto seleccionado": [
    "Periodo que muestra el panel oficial. Debe coincidir con el inicio y fin registrados.",
    "Period displayed by the official dashboard. Must match the recorded start and end.",
  ],
  "Inicio exacto de la ventana (ISO-8601 con zona)": [
    "Inicio real de la ventana observada con zona horaria, no una fecha inferida de 'último día'.",
    "Actual observed window start with timezone, not a date inferred from 'last day'.",
  ],
  "Fin exacto de la ventana (ISO-8601 con zona)": [
    "Fin real de la ventana observada con zona horaria. Permite comparar observaciones del mismo intervalo.",
    "Actual observed window end with timezone. Enables comparison of observations from the same interval.",
  ],
  "¿El panel muestra un aviso de límite alcanzado?": [
    "Registra lo mostrado por la consola. El aviso por sí solo no identifica qué cuota se agotó.",
    "Records what the console shows. The notice alone does not identify which quota was exhausted.",
  ],
  "Proyecto de Google": [
    "Proyecto al que pertenece la cuota Gemini. Crear o cambiar claves dentro del mismo proyecto no renueva su cuota.",
    "Project owning the Gemini quota. Creating or changing keys within the same project does not renew quota.",
  ],
  "URL de procedencia": [
    "Página oficial que respalda la lectura. No incluya claves, tokens ni enlaces con credenciales.",
    "Official page supporting the reading. Do not include keys, tokens or credential-bearing links.",
  ],
  "Detalle de la captura (sin credenciales)": [
    "Contexto verificable de la observación: modelo, métrica, ventana y valores mostrados; nunca secretos.",
    "Verifiable observation context: model, metric, window and displayed values; never secrets.",
  ],
  "Solicitudes totales consumidas (opcional)": [
    "Total consumido observado para el ámbito y ventana seleccionados, incluyendo uso externo conocido.",
    "Observed consumption total for the selected scope and window, including known external usage.",
  ],
  "Tokens sujetos a cuota consumidos (opcional)": [
    "Tokens que el proveedor computa para su cuota. No siempre equivalen a los tokens facturados o al total de salida.",
    "Tokens counted by the provider toward quota. Not always equal to billed tokens or output totals.",
  ],
  "Plan acreditado": [
    "Plan respaldado por evidencia. No contrata ni cambia el plan del proveedor.",
    "Evidence-backed plan. Does not subscribe to or change the provider plan.",
  ],
  "Moneda (sin conversión)": [
    "Divisa de los precios registrados. No aplica cambio de moneda.",
    "Currency of recorded prices. No currency conversion is performed.",
  ],
  "Precio de entrada por millón": [
    "Precio por un millón de tokens de entrada no cacheada, según tarifa acreditada.",
    "Price per million uncached input tokens, according to the evidenced rate.",
  ],
  "Precio de entrada cacheada por millón": [
    "Precio específico de tokens de entrada cacheados, si el proveedor lo acredita.",
    "Specific cached-input token price, when evidenced by the provider.",
  ],
  "Precio de salida por millón": [
    "Precio por un millón de tokens de salida; no incluye entrada ni impuestos no registrados.",
    "Price per million output tokens; excludes input and unrecorded taxes.",
  ],
  "Aplicable desde (UTC)": [
    "Momento a partir del cual la tarifa registrada es aplicable. No reescribe tarifas históricas.",
    "Time from which the recorded rate applies. Does not rewrite historical rates.",
  ],
  "Referencia que acredita el plan o precios": [
    "Fuente verificable del plan o tarifa. Una tarifa desconocida no equivale a coste cero.",
    "Verifiable plan or rate source. An unknown rate is not zero cost.",
  ],
  "Avisar al alcanzar el % de cuota": [
    "Umbral de alerta local; no aumenta el límite ni autoriza solicitudes adicionales.",
    "Local alert threshold; does not raise the limit or authorize more requests.",
  ],
  "Aviso de coste en el intervalo filtrado (opcional)": [
    "Alerta local sobre el coste calculado del intervalo. No es una factura ni un bloqueo de gasto del proveedor.",
    "Local alert on calculated interval cost. Not a bill or a provider spending cap.",
  ],
  "Motivo auditable (nunca claves API)": [
    "Explicación conservada con el cambio de control. No introduzca credenciales.",
    "Explanation retained with the control change. Do not enter credentials.",
  ],
  "Filtrar trazas": [
    "Busca en las trazas cargadas por identificador, tipo, estado, proveedor, modelo o función. No ejecuta inferencias.",
    "Search loaded traces by identifier, type, status, provider, model or function. Does not run inference.",
  ],
  "Actualizar cada 30 s": [
    "Refresca lecturas cuando esta pestaña está visible, no al editar controles. No consulta un modelo LLM.",
    "Refreshes readings while this tab is visible, not while editing controls. Does not query an LLM.",
  ],
  "Versión del corpus": [
    "Conjunto de situaciones de evaluación seleccionado. Solo un borrador editable admite cambios; el histórico congelado se conserva.",
    "Selected set of evaluation situations. Only an editable draft allows changes; frozen history is retained.",
  ],
  Título: [
    "Nombre descriptivo del escenario, no una instrucción para el asistente.",
    "Descriptive scenario name, not an assistant instruction.",
  ],
  "Primer mensaje del escenario": [
    "Mensaje público que inicia el episodio. Debe respetar la información permitida al usuario.",
    "Public message starting the episode. Must respect information available to the user.",
  ],
  "Objetivo privado del usuario simulado": [
    "Meta del emulador; no se entrega al asistente evaluado. No debe revelar estados que el usuario no puede conocer.",
    "Emulator goal; not delivered to the evaluated assistant. Must not reveal states unavailable to the user.",
  ],
  "Resultados aceptables (uno por línea)": [
    "Desenlaces permitidos del escenario, incluidos rechazos legítimos. No obliga a forzar una reserva.",
    "Allowed scenario outcomes, including legitimate refusals. Does not require forcing a booking.",
  ],
  "Motivo para congelar": [
    "Justificación para fijar una revisión del corpus. No autoriza su ejecución live.",
    "Rationale for freezing a corpus revision. Does not authorize live execution.",
  ],
  Cohorte: [
    "Tamaño candidato de la evaluación. Seleccionarlo no acredita capacidad ni inicia el lote.",
    "Candidate evaluation size. Selecting it does not establish capacity or start a batch.",
  ],
  "Semilla (vacía = aleatoria, guardada al crear)": [
    "Controla la selección reproducible de muestras para revisión. Vacía genera una semilla que se conserva.",
    "Controls reproducible review sample selection. Empty generates a retained seed.",
  ],
  "Máximo de muestras (vacío = todas)": [
    "Tope de muestras de la sesión de revisión, no de episodios ejecutados ni de cuota.",
    "Review-session sample cap, not executed episodes or quota.",
  ],
  "Conjuntos de revisión": [
    "Episodios existentes que se incluirán en una sesión de revisión. Seleccionar no ejecuta ni vuelve a puntuar el histórico.",
    "Existing episodes included in a review session. Selecting does not execute or rescore history.",
  ],
  Buscar: [
    "Busca en las muestras de la sesión actual sin cambiar evidencias ni valoraciones.",
    "Searches samples in the current session without changing evidence or scores.",
  ],
  Gestión: [
    "Filtra muestras por operación administrativa, no crea una operación nueva.",
    "Filters samples by administrative operation; does not create a new operation.",
  ],
  "Motivo del desacuerdo": [
    "Explica la discrepancia humana con una propuesta IA, sin convertirla automáticamente en la valoración final.",
    "Explains human disagreement with an AI proposal without automatically making it the final assessment.",
  ],
  "JSON de propuesta IA": [
    "Importa una propuesta estructurada independiente. No sustituye la firma ni la revisión humana.",
    "Imports an independent structured proposal. Does not replace signature or human review.",
  ],
  "Veredicto material final": [
    "Conclusión tras revelar los efectos internos. No sobrescribe la primera pasada ciega.",
    "Conclusion after disclosing internal effects. Does not overwrite the first blind pass.",
  ],
  "Justificación del veredicto": [
    "Razones basadas en evidencia interna para el veredicto material.",
    "Reasons grounded in internal evidence for the material verdict.",
  ],
  "Referencias post-revelación (separadas por comas)": [
    "Identificadores de evidencia interna autorizada en la segunda pasada, separados por comas.",
    "Identifiers of internal evidence authorized in the second pass, comma-separated.",
  ],
  "Notas generales": [
    "Observaciones de la muestra revisada; no cambian su conversación ni sus efectos.",
    "Observations for the reviewed sample; do not change its conversation or effects.",
  ],
  Severidad: [
    "Gravedad adjudicada a la incidencia observada, independiente de la puntuación de cada dimensión.",
    "Adjudicated severity of the observed issue, independent of individual dimension scores.",
  ],
  "Etiquetas (separadas por comas)": [
    "Categorías para organizar la revisión; no son puntuaciones.",
    "Categories organizing the review; not scores.",
  ],
  "Marcas de duda (separadas por comas)": [
    "Aspectos que requieren comprobación; no convierten una ausencia de evidencia en un fallo demostrado.",
    "Aspects requiring verification; do not turn missing evidence into a proven failure.",
  ],
  Valoración: [
    "Puntuación de la dimensión según rúbrica. N/A significa no aplicable; N/E significa no evaluada.",
    "Dimension score according to the rubric. N/A means not applicable; N/E means not evaluated.",
  ],
  "Motivo de no aplicabilidad": [
    "Justifica por qué esta dimensión no aplica al recorrido concreto.",
    "Explains why this dimension does not apply to the specific trajectory.",
  ],
  "Referencias (una por línea; deben aparecer en la lista de evidencia)": [
    "Referencias verificables de la evidencia disponible, una por línea. No admita referencias que no están en la lista.",
    "Verifiable references to available evidence, one per line. Do not admit references absent from the list.",
  ],
  "Justificación breve": [
    "Explicación de la puntuación con hechos visibles o autorizados en la pasada actual.",
    "Score explanation using facts visible or authorized in the current pass.",
  ],
  "Filtrar eventos": [
    "Busca por acción, cuenta o recurso entre los eventos cargados. No consulta todo el historial del sistema.",
    "Searches action, account or resource among loaded events. Does not query the entire system history.",
  ],
  "Confirmación explícita": [
    "Frase exacta exigida para la acción seleccionada. No acepta una respuesta afirmativa genérica.",
    "Exact phrase required for the selected action. A generic affirmative response is not accepted.",
  ],
};

export function adminFieldHelp(
  section: string,
  label: string,
  hint?: string,
): FieldHelp {
  const canonical =
    Object.keys(fieldDescriptions).find(
      (key) => key === label || translateText(key, "en") === label,
    ) || label;
  const model =
    label.startsWith("Modelo para ") || label.startsWith("Model for ");
  const description = model
    ? pick([
        "Modelo asignado a esta variante en la planificación; no cambia el proveedor del portal ni inicia llamadas.",
        "Model assigned to this variant in planning; does not change the portal provider or start calls.",
      ])
    : fieldDescriptions[canonical]
      ? pick(fieldDescriptions[canonical])
      : hint
        ? tx(hint)
        : pick([
            "Parámetro de la sección seleccionada; revise su valor antes de guardar o confirmar.",
            "Parameter of the selected section; review its value before saving or confirming.",
          ]);
  return {
    description,
    scope: pick(sectionHelp[section] || sectionHelp.config),
  };
}

export function adminSectionDescription(section: string) {
  return pick(sectionHelp[section] || sectionHelp.config);
}
export function providerName(value: string | undefined) {
  return value === "google"
    ? "Gemini"
    : value === "groq"
      ? "Groq"
      : (value ?? "—");
}
