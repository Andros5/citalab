import { MessageSquare } from "lucide-react";

// Proper name: do not translate its "Cita" fragment as the appointment noun.
const brandPrefix = "Cita";
const brandSuffix = "Lab";

export function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark" aria-hidden="true">
        <MessageSquare size={22} strokeWidth={1.7} />
      </span>
      <span>
        {brandPrefix}<span className="brand-light">{brandSuffix}</span>
        <small>Laboratorio de agentes</small>
      </span>
    </div>
  );
}
