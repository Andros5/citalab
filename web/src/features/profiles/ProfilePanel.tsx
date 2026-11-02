import { Database } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../../api";
import { ErrorState, Field, Notice, Skeleton } from "../../components";
import { useApp } from "../../context";
import { tx } from "../../i18n";
type Profile = {
  subject_id: string;
  version: number;
  attributes: {
    attribute_id: string;
    key: string;
    value: unknown;
    source: string;
    status: string;
    confidence: number;
    purposes: string[];
  }[];
};

export function ProfilePanel() {
  const { bootstrap, notify } = useApp();
  const admin = bootstrap.user.role === "admin";
  const staff = bootstrap.user.role !== "patient";
  const [subject, setSubject] = useState(
    bootstrap.user.subject_id || bootstrap.patients[0]?.id || "",
  );
  const [profile, setProfile] = useState<Profile | null>(null);
  const [language, setLanguage] = useState("es");
  const [detail, setDetail] = useState("standard");
  const [treatment, setTreatment] = useState("neutral");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const legacyLanguage = (value: string) => {
    const name = ({ fr: "Francés", de: "Alemán", pt: "Portugués" } as Record<string, string>)[value] || value;
    return `${tx(name)} (${tx("perfil heredado")})`;
  };
  const [error, setError] = useState("");
  const [profileRevision, setProfileRevision] = useState(0);
  // Un cambio de sujeto invalida el formulario anterior y cancela su lectura pendiente.
  useEffect(() => {
    const controller = new AbortController();
    setProfile(null);
    setError("");
    setReason("");
    api<Profile>(`/profiles/${subject}`, "GET", undefined, {
      signal: controller.signal,
    })
      .then((value) => {
        if (controller.signal.aborted) return;
        if (
          !value ||
          value.subject_id !== subject ||
          !Array.isArray(value.attributes)
        )
          throw new Error("El perfil recibido no tiene un formato válido.");
        setProfile(value);
        const preference = (key: string, fallback: string) =>
          String(
            [...value.attributes]
              .reverse()
              .find(
                (item) =>
                  item.key === key &&
                  item.status === "active" &&
                  item.source === "declared",
              )?.value || fallback,
          );
        setLanguage(preference("preferred-language", "es"));
        setDetail(preference("preferred-detail-level", "standard"));
        setTreatment(preference("preferred-treatment", "neutral"));
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => {
      controller.abort();
    };
  }, [subject, profileRevision]);
  return (
    <>
      {" "}
      {error && profile && <Notice tone="error">{error}</Notice>}
      {!admin && (
        <Notice>
          Vista de consulta. Puedes indicar tus preferencias durante el chat;
          solo el administrador puede publicar cambios permanentes en estos
          perfiles sintéticos.
        </Notice>
      )}
      <div className="profile-layout">
        <section className="panel">
          <div className="section-heading">
            <h2>Preferencias de comunicación</h2>
            <span className="architecture-tag">
              {staff ? `${bootstrap.patients.length} perfiles` : "Tu perfil"}
            </span>
          </div>
          <Field label={staff ? "Perfil sintético" : "Paciente"}>
            <select
              value={subject}
              disabled={saving}
              onChange={(e) => setSubject(e.target.value)}
            >
              {bootstrap.patients.map((patient) => (
                <option key={patient.id} value={patient.id}>
                  {patient.name}
                  {staff ? ` · ${patient.id}` : ""}
                </option>
              ))}
            </select>
          </Field>
          {profile?.subject_id === subject ? (
            <form
              onSubmit={async (event) => {
                event.preventDefault();
                setSaving(true);
                try {
                  const value = await api<Profile>(
                    `/profiles/${profile.subject_id}`,
                    "PUT",
                    {
                      expected_version: profile.version,
                      language,
                      detail,
                      treatment,
                      reason,
                    },
                  );
                  setProfile(value);
                  setReason("");
                  notify(
                    "Perfil actualizado. La nueva evidencia declarada conserva las versiones anteriores.",
                  );
                } catch (e) {
                  setError((e as Error).message);
                } finally {
                  setSaving(false);
                }
              }}
            >
              {!admin ? (
                <dl className="readable-settings">
                  <div>
                    <dt>Idioma declarado</dt>
                    <dd>
                      {{
                        es: tx("Español"),
                        en: tx("Inglés"),
                        fr: legacyLanguage("fr"),
                        de: legacyLanguage("de"),
                        pt: legacyLanguage("pt"),
                      }[language] || language}
                    </dd>
                  </div>
                  <div>
                    <dt>Nivel de detalle</dt>
                    <dd>
                      {tx({
                        concise: "Conciso",
                        standard: "Estándar",
                        "step-by-step": "Paso a paso",
                      }[detail] || detail)}
                    </dd>
                  </div>
                  <div>
                    <dt>Tratamiento</dt>
                    <dd>{tx(treatment === "formal" ? "Formal" : "Neutral")}</dd>
                  </div>
                </dl>
              ) : (
                <>
                  <Field label="Idioma declarado">
                    <select
                      value={language}
                      disabled={!admin || saving}
                      onChange={(e) => setLanguage(e.target.value)}
                    >
                      {[
                        ...(language === "es" || language === "en"
                          ? []
                          : [[language, legacyLanguage(language)]]),
                        ["es", tx("Español")],
                        ["en", tx("Inglés")],
                      ].map(([key, label]) => (
                        <option key={key} value={key}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Nivel de detalle">
                    <select
                      value={detail}
                      disabled={!admin || saving}
                      onChange={(e) => setDetail(e.target.value)}
                    >
                      <option value="concise">Conciso</option>
                      <option value="standard">Estándar</option>
                      <option value="step-by-step">Paso a paso</option>
                    </select>
                  </Field>
                  <Field label="Tratamiento">
                    <select
                      value={treatment}
                      disabled={!admin || saving}
                      onChange={(e) => setTreatment(e.target.value)}
                    >
                      <option value="neutral">Neutral</option>
                      <option value="formal">Formal</option>
                    </select>
                  </Field>
                </>
              )}
              {admin && (
                <>
                  <Field label="Justificación de la modificación">
                    <input
                      required
                      minLength={5}
                      maxLength={300}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                  </Field>
                  <button className="primary" disabled={saving}>
                    Guardar nueva versión
                  </button>
                </>
              )}
              <p className="muted">
                Versión actual: {profile.version}. Las preferencias del chat son
                de sesión; esta modificación administrativa sí es persistente.
              </p>
            </form>
          ) : error ? (
            <ErrorState
              message={error}
              retry={() => setProfileRevision((v) => v + 1)}
            />
          ) : (
            <Skeleton label="Cargando perfil" />
          )}
        </section>
        {staff && (
          <section className="panel">
            <div className="section-heading">
              <h2>Evidencias y procedencia</h2>
              <Database size={19} />
            </div>
            <Notice>
              No se infieren preferencias a partir de edad, salud o capacidad.
              La resolución distingue evidencia declarada, importada e inferida.
            </Notice>
            {profile && (
              <div className="table-scroll responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>Atributo</th>
                      <th>Valor</th>
                      <th>Origen / estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {profile.attributes.map((item) => (
                      <tr key={item.attribute_id}>
                        <td data-label="Atributo">
                          {tx(item.key)}
                          <small>Confianza: {item.confidence}</small>
                        </td>
                        <td data-label="Valor">{String(item.value)}</td>
                        <td data-label="Procedencia">
                          {tx(item.source)}
                          <small>{tx(item.status)}</small>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}
      </div>
    </>
  );
}
