import {
  BellRing,
  CalendarCheck,
  CalendarClock,
  CalendarX,
  Check,
} from "lucide-react";
import { motion } from "motion/react";
import { Link } from "react-router-dom";
import {
  dateTime,
  type AppointmentSummary,
  type Conversation,
  type OperationProposal,
} from "../../api";

type Props = {
  conversation: Conversation;
  busy: boolean;
  onConfirm: () => void;
  onDiscard: () => void;
};

// Se construye en cada render: el plugin de traducción envuelve estos textos en tx(),
// y fuera de una función quedarían fijados en el idioma activo al cargar el módulo.
const operationCopy = () => ({
  cancel: {
    title: "Cancelación pendiente",
    confirm: "Confirmar cancelación",
    icon: CalendarX,
  },
  reschedule: {
    title: "Cambio de cita pendiente",
    confirm: "Confirmar cambio de cita",
    icon: CalendarClock,
  },
  reminder: {
    title: "Recordatorio simulado pendiente",
    confirm: "Activar recordatorio simulado",
    icon: BellRing,
  },
}) as const;

function AppointmentFacts({ value }: { value: AppointmentSummary }) {
  return (
    <dl className="appointment-facts">
      <div>
        <dt>Servicio</dt>
        <dd>{value.service_display}</dd>
      </div>
      <div>
        <dt>Fecha y hora</dt>
        <dd>{dateTime(value.start)} · Madrid</dd>
      </div>
      <div>
        <dt>Identificador</dt>
        <dd>{value.id}</dd>
      </div>
      <div>
        <dt>Estado</dt>
        <dd>{value.status === "booked" ? "Reservada" : value.status}</dd>
      </div>
    </dl>
  );
}

function OperationProposalCard({
  proposal,
  conversation,
  busy,
  onConfirm,
  onDiscard,
}: Props & { proposal: OperationProposal }) {
  const copy = operationCopy()[proposal.operation];
  const Icon = copy.icon;
  const completed = conversation.operation_receipt?.status === "completed";
  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className={`offer-card operation-card operation-${proposal.operation}`}
      aria-label={completed ? "Resultado de la gestión" : copy.title}
    >
      <div className="section-heading">
        <strong>{completed ? "Gestión realizada" : copy.title}</strong>
        {completed ? <Check size={19} /> : <Icon size={19} />}
      </div>
      <p className="operation-subject">
        Para <strong>{conversation.subject_name}</strong> · propuesta r
        {proposal.revision}
      </p>
      {completed && (
        <p className="muted">Datos de la cita antes de esta gestión:</p>
      )}
      <AppointmentFacts value={proposal.appointment} />
      {proposal.operation === "reschedule" && proposal.target_offer && (
        <div className="operation-target">
          <span>
            {completed ? "Nuevo horario confirmado" : "Nuevo horario solicitado"}
          </span>
          <strong>{dateTime(proposal.target_offer.start)} · Madrid</strong>
        </div>
      )}
      {proposal.operation === "reminder" && (
        <div className="operation-target">
          <span>Configuración simulada</span>
          <strong>
            {proposal.arguments?.channel || "push"} ·{" "}
            {proposal.arguments?.minutes_before || 60} minutos antes
          </strong>
          <small>No se enviará ningún SMS, correo ni aviso real.</small>
        </div>
      )}
      {completed ? (
        <p className="muted operation-result">
          El resultado ya está registrado. Consulta{" "}
          <Link to="/datos">la agenda y los datos sintéticos</Link> para ver el
          estado vigente.
        </p>
      ) : (
        <p className="operation-warning">
          Todavía no se ha aplicado ningún cambio. Revisa la cita y confirma
          únicamente si el efecto mostrado es correcto.
        </p>
      )}
      {conversation.can_confirm && (
        <div className="actions">
          <button className="primary" disabled={busy} onClick={onConfirm}>
            <Check size={16} /> {copy.confirm}
          </button>
          <button disabled={busy} onClick={onDiscard}>
            Mantener la agenda sin cambios
          </button>
        </div>
      )}
    </motion.section>
  );
}

function BookingCard({ conversation, busy, onConfirm, onDiscard }: Props) {
  const offer = conversation.offer;
  if (!offer) return null;
  const completed = conversation.operation_receipt?.operation === "book";
  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="offer-card operation-card operation-book"
      aria-label={completed ? "Reserva registrada" : "Propuesta de reserva"}
    >
      <div className="section-heading">
        <strong>{completed ? "Reserva registrada" : "Reserva pendiente"}</strong>
        {completed ? <Check size={19} /> : <CalendarCheck size={19} />}
      </div>
      <p className="operation-subject">
        Para <strong>{conversation.subject_name}</strong>
      </p>
      <dl className="appointment-facts">
        <div>
          <dt>Servicio</dt>
          <dd>{offer.service_display}</dd>
        </div>
        <div>
          <dt>Fecha y hora</dt>
          <dd>{dateTime(offer.start)} · Madrid</dd>
        </div>
        <div>
          <dt>Modalidad</dt>
          <dd>{offer.modality_display}</dd>
        </div>
        <div>
          <dt>Centro</dt>
          <dd>{offer.location_display}</dd>
        </div>
      </dl>
      {!completed && (
        <p className="operation-warning">
          Es una propuesta: el hueco se revalidará al confirmar y todavía no
          está reservado.
        </p>
      )}
      {conversation.can_confirm && (
        <div className="actions">
          <button className="primary" disabled={busy} onClick={onConfirm}>
            <Check size={16} /> Confirmar reserva
          </button>
          <button disabled={busy} onClick={onDiscard}>
            Descartar propuesta
          </button>
        </div>
      )}
    </motion.section>
  );
}

function AppointmentResults({ values }: { values: AppointmentSummary[] }) {
  if (!values.length) return null;
  return (
    <section className="appointment-results" aria-label="Citas encontradas">
      <div className="section-heading">
        <strong>Citas encontradas</strong>
        <span>{values.length}</span>
      </div>
      <ol>
        {values.map((appointment) => (
          <li key={appointment.id}>
            <CalendarCheck size={17} />
            <span>
              <strong>{appointment.service_display}</strong>
              <small>{dateTime(appointment.start)} · Madrid</small>
            </span>
            <code>{appointment.id}</code>
          </li>
        ))}
      </ol>
    </section>
  );
}

/** Proyección orientada a tareas; nunca presenta el estado técnico completo al paciente. */
export function OperationPanel(props: Props) {
  if (props.conversation.operation_proposal) {
    return (
      <OperationProposalCard
        {...props}
        proposal={props.conversation.operation_proposal}
      />
    );
  }
  if (props.conversation.offer) return <BookingCard {...props} />;
  return (
    <AppointmentResults values={props.conversation.appointment_results || []} />
  );
}
