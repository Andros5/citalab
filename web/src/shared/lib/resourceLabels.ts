import type { Resource } from "../../api";
import { formatDate, tx } from "../../i18n";

/** The coding system, never array order or a display string, determines identity. */
export function serviceCode(resource: Resource): string | undefined {
  if (!Array.isArray(resource.serviceType)) return undefined;
  const codes = new Set<string>();
  for (const concept of resource.serviceType)
    if (Array.isArray(concept?.coding))
      for (const item of concept.coding)
        if (
          item?.system === "https://example.invalid/tfm/service" &&
          typeof item.code === "string"
        )
          codes.add(item.code);
  return codes.size === 1 ? [...codes][0] : undefined;
}

export function modalityLabel(resource: Resource): string {
  const value = resource.appointmentType as
    { coding?: { system?: string; display?: string }[] } | undefined;
  return (
    value?.coding?.find(
      (item) => item.system === "https://example.invalid/tfm/modality",
    )?.display || tx("Modalidad no especificada")
  );
}

export function compatibleSlots(
  appointment: Resource,
  resources: import("../../api").Resources,
) {
  const service = serviceCode(appointment);
  return Object.values(resources.Slot || {}).filter(
    (item) =>
      service &&
      item.status === "free" &&
      serviceCode(item) === service &&
      resources.Schedule?.[item.schedule?.reference.split("/")[1] || ""]
        ?.active === true,
  );
}

/** Prefer the terminology actually present in the fixture; never infer a clinical service. */
export function serviceLabel(resource: Resource): string {
  const concepts = resource.serviceType;
  if (Array.isArray(concepts))
    for (const concept of concepts) {
      if (typeof concept?.text === "string" && concept.text)
        return tx(concept.text);
      if (Array.isArray(concept?.coding)) {
        const coding = concept.coding.find(
          (item: { display?: unknown }) =>
            typeof item.display === "string" && item.display,
        );
        if (coding) return tx(coding.display);
      }
    }
  return tx("Cita administrativa");
}

export function agendaTime(value: Date): string {
  return formatDate(value, { hour: "2-digit", minute: "2-digit" });
}
