import { agendaDate, type Resource, type Resources } from "../../api";
import { serviceCode } from "../../shared/lib/resourceLabels";

export type AgendaFilters = {
  service: string;
  schedule: string;
  availability: string;
};

/** Devuelve únicamente huecos pertenecientes a agendas activas y los ordena cronológicamente. */
export function selectActiveSlots(resources?: Resources | null): Resource[] {
  return Object.values(resources?.Slot || {})
    .filter((slot) => agendaDate(slot.start || ""))
    .filter(
      (slot) =>
        resources?.Schedule?.[slot.schedule?.reference.split("/")[1] || ""]
          ?.active === true,
    )
    .sort((left, right) => Date.parse(left.start!) - Date.parse(right.start!));
}

export function selectSlots(
  slots: Resource[],
  { service, schedule, availability }: AgendaFilters,
): Resource[] {
  return slots.filter(
    (slot) =>
      (!service || serviceCode(slot) === service) &&
      (!schedule || slot.schedule?.reference === `Schedule/${schedule}`) &&
      (!availability || slot.status === availability),
  );
}

export function indexSlotsByDay(slots: Resource[]): Map<string, number> {
  const index = new Map<string, number>();
  for (const slot of slots) {
    const day = agendaDate(slot.start!);
    index.set(day, (index.get(day) || 0) + 1);
  }
  return index;
}

export function selectVisibleSlots(
  slots: Resource[],
  datePrefix: string,
  availability: string,
): Resource[] {
  return slots.filter(
    (slot) =>
      agendaDate(slot.start!).startsWith(datePrefix) &&
      (!availability || slot.status === availability),
  );
}

/** Cruza Appointment con Slot para aplicar la agenda seleccionada sin desnormalizar FHIR. */
export function selectAppointments(
  resources: Resources | null | undefined,
  service: string,
  schedule: string,
): Resource[] {
  return Object.values(resources?.Appointment || {}).filter(
    (appointment) =>
      (!service || serviceCode(appointment) === service) &&
      (!schedule ||
        (Array.isArray(appointment.slot) &&
          appointment.slot.some(
            (reference: { reference: string }) =>
              resources?.Slot?.[reference.reference.split("/")[1]]?.schedule
                ?.reference === `Schedule/${schedule}`,
          ))),
  );
}
