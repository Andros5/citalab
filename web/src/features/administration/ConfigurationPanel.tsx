import { LockKeyhole } from "lucide-react";
import { useState } from "react";
import type { PortalConfig } from "../../api";
import { api } from "../../api";
import { tx } from "../../i18n";
import { FieldInfo } from "../../shared/ui/FieldInfo";
import { providerName } from "./adminHelp";
import { Field, JsonBlock, Notice } from "../../components";
import { useApp } from "../../context";
import {
  useDraftStatus,
  useSessionDraft,
} from "../../shared/hooks/sessionDrafts";
const getParameterLabels = (): {
  key: keyof PortalConfig;
  label: string;
  hint: string;
  min: number;
  max: number;
  step?: number;
}[] => [
  {
    key: "max_calls",
    label: "Máximo de llamadas por turno (M5/S1)",
    hint: "Presupuesto del ciclo de agentes. Una confirmación es otro turno.",
    min: 1,
    max: 20,
  },
  {
    key: "daily_call_limit",
    label: "Límite diario de intentos remotos",
    hint: "Límite global local, por día UTC; incluye intentos fallidos. No garantiza la gratuidad de la cuenta del proveedor.",
    min: 1,
    max: 1000,
  },
  {
    key: "timeout_seconds",
    label: "Espera máxima por llamada (segundos)",
    hint: "Límite de una llamada, no del turno completo.",
    min: 5,
    max: 60,
  },
  {
    key: "temperature",
    label: "Temperatura",
    hint: "0 favorece consistencia. Aumentarla introduce variación; no equivale a mejorar la calidad.",
    min: 0,
    max: 0.7,
    step: 0.1,
  },
  {
    key: "max_output_tokens",
    label: "Máximo de tokens de salida",
    hint: "Tope por llamada. Un valor insuficiente puede truncar la respuesta estructurada.",
    min: 256,
    max: 2400,
  },
  {
    key: "session_minutes",
    label: "Duración del acceso (minutos)",
    hint: "Caducidad absoluta para nuevas sesiones. Cerrar sesión invalida la cookie.",
    min: 5,
    max: 240,
  },
  {
    key: "retention_days",
    label: "Retención de conversaciones (días)",
    hint: "Limpieza al arrancar, cada hora o mediante acción manual. Incluye auditoría e instantáneas caducadas; no elimina la agenda actual.",
    min: 1,
    max: 90,
  },
  {
    key: "diagnostic_days",
    label: "Retención de diagnóstico (días)",
    hint: "Entradas y salidas capturadas opcionalmente. Los metadatos permanecen hasta la retención general.",
    min: 1,
    max: 30,
  },
];

