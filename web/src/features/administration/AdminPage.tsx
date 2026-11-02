import { History, KeyRound } from "lucide-react";
import { useEffect, useState } from "react";
import { api, dateTime } from "../../api";
import {
  Empty,
  ErrorState,
  Field,
  JsonBlock,
  Modal,
  Notice,
  PageHeader,
  Skeleton,
  Tabs,
} from "../../components";
import { useApp } from "../../context";
import { tx } from "../../i18n";
import { ConfigurationPanel } from "./ConfigurationPanel";
import { PromptsPanel } from "./PromptsPanel";
import { FieldHelpContext } from "../../shared/ui/FieldInfo";
import { adminFieldHelp, adminSectionDescription } from "./adminHelp";
import "./administration.css";

type Account = {
  username: string;
  display_name: string;
  role: string;
  subject_id: string;
  active: number;
};
type Snapshot = { id: string; at: string; actor: string };
type Audit = {
  id: number;
  at: string;
  actor: string;
  action: string;
  target: string;
  detail: unknown;
};

export function AdminPage() {
  const { bootstrap, refresh, notify } = useApp();
  const config = bootstrap.config.config;
  const admin = bootstrap.user.role === "admin";
  const [tab, setTab] = useState("config");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadingTab, setLoadingTab] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [revision, setRevision] = useState(0);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [auditSearch, setAuditSearch] = useState("");
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [action, setAction] = useState<{
    title: string;
    phrase: string;
    url: string;
  } | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [retention, setRetention] = useState<Record<string, unknown> | null>(
    null,
  );
  // Cada pestaña carga solo la evidencia necesaria y cancela peticiones obsoletas.
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    setLoadError("");
    setLoadingTab(["accounts", "audit", "storage"].includes(tab));
    const load = async () => {
      const read = <T,>(path: string) =>
        api<T>(path, "GET", undefined, { signal: controller.signal });
      if (tab === "accounts" && admin) {
        const value = await read<Account[]>("/admin/accounts");
        if (!controller.signal.aborted) setAccounts(value);
      } else if (tab === "audit") {
        const value = await read<Audit[]>("/admin/audit");
        if (!controller.signal.aborted) setAudit(value);
      } else if (tab === "storage" && admin) {
        const [snaps, ret] = await Promise.all([
          read<Snapshot[]>("/snapshots"),
          read<Record<string, unknown>>("/admin/retention"),
        ]);
        if (!controller.signal.aborted) {
          setSnapshots(snaps);
          setRetention(ret);
        }
      }
    };
    void load()
      .catch((e) => {
        if (!controller.signal.aborted) setLoadError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingTab(false);
      });
    return () => controller.abort();
  }, [tab, admin, revision]);
  const openAction = (value: {
    title: string;
    phrase: string;
    url: string;
  }) => {
    setAction(value);
    setConfirmation("");
    setResult(null);
    setError("");
  };
  return (
    <FieldHelpContext.Provider
      value={(label, hint) => adminFieldHelp(tab, label, hint)}
    >
      <div className="admin-page">
        <PageHeader
          eyebrow="LABORATORIO / GOBERNANZA"
          title="Administración"
          description="Configura el experimento con límites explícitos. Cada modificación deja una versión y una justificación."
        />
        {!admin && (
          <Notice>
            Modo de consulta: puedes revisar esta configuración. Solo la cuenta
            investigadora puede modificarla.
          </Notice>
        )}
        {error && (
          <Notice tone="error">
            {error}
            <button
              type="button"
              onClick={() => {
                setRevision((v) => v + 1);
                void refresh().catch((e) => setError(e.message));
              }}
            >
              Actualizar versiones para comparar
            </button>
          </Notice>
        )}
        <Tabs
          label="Secciones de administración"
          value={tab}
          onChange={setTab}
          disabled={busy}
          items={[
            { value: "config", label: "Configuración" },
            { value: "prompts", label: "Prompts" },
            ...(admin
              ? [
                  { value: "accounts", label: "Cuentas" },
                  { value: "storage", label: "Datos y retención" },
                ]
              : []),
            { value: "audit", label: "Auditoría" },
          ]}
        >
          <p className="admin-section-scope">{adminSectionDescription(tab)}</p>
          {loadingTab && (
            <Skeleton label="Cargando sección de administración…" />
          )}
          {loadError && (
            <ErrorState
              message={loadError}
              retry={() => setRevision((v) => v + 1)}
            />
          )}
          {tab === "config" && <ConfigurationPanel />}
          {tab === "prompts" && <PromptsPanel />}
          {!loadingTab && !loadError && tab === "accounts" && admin && (
            <section className="panel">
              <div className="section-heading">
                <h2>Cuentas del laboratorio</h2>
                <span>{accounts.length} cuentas</span>
              </div>
              <Notice>
                Los 50 perfiles disponen de una cuenta propia. Los roles de
                administración y revisión son cuentas independientes. Los
                códigos no se guardan en texto claro en la base de datos.
              </Notice>
              <div className="table-scroll responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>Cuenta</th>
                      <th>Rol</th>
                      <th>Perfil vinculado</th>
                      <th>Acceso</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accounts.map((item) => (
                      <tr key={item.username}>
                        <td data-label="Cuenta">
                          <strong>{item.display_name}</strong>
                          <small>{item.username}</small>
                        </td>
                        <td data-label="Rol">
                          {item.role === "admin"
                            ? "Administrador"
                            : item.role === "researcher"
                              ? "Revisor"
                              : "Paciente sintético"}
                        </td>
                        <td data-label="Perfil vinculado">
                          {item.subject_id || "Laboratorio"}
                        </td>
                        <td data-label="Acceso">
                          <button
                            onClick={() =>
                              openAction({
                                title: `${tx("Nuevo código para")} ${item.display_name}`,
                                phrase: "GENERAR NUEVO CÓDIGO",
                                url: `/admin/accounts/${item.username}/reset-password`,
                              })
                            }
                          >
                            <KeyRound size={16} /> Generar código
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
          {!loadingTab && !loadError && tab === "storage" && admin && (
            <div className="settings-layout">
              <section className="panel">
                <div className="section-heading">
                  <h2>Instantáneas de datos sintéticos</h2>
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        await api("/snapshots", "POST");
                        setSnapshots(await api<Snapshot[]>("/snapshots"));
                        notify(
                          "Instantánea guardada: recursos, perfiles y estado transaccional.",
                        );
                      } catch (e) {
                        setError((e as Error).message);
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    Crear instantánea
                  </button>
                </div>
                <p>
                  Guarda la agenda antes de una demostración. Restaurarla crea
                  una copia de recuperación y archiva las conversaciones
                  anteriores para invalidar sus propuestas.
                </p>
                {snapshots.length ? (
                  snapshots.map((item) => (
                    <div className="version-row" key={item.id}>
                      <strong>{dateTime(item.at)}</strong>
                      <p className="hash">{item.id}</p>
                      <button
                        onClick={() =>
                          openAction({
                            title: "Restaurar el conjunto sintético",
                            phrase: "RESTAURAR DATOS SINTÉTICOS",
                            url: `/snapshots/${item.id}/restore`,
                          })
                        }
                      >
                        Restaurar esta instantánea
                      </button>
                    </div>
                  ))
                ) : (
                  <Empty title="Sin instantáneas">
                    Crea una antes de modificar la agenda o los perfiles.
                  </Empty>
                )}
              </section>
              <section className="panel">
                <h2>Retención y minimización</h2>
                <p>
                  Conversaciones: {config.retention_days} días. Diagnóstico:{" "}
                  {config.diagnostic_days} días. La purga no cancela citas;
                  elimina el historial caducado y retira las copias diagnósticas
                  vencidas. La traza mínima de operaciones se conserva aparte.
                </p>
                <JsonBlock data={retention} />
                <button
                  className="danger"
                  onClick={() =>
                    openAction({
                      title: "Eliminar contenido caducado",
                      phrase: "BORRAR CONTENIDO CADUCADO",
                      url: "/admin/retention",
                    })
                  }
                >
                  Purgar contenido caducado
                </button>
                <p>
                  La agenda de demostración puede regenerarse con huecos futuros
                  desde hoy; las conversaciones existentes no se borran.
                </p>
                <button
                  className="danger"
                  onClick={() =>
                    openAction({
                      title: "Regenerar la agenda de demostración",
                      phrase: "REGENERAR AGENDA",
                      url: "/demo/reset",
                    })
                  }
                >
                  Regenerar agenda de demostración
                </button>
              </section>
            </div>
          )}
          {!loadingTab && !loadError && tab === "audit" && (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <h2>Registro de acciones</h2>
                  <p className="muted">
                    Últimos 500 eventos administrativos. Sin contraseñas ni
                    cuerpo bruto de las peticiones.
                  </p>
                </div>
                <History size={22} />
              </div>
              <Field label="Filtrar eventos">
                <input
                  placeholder="Acción, cuenta o recurso…"
                  value={auditSearch}
                  onChange={(e) => setAuditSearch(e.target.value)}
                />
              </Field>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Cuenta</th>
                      <th>Acción</th>
                      <th>Recurso / detalle</th>
                    </tr>
                  </thead>
                  <tbody>
                    {audit
                      .filter((item) =>
                        `${item.action} ${item.actor} ${item.target}`.includes(
                          auditSearch,
                        ),
                      )
                      .map((item) => (
                        <tr key={item.id}>
                          <td data-label="Fecha">{dateTime(item.at)}</td>
                          <td data-label="Actor">{item.actor}</td>
                          <td data-label="Acción">
                            <code>{item.action}</code>
                          </td>
                          <td data-label="Detalle">
                            <span className="hash">{item.target || "—"}</span>
                            <details>
                              <summary>Detalle</summary>
                              <JsonBlock
                                data={item.detail}
                                label={`${tx("Detalle de auditoría")} ${item.id}`}
                              />
                            </details>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </Tabs>
        {action && (
          <Modal
            title={action.title}
            close={() => {
              setAction(null);
              setResult(null);
            }}
          >
            {result ? (
              <>
                <Notice tone="success">Operación completada.</Notice>
                {result.one_time_display_password ? (
                  <>
                    <p>
                      Este código se muestra una sola vez. La cuenta deberá
                      volver a iniciar sesión.
                    </p>
                    <pre className="generated-code">
                      {String(result.one_time_display_password)}
                    </pre>
                  </>
                ) : (
                  <JsonBlock data={result} />
                )}
                <button
                  className="primary"
                  onClick={() => {
                    setAction(null);
                    setResult(null);
                  }}
                >
                  Hecho
                </button>
              </>
            ) : (
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  setBusy(true);
                  try {
                    setResult(
                      await api<Record<string, unknown>>(action.url, "POST", {
                        confirmation,
                      }),
                    );
                    if (tab === "storage") {
                      setSnapshots(await api<Snapshot[]>("/snapshots"));
                      setRetention(
                        await api<Record<string, unknown>>("/admin/retention"),
                      );
                    }
                  } catch (error) {
                    setError((error as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <p>Para confirmar, escribe exactamente:</p>
                <p>
                  <strong>{action.phrase}</strong>
                </p>
                <Field label="Confirmación explícita">
                  <input
                    value={confirmation}
                    onChange={(e) => setConfirmation(e.target.value)}
                    autoComplete="off"
                  />
                </Field>
                {error && <Notice tone="error">{error}</Notice>}
                <div className="dialog-actions">
                  <button type="button" onClick={() => setAction(null)}>
                    Volver
                  </button>
                  <button
                    className="primary"
                    disabled={confirmation !== action.phrase || busy}
                  >
                    Confirmar operación
                  </button>
                </div>
              </form>
            )}
          </Modal>
        )}
      </div>
    </FieldHelpContext.Provider>
  );
}
