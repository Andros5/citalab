import { Download, ExternalLink, Network } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ErrorState, Skeleton, Tabs } from "../../components";
import { tx } from "../../i18n";
import "./architecture.css";

// Función y no constante: así los textos se traducen con el idioma activo en cada render.
const diagramList = () => [
  {
    value: "sistema",
    label: "01 · Sistema",
    title: "De la interfaz a los datos",
    description:
      "Un prototipo local con responsabilidades separadas. No es un despliegue de microservicios ni una integración sanitaria real.",
    steps: [
      "React presenta el asistente, la agenda y las herramientas de investigación. FastAPI comprueba sesión, rol y acceso al recurso.",
      "PortalService coordina trabajos y turnos. El motor agéntico recibe el almacén HIS compartido; sus herramientas validan cada operación.",
      "El portal conserva estado y trazas en SQLite. Groq y Gemini son los proveedores LLM; las llamadas remotas pueden pausarse desde Administración.",
    ],
  },
  {
    value: "agentes",
    label: "02 · Cinco agentes",
    title: "El LLM propone; el ejecutor decide si puede hacerlo",
    description:
      "M5 es la arquitectura principal. Las flechas muestran responsabilidades e invocaciones, no cinco pasos obligatorios ni cinco procesos independientes.",
    steps: [
      "Orquestación propone una acción estructurada. El grafo comprueba catálogo de acciones, dependencias, presupuesto y estado antes de ejecutarla.",
      "Contexto interpreta intención y entidades; perfiles trabaja con preferencias autorizadas; cumplimiento emite consejo semántico; personalización redacta dentro de un contrato.",
      "Los controles deterministas de identidad, permisos, confirmación e integridad no se delegan al modelo. Las llamadas y sus resultados son observables, no el razonamiento interno del LLM.",
    ],
  },
  {
    value: "reserva",
    label: "03 · Una reserva",
    title: "Dos turnos y una confirmación explícita",
    description:
      "Secuencia conceptual de una reserva: se omiten el sondeo de trabajos y las llamadas internas. No es una traza en vivo ni una medición de latencia.",
    steps: [
      "La petición debe concretar un servicio compatible. El sistema consulta huecos y ofrece una propuesta: todavía no bloquea ni reserva el intervalo.",
      "La confirmación inicia un nuevo turno. Cambiar servicio o modalidad invalida la oferta anterior y exige otra propuesta.",
      "Al escribir se revalidan permisos, oferta y disponibilidad bajo bloqueo. La idempotencia evita duplicados; un conflicto nunca se presenta como una reserva exitosa.",
    ],
  },
] as const;

type DiagramId = ReturnType<typeof diagramList>[number]["value"];
type Catalog = Record<DiagramId, { title: string; artifact_sha256: string }>;
function isCatalog(value: unknown): value is Catalog {
  if (!value || typeof value !== "object") return false;
  return diagramList().every(({ value: key }) => {
    const entry = (value as Record<string, unknown>)[key];
    return (
      !!entry &&
      typeof entry === "object" &&
      "title" in entry &&
      typeof entry.title === "string" &&
      "artifact_sha256" in entry &&
      typeof entry.artifact_sha256 === "string" &&
      /^[a-f0-9]{64}$/.test(entry.artifact_sha256)
    );
  });
}

function DiagramFrame({ id, title }: { id: DiagramId; title: string }) {
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (loaded) return;
    const timer = window.setTimeout(() => setFailed(true), 15000);
    return () => window.clearTimeout(timer);
  }, [loaded]);
  return (
    <div className={`architecture-viewer architecture-viewer-${id}`}>
      {!loaded && !failed && <p role="status">Cargando diagrama local…</p>}
      {failed && (
        <p role="alert">
          El visor no ha respondido. Prueba a recargar los diagramas o consulta
          la explicación de abajo.
        </p>
      )}
      <iframe
        title={`Vista previa del diagrama: ${title}`}
        src={`/architecture/${id}.html?embed=1`}
        sandbox="allow-scripts allow-downloads"
        referrerPolicy="no-referrer"
        onLoad={() => {
          setLoaded(true);
          setFailed(false);
        }}
        onError={() => setFailed(true)}
      />
    </div>
  );
}

