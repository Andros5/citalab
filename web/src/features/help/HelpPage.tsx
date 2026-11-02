import { BadgeCheck, Bot, ClipboardCheck, Database, Gavel, History, KeyRound, ShieldCheck, UserRound } from "lucide-react";
import { useState } from "react";
import { api } from "../../api";
import { Field, Notice, PageHeader } from "../../components";
import { useApp } from "../../context";
import { ArchitectureGuide } from "./ArchitectureGuide";
import { tx } from "../../i18n";
import "./help.css";

export function HelpPage() {
  const { bootstrap } = useApp();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState("");
  return (
    <>
      <PageHeader
        eyebrow="RECURSOS / GUÍA DE USO"
        title="Un entorno para entender tu sistema"
        description="Del primer acceso a la evidencia de investigación, sin confundir una demostración con un servicio sanitario real."
      />
      <nav className="architecture-actions" aria-label="Secciones de ayuda">
        <a href="#arquitectura">Arquitectura</a>
        <a href="#evaluacion">Cómo se evalúa</a>
        <a href="#configuracion">Configuración</a>
        <a href="#recorrido">Recorrido</a>
        <a href="#codigo">Código</a>
        <a href="#mi-codigo">Mi código de acceso</a>
      </nav>
      <ArchitectureGuide />
      <EvaluationGuide />
      <ConfigurationGuide />
      <section id="recorrido" className="panel guide">
        <h2>Recorrido recomendado</h2>
        <ol>
          {[
            [
              "Prepara el conjunto",
              "En Agenda y datos, revisa los perfiles y los huecos disponibles. Antes de modificar datos, crea una instantánea desde Administración.",
            ],
            [
              "Elige qué vas a probar",
              "En Administración, comprueba proveedor, límites y prompts. M5 es la arquitectura principal; S1 y H son los comparadores. Puedes pausar las llamadas remotas en cualquier momento.",
            ],
            [
              "Abre una conversación",
              "El paciente entra con su propia cuenta. El investigador puede elegir un perfil sintético y un motor; esta simulación queda identificada como sesión de laboratorio.",
            ],
            [
              "Inspecciona la ejecución",
              "Abre cada llamada para ver su plantilla, versión, contrato, tokens y latencia. Si necesitas entradas y salidas, activa diagnóstico al crear la conversación.",
            ],
            [
              "Confirma y contrasta",
              "La propuesta no es una reserva. Pulsa Confirmar reserva, Confirmar cambio de cita o Confirmar cancelación, o responde «sí», y comprueba la cita en Agenda y datos. Los formularios de cambiar y cancelar de la agenda son un canal distinto al asistente.",
            ],
            [
              "Conserva evidencia",
              "Reabre la conversación desde el historial y exporta su registro. Las pruebas automáticas comprueban contratos y controles; la calidad conversacional se mide en Evaluación.",
            ],
          ].map(([title, text]) => (
            <li key={title}>
              <div>
                <h3>{tx(title)}</h3>
                <p>{tx(text)}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
      <section id="codigo" className="panel guide">
        <h2>Cómo seguir una petición en el código</h2>
        <p>
          La ruta mínima es: interfaz React → API FastAPI → PortalService →
          grafo M5, S1 o H → políticas deterministas → simulador FHIR →
          historial SQLite. El modelo propone; el núcleo autoriza; el HIS
          ejecuta; el personalizador comunica hechos ya comprobados.
        </p>
        <p>
          En el repositorio, <code>docs/guia-codigo.md</code> identifica las
          funciones concretas, el orden de lectura y las pruebas que acompañan
          cada frontera.
        </p>
      </section>
      <div className="info-columns">
        <section>
          <h2>Tres servicios, sin reservas implícitas</h2>
          <p>
            En Administración → Escenario comprueba qué paquete está activo.
            Multiagenda permite medicina de familia, pediatría y enfermería con
            huecos presenciales. El escenario histórico conserva una sola
            agenda.
          </p>
          <p>
            Prueba «Quiero una cita de enfermería por la tarde». Si omites el
            servicio, el asistente te lo preguntará; responde «enfermería».
            «Mejor pediatría» descarta la propuesta anterior y necesita otra
            confirmación. Pedir teléfono no genera disponibilidad ficticia.
          </p>
          <p>
            Los filtros Servicio y Agenda solo cambian la vista del calendario.
            Cambiar una cita ya reservada conserva su servicio. Pediatría no
            implica permiso para actuar por un menor ni comprueba elegibilidad
            clínica.
          </p>
          <p>
            Si tu base conserva el escenario antiguo, el administrador puede
            previsualizar la ampliación, revisar los recursos y confirmarla.
            Ante un conflicto no se sobrescriben datos. Una restauración puede
            devolver el escenario histórico.
          </p>
        </section>
        <section>
          <ShieldCheck />
          <h2>Límites y privacidad</h2>
          <p>
            Solo perfiles sintéticos. No hay conexión con ClicSalud+, SAS,
            DIRAYA ni servicios de identidad de la Administración. El login es
            real dentro del prototipo, pero no representa identificación
            sustancial eIDAS.
          </p>
          <p>
            Se filtran ciertos identificadores y señales clínicas; esto no
            garantiza anonimización de texto libre. No introduzcas datos reales.
            Los prompts y resultados son datos no confiables y nunca se ejecutan
            como código.
          </p>
        </section>
        <section>
          <History />
          <h2>Qué se conserva</h2>
          <p>
            Conversaciones, configuraciones, llamadas y agenda residen en SQLite
            local. El diagnóstico es opcional y tiene una retención más corta.
            No se registra razonamiento interno de modelos.
          </p>
          <p>
            Los datos de ejecución, códigos iniciales y exportaciones no se
            suben a Git. Las copias descargadas son responsabilidad del
            investigador. Este entorno no está preparado para exposición
            pública.
          </p>
        </section>
      </div>
      <section className="panel">
        <h2>Accesibilidad y navegación</h2>
        <p>
          Todos los controles principales admiten teclado. Usa Tab para navegar,
          Enter o Espacio para activar y Escape para cerrar diálogos. Existe un
          enlace de salto al contenido. Se respeta la preferencia de reducir
          animaciones del sistema.
        </p>
        <p>
          No se afirma conformidad certificada WCAG: la revisión automática y
          visual no sustituye pruebas con tecnologías de apoyo y personas
          usuarias.
        </p>
      </section>
      <section id="mi-codigo" className="panel account-security">
        <h2>Cambiar mi código de acceso</h2>
        <p>
          {bootstrap.user.username} · Se cerrarán todas tus sesiones tras
          guardar.
        </p>
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            try {
              await api("/auth/password", "POST", {
                current_password: current,
                new_password: next,
              });
              setCurrent("");
              setNext("");
              window.dispatchEvent(new Event("session-expired"));
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          <div className="form-grid">
            <Field label="Código actual">
              <input
                type="password"
                autoComplete="current-password"
                required
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
              />
            </Field>
            <Field label="Nuevo código (mínimo 12 caracteres)">
              <input
                type="password"
                autoComplete="new-password"
                minLength={12}
                maxLength={200}
                required
                value={next}
                onChange={(e) => setNext(e.target.value)}
              />
            </Field>
          </div>
          {error && <Notice tone="error">{error}</Notice>}
          <button className="primary">
            <KeyRound size={16} /> Cambiar código
          </button>
        </form>
      </section>
    </>
  );
}

// Del corpus congelado a la estimación final. Resume el capítulo de metodología
// de la memoria; los valores son los de la campaña final, no los del portal.
// Función y no constante: así los títulos se traducen con el idioma activo en cada render.
const pipeline = () => [
  {
    icon: Database,
    title: "1 · Corpus congelado",
    text: "276 episodios: las mismas 46 unidades en M5, S1 y H con Groq y con Gemini. Cubren reservar, consultar, cambiar, cancelar y recordatorios, con bloques de repetición, contrafactuales, estilos de persona y suplementos. Un manifiesto fija el hash del código, de los prompts y de los escenarios: si cambian, la campaña no se reanuda.",
  },
  {
    icon: UserRound,
    title: "2 · Usuario simulado",
    text: "Un modelo distinto de los evaluados (qwen3.8-27b en Groq) interpreta a la persona. Solo conoce su objetivo, su estilo y sus instrucciones; confirma pulsando el botón de la propuesta, como haría en la interfaz.",
  },
  {
    icon: BadgeCheck,
    title: "3 · Oráculo determinista",
    text: "Compara la agenda final con la esperada. Éxito integral significa objetivo alcanzado, controles respetados y respuestas fieles a lo ocurrido. Seguridad y uso de preferencias se miden aparte. Un incidente de proveedor nunca cuenta como fallo.",
  },
  {
    icon: Gavel,
    title: "4 · Jurado LLM",
    text: "Claude Sonnet 5.5 y GPT-6.1-Terra puntúan cada conversación en un proceso aislado, sin herramientas ni acceso al proyecto. Ven la misma vista ciega que el revisor humano y dan 0–3 o NA en seis dimensiones del asistente y cinco del simulador, con una cita literal que se comprueba. Un 10 % se repite para medir su consistencia.",
  },
  {
    icon: ClipboardCheck,
    title: "5 · Revisión humana ciega",
    text: "60 episodios fijados antes de ver ninguna nota del jurado y 12 de segunda pasada, al menos 48 h después. Se hace en Evaluación → Revisión humana ciega. Con ella se mide la concordancia del jurado con la revisión humana y la de la revisión consigo misma (κ ponderada). La estimación con PPI++ se descartó porque la muestra no representa toda la campaña.",
  },
] as const;

const commands = [
  ["Reanudar la campaña", "python scripts/run_independent_campaign.py"],
  ["Jurado sobre la campaña", "python -m citalab_judge judge --judge claude"],
  ["Abrir la revisión humana", "python -m citalab_judge review"],
  ["Informe de concordancia", "python -m citalab_judge report"],
] as const;

function EvaluationGuide() {
  return (
    <section id="evaluacion" className="panel guide-evaluation">
      <p className="eyebrow">{tx("EVALUACIÓN / MÉTODO")}</p>
      <h2>{tx("Cómo se evalúa CitaLab")}</h2>
      <p className="lede">
        {tx(
          "Tres fuentes independientes se combinan sin mezclarse: el oráculo mide lo que ocurrió en la agenda, el jurado puntúa la conversación en todos los episodios y la revisión humana ciega contrasta sus notas en una muestra.",
        )}
      </p>
      <ol className="pipeline">
        {pipeline().map(({ icon: Icon, title, text }) => (
          <li key={title}>
            <span className="pipeline-icon">
              <Icon size={20} aria-hidden />
            </span>
            <h3>{tx(title)}</h3>
            <p>{tx(text)}</p>
          </li>
        ))}
      </ol>
      <div className="guide-callout">
        <Bot size={20} aria-hidden />
        <p>
          {tx(
            "Mientras revisas, no abras las notas del jurado ni la pestaña Episodios de la campaña final: mostrarían arquitectura, proveedor y veredicto, y la revisión dejaría de ser ciega.",
          )}
        </p>
      </div>
      <h3>{tx("Comandos")}</h3>
      <dl className="command-list">
        {commands.map(([label, command]) => (
          <div key={command}>
            <dt>{tx(label)}</dt>
            <dd>
              <code>{command}</code>
            </dd>
          </div>
        ))}
      </dl>
      <p className="muted">
        {tx("Se ejecutan desde la raíz del proyecto con el entorno de Python activado y PYTHONPATH=src.")}
      </p>
    </section>
  );
}

const configuration = [
  ["Arquitecturas", "M5 (cinco agentes, principal) · S1 (agente único) · H (flujo híbrido)"],
  ["Modelo con Groq", "openai/gpt-oss-20b"],
  ["Modelo con Gemini", "gemini-3.5-flash-lite (Google AI Studio)"],
  ["Usuario simulado", "qwen/qwen3.8-27b (Groq)"],
  ["Temperatura", "0"],
  ["Máximo de tokens de salida", "1200 por llamada"],
  ["Intentos por llamada", "4, con espera exponencial o la indicada por Retry-After"],
  ["Espera máxima por llamada", "20 s en la campaña"],
  ["Ritmo de llamadas", "Gemini cada 4,5 s y simulador cada 2,1 s, por debajo de sus límites por minuto"],
  ["Paralelismo", "Un episodio a la vez por proveedor"],
  ["Versión de los prompts", "v3.0"],
] as const;

function ConfigurationGuide() {
  return (
    <section id="configuracion" className="panel guide-configuration">
      <p className="eyebrow">{tx("CONFIGURACIÓN / CAMPAÑA FINAL")}</p>
      <h2>{tx("Configuración del experimento")}</h2>
      <p className="lede">
        {tx(
          "Valores congelados en el manifiesto de la campaña final. El portal tiene su propia configuración en Administración (por ejemplo, 60 s de espera por llamada) y cambiarla no altera la campaña.",
        )}
      </p>
      <dl className="config-grid">
        {configuration.map(([label, value]) => (
          <div key={label}>
            <dt>{tx(label)}</dt>
            <dd>{tx(value)}</dd>
          </div>
        ))}
      </dl>
      <p className="muted">
        {tx(
          "Los tres diseños comparten herramientas, políticas, confirmación y presupuesto; solo cambia quién decide el siguiente paso. Así una diferencia de resultados se puede atribuir a la arquitectura y no a controles distintos.",
        )}
      </p>
    </section>
  );
}
