import { dateTime, roleLabels } from "../../api";
import { Empty, ErrorState, Field, Notice, Skeleton } from "../../components";
import { tx } from "../../i18n";
import { usePromptEditor } from "./usePromptEditor";
export function PromptsPanel() {
  const {
    admin,
    resource,
    history,
    role,
    setRole,
    prompt,
    instruction,
    setInstruction,
    reason,
    setReason,
    busy,
    error,
    dirty,
    publish,
    discard,
  } = usePromptEditor();
  if (resource.loading) return <Skeleton label="Cargando instrucciones" />;
  if (resource.error)
    return <ErrorState message={resource.error} retry={resource.retry} />;
  return (
    <>
      {error && (
        <Notice tone="error">
          {error}
          <button onClick={resource.retry}>
            Actualizar versión vigente sin descartar borrador
          </button>
        </Notice>
      )}
      {dirty && (
        <Notice>
          Instrucciones sin guardar. Cada rol conserva su propio borrador
          durante esta sesión.
          <button onClick={discard}>Descartar instrucciones</button>
        </Notice>
      )}
      {dirty && (
        <details className="details">
          <summary>
            {tx("Comparar instrucción vigente y borrador de ")}{tx(roleLabels[role])}
          </summary>
          <h3>Vigente · r{prompt?.version}</h3>
          <pre className="prompt">
            {prompt?.instruction || "(Sin instrucciones adicionales)"}
          </pre>
          <h3>Borrador</h3>
          <pre className="prompt">
            {instruction || "(Sin instrucciones adicionales)"}
          </pre>
        </details>
      )}
      <div className="settings-layout">
        <section className="panel">
          <div className="section-heading">
            <h2>Instrucciones experimentales</h2>
            <span className="architecture-tag">Versionadas</span>
          </div>
          <Field label="Rol">
            <select
              value={role}
              disabled={busy}
              onChange={(e) => setRole(e.target.value)}
            >
              {Object.entries(roleLabels).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Notice>
            Se añaden al prompt base; no reemplazan las restricciones del
            contrato. S1 sigue recibiendo instrucciones adaptadas a las acciones
            disponibles en cada fase.
          </Notice>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void publish();
            }}
          >
            <Field
              label="Instrucción adicional"
              hint="Puede quedar vacía para utilizar solo la plantilla base. Máximo 4.000 caracteres; sin datos personales ni secretos."
            >
              <textarea
                rows={9}
                maxLength={4000}
                readOnly={!admin}
                disabled={busy}
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
              />
            </Field>
            {admin && (
              <>
                <Field label="Hipótesis o motivo del cambio">
                  <input
                    required
                    minLength={5}
                    maxLength={300}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                </Field>
                <button className="primary" disabled={busy || !prompt}>
                  Publicar versión {(prompt?.version || 0) + 1}
                </button>
              </>
            )}
          </form>
          <details className="details">
            <summary>Ver plantilla base y su huella</summary>
            <pre className="prompt" tabIndex={0}>
              {prompt?.base_prompt}
            </pre>
            <p className="hash">SHA-256 · {prompt?.base_hash}</p>
          </details>
        </section>
        <section className="panel">
          <h2>Historial de versiones</h2>
          <p className="muted">
            Recuperar una versión carga su texto en el editor. Publicarla crea
            una revisión nueva; no reescribe la evidencia anterior.
          </p>
          {!history.filter((item) => item.role === role).length ? (
            <Empty title="Plantilla original">
              Aún no se han publicado instrucciones adicionales para este rol.
            </Empty>
          ) : (
            history
              .filter((item) => item.role === role)
              .map((item) => (
                <article
                  className="version-row"
                  key={`${item.role}-${item.version}`}
                >
                  <div className="section-heading">
                    <strong>Revisión {item.version}</strong>
                    <span>{dateTime(item.at)}</span>
                  </div>
                  <p>{item.reason}</p>
                  <pre>
                    {item.instruction || "(Sin instrucciones adicionales)"}
                  </pre>
                  {admin && (
                    <button
                      onClick={() => {
                        setInstruction(item.instruction);
                        setReason(
                          `${tx("Recuperar instrucción de la revisión")} ${item.version}`,
                        );
                      }}
                    >
                      Cargar en el editor
                    </button>
                  )}
                </article>
              ))
          )}
        </section>
      </div>
    </>
  );
}
