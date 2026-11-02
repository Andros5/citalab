import { Info } from "lucide-react";
import { createContext, useContext, useId, useState } from "react";
import { tx } from "../../i18n";
import "./field-info.css";

export type FieldHelp = { description: string; scope: string };
export const FieldHelpContext = createContext<
  ((label: string, hint?: string) => FieldHelp) | null
>(null);

/** Context opts administration in without changing forms elsewhere. */
export function FieldInfo({ label, hint }: { label: string; hint?: string }) {
  const resolve = useContext(FieldHelpContext);
  const [open, setOpen] = useState(false);
  const id = useId();
  if (!resolve) return null;
  const help = resolve(label, hint);
  return (
    <div className="field-info">
      <button
        type="button"
        className="field-info-button"
        aria-label={`${tx("Información sobre")} ${tx(label)}`}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
        onKeyDown={(event) => {
          if (open && event.key === "Escape") {
            setOpen(false);
            event.stopPropagation();
          }
        }}
      >
        <Info size={15} aria-hidden="true" /> Info
      </button>
      <div id={id} className="field-info-content" role="note" hidden={!open}>
        <p>{help.description}</p>
        <p>
          <strong>{tx("Alcance")}: </strong>
          {help.scope}
        </p>
      </div>
    </div>
  );
}