// Los diagramas son ficheros estáticos de web/public/architecture (copiados a dist al
// compilar). El manifiesto registra el hash de cada artefacto generado con Archify.
function useDiagramCatalog() {
  const [data, setData] = useState<Catalog | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    fetch("/architecture/manifest.json", { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`))))
      .then((manifest: { diagrams?: unknown }) => {
        if (!isCatalog(manifest.diagrams)) throw new Error("La respuesta recibida no tiene el formato esperado.");
        setData(manifest.diagrams);
      })
      .catch((e: Error) => {
        if (!controller.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [attempt]);
  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  return { data, error, loading, retry };
}

export function ArchitectureGuide() {
  const [selected, setSelected] = useState<DiagramId>("sistema");
  const { data, error, loading, retry } = useDiagramCatalog();
  const diagrams = diagramList();
  const diagram = diagrams.find((item) => item.value === selected)!;
  return (
    <section
      id="arquitectura"
      className="panel architecture-guide"
      aria-labelledby="architecture-title"
    >
      <div className="architecture-heading">
        <Network size={28} aria-hidden="true" />
        <div>
          <p className="eyebrow">ARQUITECTURA / MAPAS EXPLICATIVOS</p>
          <h2 id="architecture-title">Entiende qué ocurre detrás del chat</h2>
          <p>
            Lee de izquierda a derecha: sistema, agentes y reserva.
            Documentación del prototipo, no monitorización en directo.
          </p>
        </div>
      </div>
      <Tabs
        label="Vistas de arquitectura"
        value={selected}
        onChange={(value) => setSelected(value as DiagramId)}
        items={diagrams}
      >
        <div className="architecture-intro">
          <h3>{tx(diagram.title)}</h3>
          <p>{tx(diagram.description)}</p>
        </div>
        {loading && <Skeleton label="Comprobando diagramas disponibles…" />}
        {error && (
          <ErrorState
            title="No se han podido abrir los diagramas"
            message={error}
            retry={retry}
          />
        )}
        {data && (
          <>
            <div className="architecture-actions">
              <a
                className="button secondary"
                href={`/architecture/${selected}.html`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <ExternalLink size={16} aria-hidden="true" /> Abrir visor amplio
              </a>
              <a
                className="button secondary"
                href={`/architecture/${selected}.html`}
                download={`citalab-${selected}.html`}
              >
                <Download size={16} aria-hidden="true" /> Descargar HTML
              </a>
              <button type="button" className="text-button" onClick={retry}>
                Recargar diagramas
              </button>
            </div>
            <DiagramFrame
              key={selected}
              id={selected}
              title={data[selected].title}
            />
          </>
        )}
        <details className="architecture-reading" open>
          <summary>Lectura guiada y alternativa textual</summary>
          <ol>
            {diagram.steps.map((step) => (
              <li key={step}>{tx(step)}</li>
            ))}
          </ol>
        </details>
      </Tabs>
      <div className="architecture-comparison">
        <h3>Qué cambia entre las arquitecturas</h3>
        <dl>
          <div>
            <dt>M5 · principal</dt>
            <dd>
              Cinco roles especializados con LLM y coordinación adaptativa.
            </dd>
          </div>
          <div>
            <dt>S1 · comparación</dt>
            <dd>
              Un rol LLM unificado con acceso equivalente a herramientas y
              controles.
            </dd>
          </div>
          <div>
            <dt>H · comparación</dt>
            <dd>
              Grafo híbrido: LLM en contexto y redacción; otras fases
              deterministas.
            </dd>
          </div>
        </dl>
        <p>
          Compartir controles permite comparar utilidad, coste y errores. Añadir
          agentes no demuestra por sí solo una mejora.
        </p>
      </div>
      <p className="architecture-footnote">
        La vista previa muestra el mapa sin barras ni paneles superpuestos. Abre
        el visor amplio para usar zoom, explorar componentes y exportar.
        Generado localmente con{" "}
        <a
          href="https://github.com/tt-a1i/archify"
          target="_blank"
          rel="noopener noreferrer"
        >
          Archify
        </a>
        . Texto en español; controles del visor en inglés. Usa + / − para
        ampliar, 0 para restablecer y Escape para cerrar paneles. En móvil, abre
        el visor amplio o utiliza la lectura guiada. El visor está aislado de tu
        sesión; el portapapeles y algunas exportaciones pueden estar
        restringidos por el navegador.
      </p>
    </section>
  );
}
