import { ArrowRight } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Conversation } from "../../api";
import { Field, Modal, Notice } from "../../components";
import { useApp } from "../../context";
import { useLocale } from "../../i18n";

export function NewConversationDialog({ close }: { close: () => void }) {
  const { bootstrap } = useApp();
  const { language } = useLocale();
  const navigate = useNavigate();
  const staff = bootstrap.user.role !== "patient";
  const [subject, setSubject] = useState(
    bootstrap.user.subject_id || bootstrap.patients[0]?.id || "",
  );
  const [architecture, setArchitecture] = useState(
    bootstrap.config.config.default_architecture,
  );
  const [provider, setProvider] = useState(
    bootstrap.config.config.default_provider,
  );
  const [diagnostic, setDiagnostic] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <Modal title="Nueva conversación" close={close}>
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          setBusy(true);
          setError("");
          try {
            const conversation = await api<Conversation>(
              "/conversations",
              "POST",
              {
                synthetic_confirmed: true,
                ui_language: language,
                ...(staff
                  ? { subject_id: subject, architecture, provider, diagnostic }
                  : {}),
              },
            );
            close();
            navigate(`/asistente/${conversation.id}`);
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Notice>
          Escenario activo: {bootstrap.catalog?.scenario.id || "no disponible"} ·
          versión {bootstrap.catalog?.scenario.version || "n/d"}.
        </Notice>
        {bootstrap.catalog?.availability?.future_free_slots === 0 && (
          <Notice tone="error">
            Este escenario no contiene huecos libres futuros. Puedes auditarlo,
            pero una demostración de reserva necesitará añadir disponibilidad
            sintética futura desde Agenda y datos.
          </Notice>
        )}
        <Field
          label={
            staff ? "Perfil sintético para la prueba" : "Cuenta del paciente"
          }
        >
          <select
            value={subject}
            disabled={!staff}
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
        {staff && (
          <>
            <div className="form-grid">
              <Field label="Arquitectura">
                <select
                  value={architecture}
                  onChange={(e) => setArchitecture(e.target.value)}
                >
                  <option value="M5">M5 · Cinco agentes (principal)</option>
                  <option value="S1">S1 · Agente único</option>
                  <option value="H">H · Híbrida</option>
                </select>
              </Field>
              <Field label="Motor de ejecución">
                <select
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                >
                  <option value="groq">Groq · API LLM</option>
                  <option value="google">Gemini · Google AI Studio</option>
                </select>
              </Field>
            </div>
            {(
              <Notice>
                Modelo: {bootstrap.models[provider]}.{" "}
                {bootstrap.config.config.remote_enabled
                  ? "Se utilizará la API configurada y su cuota."
                  : "Las llamadas externas están pausadas en Administración."}
              </Notice>
            )}
            <label className="check-row">
              <input
                type="checkbox"
                checked={diagnostic}
                onChange={(e) => setDiagnostic(e.target.checked)}
              />
              <span>
                Capturar diagnóstico de entradas y salidas
                <small>
                  Solo contenido sintético filtrado. Accesible al equipo
                  investigador durante {bootstrap.config.config.diagnostic_days}{" "}
                  días. Nunca razonamiento interno.
                </small>
              </span>
            </label>
          </>
        )}
        <Notice>Solo datos sintéticos. No introduzcas información personal real.</Notice>
        {error && <Notice tone="error">{error}</Notice>}
        <div className="dialog-actions">
          <button type="button" onClick={close}>
            Volver
          </button>
          <button className="primary" disabled={busy}>
            {busy ? "Preparando…" : "Crear conversación"}
            <ArrowRight size={16} />
          </button>
        </div>
      </form>
    </Modal>
  );
}
