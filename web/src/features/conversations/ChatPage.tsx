import {
  ArrowRight,
  Bot,
  Clock3,
  MessageSquare,
  Plus,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { lazy, Suspense, useState } from "react";
import { useParams } from "react-router-dom";
import { dateTime, roleLabels } from "../../api";
import {
  ErrorState,
  Field,
  JsonBlock,
  Loading,
  Notice,
  PageHeader,
  Status,
  Tabs,
} from "../../components";
import { useApp } from "../../context";
import { ConversationPreferences } from "./ConversationPreferences";
import { MessageComposer } from "./MessageComposer";
import { MessageTimeline } from "./MessageTimeline";
import { NewConversationDialog } from "./NewConversationDialog";
import { OperationPanel } from "./OperationPanel";
import { useConversation } from "./useConversation";
import { getUiLanguage, tx } from "../../i18n";
import { useResponseLanguage } from "./useResponseLanguage";

const CallInspector = lazy(() =>
  import("../inspector/CallInspector").then((module) => ({
    default: module.CallInspector,
  })),
);

export function ChatPage() {
  const { id } = useParams();
  // Cada ruta conserva su propio estado: las respuestas de la anterior no
  // deben reemplazar ni enviar mensajes sobre la conversación recién abierta.
  return <ConversationPage key={id || "new"} />;
}

function ConversationPage() {
  const { id } = useParams();
  const { bootstrap } = useApp();
  const staff = bootstrap.user.role !== "patient";
  const {
    conversation,
    job,
    error,
    loading,
    busy,
    uncertain,
    refresh,
    send: submit,
    retryPending,
    polling,
    outgoing,
  } = useConversation(id);
  useResponseLanguage(conversation?.id, conversation?.turns.at(-1), busy);
  const [newDialog, setNewDialog] = useState(false);
  const [input, setInput] = useState("");
  const [inspect, setInspect] = useState(true);
  const [inspectTab, setInspectTab] = useState("calls");
  const [turnSelection, setTurnSelection] = useState("latest");
  const send = async (
    action: "message" | "confirm" | "discard",
    message = input,
  ) => {
    setTurnSelection("latest");
    if (await submit(action, message)) setInput("");
  };
  const selectedTurn =
    turnSelection === "latest"
      ? conversation?.turns.at(-1)
      : conversation?.turns.find((turn) => turn.id === turnSelection);
  const failedAttempt = conversation?.failed_attempts?.find(
    (attempt) => attempt.id === turnSelection,
  );
  const calls = busy
    ? job?.calls || []
    : failedAttempt?.calls || selectedTurn?.calls || job?.calls || [];
  const state = selectedTurn?.state || {};
  const events = busy
    ? job?.events
    : failedAttempt?.events || selectedTurn?.events;
  return (
    <>
      <PageHeader
        eyebrow="TRABAJO DIARIO / ASISTENTE"
        title="Asistente de citas"
        description="Conversación administrativa, decisiones observables y confirmación bajo tu control."
        actions={
          <>
            {id && (
              <button onClick={() => setNewDialog(true)}>
                <Plus size={17} /> Nueva conversación
              </button>
            )}
            {staff && conversation && (
              <button
                className="icon-button"
                aria-label={inspect ? "Ocultar inspector" : "Mostrar inspector"}
                aria-pressed={inspect}
                onClick={() => setInspect(!inspect)}
              >
                <SlidersHorizontal size={18} />
              </button>
            )}
          </>
        }
      />
      {error && conversation && (
        <Notice tone="error">
          {error}{" "}
          <button type="button" onClick={() => void refresh()}>
            Actualizar estado
          </button>
        </Notice>
      )}
      {conversation?.status === "SCENARIO_UPDATED" && (
        <Notice>
          El escenario de agendas ha cambiado. Conservamos el historial, pero la
          propuesta anterior ya no puede confirmarse. Indica de nuevo el
          servicio y las condiciones para consultar una oferta vigente.
        </Notice>
      )}
      {uncertain && (
        <Notice>
          La respuesta no llegó. La operación podría haberse aceptado.
          <button type="button" onClick={() => void refresh()}>
            Consultar resultado
          </button>
          <button type="button" onClick={() => void retryPending()}>
            Recuperar el mismo intento
          </button>
        </Notice>
      )}
      {polling.error && (
        <Notice>
          Seguimiento interrumpido: {polling.error}
          <button type="button" onClick={polling.retry}>
            Reanudar seguimiento
          </button>
        </Notice>
      )}
      {conversation?.read_only && (
        <Notice>
          Revisión de otra cuenta: puedes consultar la evidencia, pero no enviar
          mensajes ni modificar la conversación.
        </Notice>
      )}
      {!id ? (
        <div className="assistant-start">
          <section className="start-primary">
            <span className="section-index">TU ESPACIO DE PRUEBAS</span>
            <h2>
              Empieza por una gestión.
              <br />
              Explora cada decisión.
            </h2>
            <p>
              Inicia sesión con un perfil sintético y sigue la reserva desde la
              petición hasta su confirmación. La agenda es la fuente de verdad.
            </p>
            <button className="primary" onClick={() => setNewDialog(true)}>
              Iniciar una conversación <ArrowRight size={18} />
            </button>
            <div className="start-example">
              <MessageSquare size={19} />
              <span>
                «Quiero reservar una cita por la mañana»
                <small>Ejemplo de petición administrativa</small>
              </span>
            </div>
          </section>
          <section className="start-secondary">
            <p className="eyebrow">ARQUITECTURA PRINCIPAL · M5</p>
            <h3>
              Cinco especialidades.
              <br />
              Un núcleo de control.
            </h3>
            <ol className="roles-list">
              {[
                "context",
                "profile",
                "compliance",
                "personalization",
                "orchestration",
              ].map((role, index) => (
                <li key={role}>
                  <span>{index + 1}</span>
                  <div>
                    <strong>{tx(roleLabels[role])}</strong>
                    <small>
                      {tx(
                        [
                          "Interpreta la petición administrativa",
                          "Consulta preferencias autorizadas",
                          "Examina riesgos y límites",
                          "Adapta la explicación",
                          "Coordina acciones permitidas",
                        ][index],
                      )}
                    </small>
                  </div>
                </li>
              ))}
            </ol>
            <div className="kernel">
              <ShieldCheck size={18} /> Permisos y escrituras validados por
              código
            </div>
          </section>
        </div>
      ) : !conversation ? (
        loading ? (
          <Loading />
        ) : (
          <ErrorState
            message={error || "Conversación no disponible."}
            retry={() => void refresh()}
          />
        )
      ) : (
        <>
          <div className="session-strip">
            <div>
              <span className="avatar small">
                {conversation.subject_name.slice(0, 2).toUpperCase()}
              </span>
              <strong>{conversation.subject_name}</strong>
              <span className="muted">
                {staff ? "Sesión de laboratorio" : "Mi sesión"}
              </span>
            </div>
            <div>
              <span className="architecture-tag">
                {conversation.architecture}
              </span>
              <span>
                {conversation.provider === "offline"
                  ? "Sin API · prueba de contratos"
                  : `${conversation.provider} · LLM`}
              </span>
              <Status value={busy ? "running" : conversation.status} />
            </div>
          </div>
          <div
            className={`chat-layout ${staff && inspect ? "with-inspector" : ""}`}
          >
            <section className="chat-panel">
              <div className="chat-panel-heading">
                <Bot size={20} />
                <strong>Conversación</strong>
                <span>
                  {conversation.turn_count}{" "}
                  {conversation.turn_count === 1 ? "turno" : "turnos"}
                </span>
              </div>
              <ConversationPreferences
                conversation={conversation}
                busy={busy}
                onSaved={refresh}
                canPersistProfile={bootstrap.user.role === "patient"}
              />
              <MessageTimeline
                outgoing={outgoing}
                conversation={conversation}
                busy={busy}
                job={job}
                calls={calls}
              />
              <OperationPanel
                conversation={conversation}
                busy={busy}
                onConfirm={() => void send("confirm")}
                onDiscard={() => void send("discard")}
              />
              <MessageComposer
                value={input}
                busy={busy}
                disabled={Boolean(
                  conversation.archived || conversation.read_only,
                )}
                onChange={setInput}
                onSubmit={() => void send("message")}
              />
              {!conversation.turns.length && (
                <div className="quick-requests">
                  {(getUiLanguage() === "en"
                    ? [
                        "I want to book an appointment in the morning",
                        "Do not use my preferences",
                        "I want to speak to a person",
                      ]
                    : [
                        "Quiero reservar una cita por la mañana",
                        "No uses mis preferencias",
                        "Quiero hablar con una persona",
                      ]
                  ).map((text) => (
                    <button
                      disabled={busy}
                      onClick={() => setInput(text)}
                      key={text}
                    >
                      {text}
                    </button>
                  ))}
                </div>
              )}
            </section>
            {staff && inspect && (
              <aside className="inspector" aria-label="Inspector de ejecución">
                <header>
                  <span className="eyebrow">OBSERVABILIDAD</span>
                  <h2>Dentro de la ejecución</h2>
                  <p>
                    Selecciona un turno o intento fallido. Sin razonamiento
                    interno.
                  </p>
                  <Field label="Ejecución que deseas inspeccionar">
                    <select
                      value={turnSelection}
                      disabled={busy}
                      onChange={(e) => setTurnSelection(e.target.value)}
                    >
                      <option value="latest">Último turno</option>
                      {conversation.turns.map((turn) => (
                        <option key={turn.id} value={turn.id}>
                          Turno {turn.number} · {turn.status}
                        </option>
                      ))}
                      {conversation.failed_attempts?.map((attempt) => (
                        <option key={attempt.id} value={attempt.id}>
                          Intento {attempt.status} · {dateTime(attempt.at)}
                        </option>
                      ))}
                    </select>
                  </Field>
                  {failedAttempt && (
                    <Notice tone="error">
                      {failedAttempt.error ||
                        "Ejecución interrumpida. No se reenvió automáticamente."}
                    </Notice>
                  )}
                </header>
                <div className="inspector-metrics">
                  <div>
                    <strong>{calls.length}</strong>
                    <span>Llamadas</span>
                  </div>
                  <div>
                    <strong>
                      {calls.some((c) => c.total_tokens != null)
                        ? calls.reduce((n, c) => n + (c.total_tokens ?? 0), 0)
                        : "n/d"}
                    </strong>
                    <span>
                      {calls.every((c) => c.total_tokens != null)
                        ? "Tokens conocidos"
                        : "Tokens · medida parcial"}
                    </span>
                  </div>
                  <div>
                    <strong>
                      {calls.some((c) => c.latency_ms != null)
                        ? `${(
                            calls.reduce((n, c) => n + (c.latency_ms || 0), 0) /
                            1000
                          ).toFixed(1)} s`
                        : "n/d"}
                    </strong>
                    <span>
                      {calls.every((c) => c.latency_ms != null)
                        ? "Tiempo de API"
                        : "Tiempo · medida parcial"}
                    </span>
                  </div>
                </div>
                <Tabs
                  label="Vistas del inspector"
                  value={inspectTab}
                  onChange={setInspectTab}
                  items={[
                    { value: "calls", label: "LLMs" },
                    { value: "flow", label: "Flujo" },
                    { value: "decisions", label: "Decisiones" },
                    { value: "controls", label: "Controles" },
                  ]}
                >
                  {inspectTab === "calls" && (
                    <Suspense fallback={<Loading />}>
                      <CallInspector
                        calls={calls}
                        executionTrace={
                          (state.execution_trace as Record<string, unknown>[]) || []
                        }
                      />
                    </Suspense>
                  )}
                  {inspectTab === "flow" && (
                    <>
                      <h3 className="minor-heading">
                        Acciones del orquestador
                      </h3>
                      <JsonBlock
                        data={state.agent_steps || []}
                        label="Acciones del orquestador"
                      />
                      <h3 className="minor-heading">
                        Herramientas y resultado FHIR
                      </h3>
                      <JsonBlock
                        data={{
                          tools: state.tool_calls || [],
                          results: state.tool_results || [],
                          result: state.tool_result || {},
                          chronology: state.execution_trace || [],
                        }}
                      />
                      {events && (
                        <ol className="events">
                          {events.map((event, index) => (
                            <li key={index}>
                              <Clock3 size={14} />
                              <span>
                                <strong>{event.kind}</strong>
                                <small>{event.detail}</small>
                              </span>
                            </li>
                          ))}
                        </ol>
                      )}
                    </>
                  )}
                  {inspectTab === "decisions" && (
                    <>
                      <Notice>
                        Evidencia estructurada y valores normalizados. CitaLab no
                        solicita ni reconstruye razonamiento privado del modelo.
                      </Notice>
                      <h3 className="minor-heading">Actos y restricciones</h3>
                      <JsonBlock
                        data={{
                          turn_plan: state.turn_plan || {},
                          temporal: state.temporal_constraints || {},
                          tasks: state.conversation_tasks || [],
                          interpreted_entities: state.entities || {},
                        }}
                        label="Decisiones normalizadas del turno"
                      />
                      <h3 className="minor-heading">Propuesta y resultado</h3>
                      <JsonBlock
                        data={{
                          operation_proposal: state.operation_proposal || {},
                          booking_offer: state.proposed_offer || {},
                          invalidation:
                            state.proposal_invalidation_reason || null,
                          response_plan: state.response_plan || {},
                          receipt: state.operation_receipt || {},
                        }}
                        label="Propuesta versionada y recibo observable"
                      />
                    </>
                  )}
                  {inspectTab === "controls" && (
                    <>
                      <Notice>
                        Las decisiones del LLM no conceden permisos. Cada acceso
                        pasa por el núcleo de políticas.
                      </Notice>
                      <JsonBlock
                        data={{
                          entry: state.compliance_entry_decision,
                          decision: state.compliance_decision,
                          semantic: state.semantic_review,
                          error: state.error_code,
                          fallback: state.personalization,
                          audit: state.audit_events,
                          provenance: conversation.provenance,
                          turn_scenario: selectedTurn?.scenario,
                          source_sha256: selectedTurn?.source_sha256,
                          data_before_sha256: selectedTurn?.data_before_sha256,
                          data_after_sha256: selectedTurn?.data_after_sha256,
                        }}
                      />
                    </>
                  )}
                </Tabs>
                <div className="inspector-footer">
                  Configuración r{conversation.config_version} ·{" "}
                  {conversation.diagnostic
                    ? "Diagnóstico activado"
                    : "Contenido de diagnóstico desactivado"}
                </div>
              </aside>
            )}
          </div>
        </>
      )}
      {newDialog && <NewConversationDialog close={() => setNewDialog(false)} />}
    </>
  );
}