export function ConfigurationPanel() {
  const parameterLabels = getParameterLabels();
  const { bootstrap, refresh, notify } = useApp();
  const admin = bootstrap.user.role === "admin";
  const [config, setConfig] = useSessionDraft(
    "admin-config",
    bootstrap.config.config,
  );
  const [reason, setReason] = useSessionDraft("admin-config-reason", "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const dirty =
    admin && JSON.stringify(config) !== JSON.stringify(bootstrap.config.config);
  useDraftStatus("configuration", dirty);
  if (!admin)
    return (
      <section className="panel">
        <h2>Configuración vigente · r{bootstrap.config.version}</h2>
        <p className="muted">
          Valores de consulta, seleccionables y copiables. Esta cuenta no puede
          publicarlos.
        </p>
        <dl className="readable-settings">
          <div>
            <dt>Arquitectura predeterminada</dt>
            <FieldInfo label="Arquitectura predeterminada" />
            <dd>{bootstrap.config.config.default_architecture}</dd>
          </div>
          <div>
            <dt>Proveedor predeterminado</dt>
            <FieldInfo label="Proveedor predeterminado" />
            <dd>{providerName(bootstrap.config.config.default_provider)}</dd>
          </div>
          <div>
            <dt>Llamadas externas</dt>
            <FieldInfo label="Permitir llamadas a proveedores externos" />
            <dd>
              {bootstrap.config.config.remote_enabled
                ? "Permitidas"
                : "Pausadas"}
            </dd>
          </div>
          <div>
            <dt>Recuperación de errores transitorios</dt>
            <FieldInfo label="Recuperación de errores transitorios"
              hint="Se aplica igual a Groq y Gemini en nuevas conversaciones. Cada envío consume presupuesto. No reintenta cuotas, contratos inválidos ni operaciones administrativas." />
            <dd>{tx(bootstrap.config.config.recovery_policy_version === "bounded-transient-v2"
              ? "Hasta tres intentos; respeta Retry-After hasta 30 s"
              : bootstrap.config.config.recovery_policy_version === "bounded-transient-v1"
                ? "Hasta tres intentos con espera progresiva" : "Un intento por inferencia")}</dd>
          </div>
          {parameterLabels.map((item) => (
            <div key={item.key}>
              <dt>
                {item.label}
                <small>{item.hint}</small>
              </dt>
              <FieldInfo label={item.label} hint={item.hint} />
              <dd>{String(bootstrap.config.config[item.key])}</dd>
            </div>
          ))}
        </dl>
        <details className="details">
          <summary>Controles no configurables</summary>
          <JsonBlock
            data={bootstrap.fixed_controls}
            label="Controles fijos del sistema"
          />
        </details>
      </section>
    );
  return (
    <>
      {error && (
        <Notice tone="error">
          {error}
          <button
            onClick={() => void refresh().catch((e) => setError(e.message))}
          >
            Actualizar versión vigente
          </button>
        </Notice>
      )}
      {dirty && (
        <Notice>
          Configuración sin guardar. El borrador se conserva durante la sesión.
          <button
            onClick={() => {
              if (window.confirm("¿Descartar la configuración sin guardar?")) {
                setConfig(bootstrap.config.config);
                setReason("");
              }
            }}
          >
            Descartar configuración
          </button>
        </Notice>
      )}
      {dirty && (
        <details className="details">
          <summary>Comparar configuración vigente y borrador</summary>
          <h3>Vigente · r{bootstrap.config.version}</h3>
          <JsonBlock
            data={bootstrap.config.config}
            label="Configuración vigente"
          />
          <h3>Borrador</h3>
          <JsonBlock data={config} label="Borrador de configuración" />
        </details>
      )}
      <div className="settings-layout">
        <section className="panel">
          <div className="section-heading">
            <h2>Parámetros de ejecución</h2>
            <span className="architecture-tag">
              r{bootstrap.config.version}
            </span>
          </div>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              try {
                await api("/admin/config", "PUT", {
                  expected_version: bootstrap.config.version,
                  config,
                  reason,
                });
                await refresh();
                setReason("");
                notify(
                  "Configuración publicada. Se aplicará a nuevas conversaciones; la pausa remota es inmediata antes de cada llamada.",
                );
              } catch (error) {
                setError((error as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <div className="admin-remote-toggle">
              <label className="check-row toggle-row">
                <input
                  type="checkbox"
                  checked={config.remote_enabled}
                  disabled={!admin || busy}
                  onChange={(e) =>
                    setConfig({ ...config, remote_enabled: e.target.checked })
                  }
                />
                <span>
                  Permitir llamadas a proveedores externos
                  <small>
                    Utiliza las claves ya configuradas. No activa facturación ni
                    cambia de proveedor automáticamente.
                  </small>
                </span>
              </label>
              <FieldInfo label="Permitir llamadas a proveedores externos" />
            </div>
            <div className="form-grid">
              <Field label="Arquitectura predeterminada">
                <select
                  disabled={!admin || busy}
                  value={config.default_architecture}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      default_architecture: e.target.value,
                    })
                  }
                >
                  {["M5", "S1", "H"].map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </Field>
              <Field label="Proveedor predeterminado">
                <select
                  disabled={!admin || busy}
                  value={config.default_provider}
                  onChange={(e) =>
                    setConfig({ ...config, default_provider: e.target.value })
                  }
                >
                  <option value="groq">Groq</option>
                  <option value="google">Gemini</option>
                </select>
              </Field>
              <Field label="Recuperación de errores transitorios">
                <select value={config.recovery_policy_version ?? "single-attempt-v1"}
                  disabled={busy} onChange={e => setConfig({...config,
                    recovery_policy_version: e.target.value as PortalConfig["recovery_policy_version"]})}>
                  <option value="single-attempt-v1">Un intento por inferencia</option>
                  <option value="bounded-transient-v1">Hasta tres intentos con espera progresiva</option>
                  <option value="bounded-transient-v2">Hasta tres intentos; respeta Retry-After hasta 30 s</option>
                </select>
              </Field>
            </div>
            {[
              {
                title: "Generación y tiempos",
                keys: ["temperature", "max_output_tokens", "timeout_seconds"],
              },
              {
                title: "Presupuesto del portal",
                keys: ["max_calls", "daily_call_limit"],
              },
              {
                title: "Acceso y conservación",
                keys: ["session_minutes", "retention_days", "diagnostic_days"],
              },
            ].map((group) => (
              <fieldset className="admin-parameter-group" key={group.title}>
                <legend>{tx(group.title)}</legend>
                <div className="form-grid">
                  {parameterLabels
                    .filter((item) => group.keys.includes(item.key))
                    .map((item) => (
                      <Field label={item.label} hint={item.hint} key={item.key}>
                        <input
                          type="number"
                          min={item.min}
                          max={item.max}
                          step={item.step || 1}
                          required
                          disabled={!admin || busy}
                          value={Number(config[item.key])}
                          onChange={(e) =>
                            setConfig({
                              ...config,
                              [item.key]: Number(e.target.value),
                            })
                          }
                        />
                      </Field>
                    ))}
                </div>
              </fieldset>
            ))}
            {admin && (
              <>
                <Field label="Motivo de la nueva configuración">
                  <input
                    required
                    minLength={5}
                    maxLength={300}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                </Field>
                <button className="primary" disabled={busy}>
                  Publicar configuración
                </button>
              </>
            )}
          </form>
        </section>
        <aside className="settings-aside">
          <section className="panel">
            <LockKeyhole size={24} />
            <h2>Controles que no se desactivan</h2>
            <p>
              La interfaz no permite deshabilitar confirmaciones, permisos,
              límites clínicos ni validación estructurada.
            </p>
            <JsonBlock data={bootstrap.fixed_controls} />
          </section>
          <section className="panel">
            <h3>Proveedores disponibles</h3>
            {["groq", "google"].map((key) => (
              <div className="connection" key={key}>
                <strong>{key === "google" ? "Gemini" : "Groq"}</strong>
                <span>
                  {bootstrap.providers[key]
                    ? tx("Clave presente")
                    : tx("Sin clave")}
                </span>
                <small>{bootstrap.models[key]}</small>
                <FieldInfo label="Modelo de conexión" />
                {bootstrap.config.config.default_provider === key && (
                  <span className="architecture-tag">Predeterminado</span>
                )}
              </div>
            ))}
            <p className="muted">
              Ambos proveedores pueden seleccionarse. Una clave presente no
              acredita disponibilidad ni cuota suficiente.
            </p>
            <p className="muted">
              Esta sección no consulta el saldo ni la facturación oficiales. El
              administrador puede auditar el registro local en Consumo y cuotas
              API. Las claves se configuran en el entorno local y nunca se
              envían al navegador. Los nombres de modelo sí se muestran para
              identificar el experimento.
            </p>
          </section>
        </aside>
      </div>
    </>
  );
}
