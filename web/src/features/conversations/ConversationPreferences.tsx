import { SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, type Conversation, type PreferenceProposal } from "../../api";
import { Field, Notice } from "../../components";
import { tx } from "../../i18n";

type Props = {
  conversation: Conversation;
  busy: boolean;
  onSaved: () => Promise<void>;
  canPersistProfile?: boolean;
};

type SettingKey =
  | "preferred-language"
  | "preferred-detail-level"
  | "preferred-treatment"
  | "preferred-time-of-day"
  | "preferred-reminder-channel";

type Settings = Record<SettingKey, string>;
type Scope = "turn" | "conversation" | "profile";

const labels: Record<string, string> = {
  turn: "esta respuesta",
  conversation: "esta conversación",
  profile: "perfil autorizado",
  default: "valor general",
};
const attributeLabels: Record<SettingKey, string> = {
  "preferred-language": "idioma",
  "preferred-detail-level": "detalle",
  "preferred-treatment": "tratamiento",
  "preferred-time-of-day": "franja",
  "preferred-reminder-channel": "canal de recordatorio",
};
const emptySettings: Settings = {
  "preferred-language": "es",
  "preferred-detail-level": "standard",
  "preferred-treatment": "neutral",
  "preferred-time-of-day": "",
  "preferred-reminder-channel": "",
};
const requestField: Record<SettingKey, string> = {
  "preferred-language": "language",
  "preferred-detail-level": "detail",
  "preferred-treatment": "treatment",
  "preferred-time-of-day": "time_of_day",
  "preferred-reminder-channel": "reminder_channel",
};

function profileProposal(conversation: Conversation): PreferenceProposal | null {
  const proposal = conversation.preference_proposal;
  return proposal?.status === "pending" ? proposal : null;
}

