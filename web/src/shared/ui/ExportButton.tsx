import { ArrowDownToLine } from "lucide-react";
import { useState } from "react";
import { api, downloadJSON } from "../../api";

/** Download only the server-authorized representation; never reconstruct an export. */
export function ExportButton({
  path,
  filename,
  label = "Exportar",
  iconOnly = false,
}: {
  path: string;
  filename: string;
  label?: string;
  iconOnly?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  return (
    <span className="export-control">
      <button
        type="button"
        className={iconOnly ? "icon-button" : undefined}
        aria-label={label}
        disabled={busy}
        aria-busy={busy}
        onClick={async () => {
          setBusy(true);
          setError("");
          setDone(false);
          try {
            downloadJSON(await api(path), filename);
            setDone(true);
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <ArrowDownToLine size={17} aria-hidden="true" />
        {!iconOnly && (busy ? "Preparando…" : label)}
      </button>
      <span role="status" className="sr-only">
        {done ? "Archivo preparado para descargar." : ""}
      </span>
      {error && (
        <span role="alert" className="field-error">
          {error} Puedes volver a intentarlo.
        </span>
      )}
    </span>
  );
}
