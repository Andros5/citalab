import { useState } from "react";
import { api, type Catalog, type Resource, type Resources } from "../../api";
import { Field, Modal, Notice } from "../../components";

export function SlotDialog({
  slot,
  resources,
  catalog,
  initialSchedule,
  close,
  saved,
}: {
  slot: Resource | null;
  resources: Resources;
  catalog: Catalog | null;
  initialSchedule?: string;
  close: () => void;
  saved: () => void;
}) {
  const [schedule, setSchedule] = useState(
    slot?.schedule?.reference.split("/")[1] ||
      initialSchedule ||
      catalog?.schedules.find((item) => item.active)?.id ||
      Object.keys(resources.Schedule || {})[0] ||
      "",
  );
  const [start, setStart] = useState(slot?.start || "");
  const [end, setEnd] = useState(slot?.end || "");
  const [status, setStatus] = useState(slot?.status || "free");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const selected = catalog?.schedules.find((item) => item.id === schedule);
  return (
    <Modal
      title={slot ? "Editar hueco sintético" : "Añadir un hueco a la agenda"}
      close={close}
    >
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            await api(
              `/slots${slot ? `/${slot.id}` : ""}`,
              slot ? "PUT" : "POST",
              {
                schedule_id: schedule,
                start,
                end,
                status,
                reason,
                expected_version: slot?.meta?.versionId || (slot ? "1" : null),
              },
            );
            saved();
            close();
          } catch (error) {
            setError((error as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Field label="Agenda">
          <select
            value={schedule}
            onChange={(e) => setSchedule(e.target.value)}
            disabled={!!slot}
          >
            {(catalog?.schedules || []).map((item) => (
              <option value={item.id} key={item.id} disabled={!item.active}>
                {item.label} · {item.id}
                {item.active ? "" : " · Inactiva"}
              </option>
            ))}
          </select>
        </Field>
        <p>
          {selected
            ? `${selected.label} · modalidad ${selected.modality_label || selected.modality_code}`
            : "Esperando una agenda configurada. No se puede guardar sin catálogo."}
        </p>
        <Field
          label="Inicio con zona horaria"
          hint="Formato ISO, por ejemplo 2026-09-15T09:00:00+02:00"
        >
          <input
            required
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </Field>
        <Field label="Fin con zona horaria">
          <input
            required
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </Field>
        <Field label="Disponibilidad">
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="free">Disponible</option>
            <option value="busy-unavailable">No disponible</option>
          </select>
        </Field>
        <Field label="Motivo del cambio">
          <input
            minLength={5}
            maxLength={300}
            required
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </Field>
        <Notice>
          No se pueden editar huecos reservados ni crear intervalos solapados.
          El servicio y la modalidad proceden de la agenda existente.
        </Notice>
        {error && <Notice tone="error">{error}</Notice>}
        <div className="dialog-actions">
          <button type="button" onClick={close}>
            Volver
          </button>
          <button className="primary" disabled={busy || !selected?.active}>
            Guardar hueco
          </button>
        </div>
      </form>
    </Modal>
  );
}