/** Preferencias temporales separadas de una propuesta explícita de persistencia. */
export function ConversationPreferences({
  conversation,
  busy,
  onSaved,
  canPersistProfile = false,
}: Props) {
  const preferences = conversation.preferences;
  const initialValues = useMemo(
    () => ({
      ...emptySettings,
      ...(preferences?.effective || preferences?.values || {}),
      ...(preferences?.pending_turn_values || {}),
    }),
    [preferences],
  );
  const [settings, setSettings] = useState<Settings>(initialValues);
  const [enabled, setEnabled] = useState(!preferences?.profile_opt_out);
  const [scope, setScope] = useState<Scope>("conversation");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const profileRequest = useRef<{ fingerprint: string; id: string } | null>(null);
  const decisionRequests = useRef(new Map<string, string>());

  useEffect(() => {
    setSettings(initialValues);
    setEnabled(!preferences?.profile_opt_out);
  }, [initialValues, preferences?.profile_opt_out]);

  const proposal = profileProposal(conversation);
  const changedValues = useMemo(() => {
    const values: Partial<Record<SettingKey, string>> = {};
    (Object.keys(settings) as SettingKey[]).forEach((key) => {
      if (settings[key] && settings[key] !== initialValues[key]) {
        values[key] = settings[key];
      }
    });
    return values;
  }, [initialValues, settings]);

  const save = async () => {
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const body: Record<string, unknown> = {
        expected_turn: conversation.turn_count,
        scope,
        enabled,
      };
      if (scope === "profile") {
        Object.entries(changedValues).forEach(([key, value]) => {
          body[requestField[key as SettingKey]] = value;
        });
        const fingerprint = JSON.stringify({
          values: Object.fromEntries(
            Object.entries(changedValues).sort(([left], [right]) =>
              left.localeCompare(right),
            ),
          ),
          enabled,
          expected_turn: conversation.turn_count,
        });
        if (profileRequest.current?.fingerprint !== fingerprint) {
          profileRequest.current = { fingerprint, id: crypto.randomUUID() };
        }
        body.request_id = profileRequest.current.id;
      } else {
        Object.entries(changedValues).forEach(([key, value]) => {
          body[requestField[key as SettingKey]] = value;
        });
      }
      const updated = await api<Conversation>(
        `/conversations/${conversation.id}/preferences`,
        "PUT",
        body,
      );
      if (scope === "profile") {
        setNotice(
          "La preferencia se aplica a esta conversación. Para guardarla en futuras conversaciones debes confirmar la propuesta; aún no se ha escrito en el perfil.",
        );
      } else if (scope === "turn") {
        setNotice("Los cambios se aplicarán a la próxima respuesta y después caducarán.");
      } else {
        setNotice(
          updated.preference_update?.proposal_invalidated
            ? "La preferencia cambió y se retiró la propuesta de agenda afectada. No se ha reservado ninguna alternativa."
            : enabled
              ? "Preferencias aplicadas solo a esta conversación; el perfil persistente no ha cambiado."
              : "El perfil no se usará en esta conversación. Sus datos no se han borrado.",
        );
      }
      await onSaved();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const decide = async (confirm: boolean) => {
    if (!proposal) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const endpoint = confirm ? "confirm" : "reject";
      const decisionKey = `${proposal.proposal_id}:${endpoint}`;
      if (!decisionRequests.current.has(decisionKey)) {
        decisionRequests.current.set(decisionKey, crypto.randomUUID());
      }
      const result = await api<Conversation>(
        `/conversations/${conversation.id}/preference-proposal/${endpoint}`,
        "POST",
        {
          proposal_id: proposal.proposal_id,
          request_id: decisionRequests.current.get(decisionKey),
        },
      );
      setNotice(
        confirm
          ? "Preferencias guardadas para futuras conversaciones."
          : "No se guardaron en el perfil; los cambios temporales siguen limitados a esta conversación.",
      );
      profileRequest.current = null;
      await onSaved();
      if (!result.preference_proposal) setScope("conversation");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const disabled =
    busy || saving || conversation.read_only || conversation.archived;
  const sourceEntries = (Object.keys(attributeLabels) as SettingKey[]).map(
    (key) => [key, preferences?.sources?.[key] || "default"] as const,
  );
  const canSave =
    scope === "profile"
      ? canPersistProfile && !proposal && Object.keys(changedValues).length > 0
      : scope === "turn"
        ? enabled && Object.keys(changedValues).length > 0
        : !enabled || Object.keys(changedValues).length > 0;

  return (
    <details className="conversation-preferences">
      <summary>
        <SlidersHorizontal size={17} />
        Preferencias
        <span>{enabled ? "Uso temporal" : "Perfil excluido en esta conversación"}</span>
      </summary>
      <div className="conversation-preferences-body">
        <p className="muted">
          La preferencia afecta a la comunicación o al orden de opciones, nunca a los permisos ni a una escritura automática.
        </p>
        {notice && <Notice>{notice}</Notice>}
        {error && <Notice tone="error">{error}</Notice>}
        <Field label="Alcance">
          <select
            value={scope}
            disabled={disabled || Boolean(proposal)}
            onChange={(event) => setScope(event.target.value as Scope)}
          >
            <option value="turn">Solo la próxima respuesta</option>
            <option value="conversation">Esta conversación</option>
            {canPersistProfile && (
              <option value="profile">Proponer para futuras conversaciones</option>
            )}
          </select>
        </Field>
        <label className="preference-toggle">
          <input
            type="checkbox"
            checked={enabled}
            disabled={disabled || scope === "turn"}
            onChange={(event) => setEnabled(event.target.checked)}
          />
          Usar preferencias autorizadas en esta conversación
        </label>
        {enabled && (
          <div className="preference-grid">
            <Field label="Idioma">
              <select value={settings["preferred-language"]} disabled={disabled} onChange={(e) => setSettings({ ...settings, "preferred-language": e.target.value })}>
                {!(["es", "en"].includes(settings["preferred-language"])) && (
                  <option value={settings["preferred-language"]}>
                    {settings["preferred-language"]} ({tx("preferencia heredada")})
                  </option>
                )}
                <option value="es">Español</option>
                <option value="en">Inglés</option>
              </select>
            </Field>
            <Field label="Nivel de detalle">
              <select value={settings["preferred-detail-level"]} disabled={disabled} onChange={(e) => setSettings({ ...settings, "preferred-detail-level": e.target.value })}>
                <option value="concise">Conciso</option><option value="standard">Estándar</option><option value="step-by-step">Paso a paso</option>
              </select>
            </Field>
            <Field label="Tratamiento">
              <select value={settings["preferred-treatment"]} disabled={disabled} onChange={(e) => setSettings({ ...settings, "preferred-treatment": e.target.value })}>
                <option value="neutral">Neutro</option><option value="formal">Formal</option>
              </select>
            </Field>
            <Field label="Franja preferida (ordenación) ">
              <select value={settings["preferred-time-of-day"]} disabled={disabled} onChange={(e) => setSettings({ ...settings, "preferred-time-of-day": e.target.value })}>
                <option value="">Sin cambios</option><option value="morning">Mañana (antes de las 14:00)</option><option value="afternoon">Tarde (desde las 14:00)</option>
              </select>
            </Field>
            <Field label="Canal preferido de recordatorio simulado">
              <select value={settings["preferred-reminder-channel"]} disabled={disabled} onChange={(e) => setSettings({ ...settings, "preferred-reminder-channel": e.target.value })}>
                <option value="">Sin cambios</option><option value="sms">SMS simulado</option><option value="email">Correo simulado</option><option value="push">Notificación push simulada</option>
              </select>
            </Field>
          </div>
        )}
        <p className="preference-source">
          {tx("Origen")}: {sourceEntries.map(([key, source]) => `${tx(attributeLabels[key])}: ${tx(labels[source] || source)}`).join(" · ")}
        </p>
        <button type="button" disabled={disabled || !canSave} onClick={() => void save()}>
          {saving ? "Aplicando…" : scope === "profile" ? "Crear propuesta persistente" : scope === "turn" ? "Aplicar a la próxima respuesta" : "Aplicar a esta conversación"}
        </button>
        {proposal && (
          <section className="preference-proposal" aria-label="Propuesta para futuras conversaciones">
            <h3>Propuesta de preferencias persistentes</h3>
            <p>Perfil versión {proposal.profile_version}. Estas preferencias ya están activas solo en este diálogo; confirmar aquí es una decisión separada de confirmar una cita.</p>
            {proposal.stale && <Notice tone="error">El perfil cambió desde la propuesta. Descártala y vuelve a revisarla.</Notice>}
            <ul>{Object.entries(proposal.values).map(([key, value]) => <li key={key}>{tx(attributeLabels[key as SettingKey] || key)}: {value}</li>)}</ul>
            <div className="button-row">
              <button type="button" className="primary" disabled={disabled || proposal.stale} onClick={() => void decide(true)}>Confirmar guardado en el perfil</button>
              <button type="button" disabled={disabled} onClick={() => void decide(false)}>Rechazar y no guardar</button>
            </div>
          </section>
        )}
      </div>
    </details>
  );
}
