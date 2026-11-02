import { useLayoutEffect, useRef, useState } from "react";
import { roleLabels, type Call, type Conversation, type Job } from "../../api";
import { getUiLanguage, tx } from "../../i18n";
import { AssistantText } from "./assistantText";
import { ExecutionProgress } from "./ExecutionProgress";
import type { OutgoingMessage } from "./useConversation";

export function MessageTimeline({
  conversation,
  busy,
  job,
  calls,
  outgoing = null,
}: {
  conversation: Conversation;
  busy: boolean;
  job: Job | null;
  calls: Call[];
  outgoing?: OutgoingMessage | null;
}) {
  const messageBox = useRef<HTMLDivElement>(null);
  const followEnd = useRef(true);
  const anchor = useRef<{ height: number; top: number } | null>(null);
  const [visibleCount, setVisibleCount] = useState(50);
  const [newMessages, setNewMessages] = useState(false);
  useLayoutEffect(() => {
    const box = messageBox.current;
    if (!box) return;
    if (anchor.current) {
      box.scrollTop =
        anchor.current.top + (box.scrollHeight - anchor.current.height);
      anchor.current = null;
    } else if (followEnd.current)
      box.scrollTo?.({ top: box.scrollHeight, behavior: "instant" });
    else setNewMessages(true);
  }, [conversation.turn_count, busy, visibleCount, outgoing]);
  return (
    <>
      <div
        ref={messageBox}
        onScroll={() => {
          const box = messageBox.current;
          if (box) {
            followEnd.current =
              box.scrollHeight - box.scrollTop - box.clientHeight < 80;
            if (followEnd.current) setNewMessages(false);
          }
        }}
        className="messages"
        role="log"
        aria-label="Mensajes de la conversación"
      >
        {conversation.turns.length > visibleCount && (
          <button
            type="button"
            onClick={() => {
              const box = messageBox.current;
              if (box)
                anchor.current = {
                  height: box.scrollHeight,
                  top: box.scrollTop,
                };
              setVisibleCount((v) => v + 50);
            }}
          >
            Cargar 50 turnos anteriores (
            {conversation.turns.length - visibleCount} pendientes)
          </button>
        )}
        <div className="message assistant">
          <span className="message-author">{tx("AVISO INICIAL · ")}{conversation.provider === "offline" ? tx("SIMULACIÓN SIN LLM") : tx("IA")}</span>
          {(conversation.welcome?.text || tx("Puedo ayudarte a reservar una cita en este simulador. No realizo valoración clínica. No introduzcas datos reales; puedes pedir atención humana en cualquier momento."))
            .split(/\n\s*\n/)
            .map((paragraph, index) => <p key={index}>{paragraph}</p>)}
        </div>
        {conversation.turns.slice(-visibleCount).map((turn) => (
          <div key={turn.id} className="turn">
            <div className="message user">
              <span className="message-author">
                {conversation.subject_name.toUpperCase()}
              </span>
              <p>{turn.request}</p>
            </div>
            <div className="message assistant">
              <span className="message-author">
                ASISTENTE · TURNO {turn.number}
              </span>
              <AssistantText text={turn.response} />
              {(turn.response_metadata?.recovery || turn.execution_summary?.programmed_recovery) && (
                <small role="status">El asistente utilizó una respuesta de recuperación programada.</small>
              )}
              {turn.execution_summary?.transport_recovered && !turn.response_metadata?.recovery && !turn.execution_summary?.programmed_recovery && (
                <small role="status">Respuesta completada tras un reintento del proveedor.</small>
              )}
            </div>
          </div>
        ))}
        {outgoing && !conversation.turns.some(turn =>
          outgoing.job_id && turn.job_id ? turn.job_id === outgoing.job_id : turn.number > outgoing.expected_turn
        ) && <div className="message user" data-request-id={outgoing.request_id}>
          <span className="message-author">{conversation.subject_name.toUpperCase()}</span>
          <p>{outgoing.message}</p>
          {outgoing.status === "failed" && <small role="status">No se pudo completar el envío.</small>}
          {outgoing.status === "uncertain" && <small role="status">Envío pendiente de verificar.</small>}
        </div>}
        {busy && !["uncertain", "failed"].includes(outgoing?.status ?? "") && (
          <div className="working-message" role="status">
            <span className="working-dot" />
            {job?.status === "queued"
              ? tx("Esperando turno de ejecución…")
              : `${tx("Procesando")}${calls.at(-1)?.agent ? ` · ${tx(roleLabels[calls.at(-1)!.agent] || (getUiLanguage() === "en" ? "agent" : "agente"))}` : ` ${tx("la petición")}`}…`}
          </div>
        )}
        {busy && !["uncertain", "failed"].includes(outgoing?.status ?? "") && calls.length > 0 && <ExecutionProgress calls={calls} job={job} />}
      </div>
      {newMessages && (
        <div className="jump-latest">
          <button
            type="button"
            onClick={() => {
              const box = messageBox.current;
              box?.scrollTo?.({ top: box.scrollHeight });
              followEnd.current = true;
              setNewMessages(false);
            }}
          >
            Ir a los mensajes nuevos
          </button>
        </div>
      )}
    </>
  );
}
