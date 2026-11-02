import { useState } from "react";
import { api, dateTime, type Resource, type Resources } from "../../api";
import { Field, Modal, Notice } from "../../components";
import { tx } from "../../i18n";
import {
  compatibleSlots,
  modalityLabel,
  serviceLabel,
} from "../../shared/lib/resourceLabels";

export function AppointmentDialog({
  appointment,
  resources,
  close,
  saved,
}: {
  appointment: Resource;
  resources: Resources;
  close: () => void;
  saved: () => void;
}) {
  const [action, setAction] = useState("reschedule");
  const [slot, setSlot] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const destinations = compatibleSlots(appointment, resources);
  const selected = destinations.find((item) => item.id === slot);
  return (
    <Modal title="Gestionar cita sintética" close={close}>
      <p>
        <strong>{serviceLabel(appointment)}</strong> ·{" "}
        {dateTime(appointment.start)} · {appointment.id}
      </p>
      <Notice>
        Esta operación se realiza mediante un formulario validado, no mediante
        el chatbot. Conserva el servicio original; no permite cambiar de
        especialidad. Quedará registrada en la auditoría.
      </Notice>
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          setBusy(true);
          try {
            await api(`/appointments/${appointment.id}`, "POST", {
              action,
              slot_id: action === "reschedule" ? slot : null,
              confirmed: true,
              expected_version: appointment.meta?.versionId,
              request_id: crypto.randomUUID(),
            });
            saved();
            close();
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Field label="Operación">
          <select
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setConfirmed(false);
            }}
          >
            <option value="reschedule">Cambiar fecha u hora</option>
            <option value="cancel">Cancelar la cita</option>
          </select>
        </Field>
        {action === "reschedule" && (
          <Field label="Nuevo hueco disponible">
            <select
              required
              value={slot}
              onChange={(e) => {
                setSlot(e.target.value);
                setConfirmed(false);
              }}
            >
              <option value="">Selecciona un hueco</option>
              {destinations.map((item) => (
                <option key={item.id} value={item.id}>
                  {serviceLabel(item)} · {dateTime(item.start)} ·{" "}
                  {modalityLabel(item)} · {item.schedule?.reference}
                </option>
              ))}
            </select>
          </Field>
        )}
        {action === "reschedule" && !destinations.length && (
          <Notice>
            No hay destinos libres del mismo servicio. Puedes volver o cancelar
            explícitamente; no se ofrece otro servicio.
          </Notice>
        )}
        <label className="check-row">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
            required
          />
          <span>
            {tx("Confirmo")}{" "}
            {action === "cancel"
              ? `${tx("la cancelación de")} ${appointment.id}`
              : `${tx("el cambio de")} ${serviceLabel(appointment)} ${tx("a")} ${selected ? `${dateTime(selected.start)} · ${modalityLabel(selected)}` : tx("un hueco aún no seleccionado")}`}
            .
          </span>
        </label>
        {error && <Notice tone="error">{error}</Notice>}
        <div className="dialog-actions">
          <button type="button" onClick={close}>
            Volver
          </button>
          <button
            className={action === "cancel" ? "danger" : "primary"}
            disabled={!confirmed || busy || (action === "reschedule" && !slot)}
          >
            Confirmar {action === "cancel" ? "cancelación" : "cambio"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
