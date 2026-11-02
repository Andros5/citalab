import { useState } from "react";
import { api, setCsrf, type User } from "../../api";
import { Field } from "../../components";
import { Brand } from "../../shared/ui/Brand";
import { ThemeToggle } from "../../shared/ui/ThemeToggle";
import { LanguageSelect, tx } from "../../i18n";

// El punto focal de la portada es una cita real pidiéndose en el portal (la misma
// conversación de la figura 6.1 de la memoria): la agenda de la tarde, los turnos y,
// al margen, qué parte del sistema decidió cada paso.
// Función y no constante: así los textos se traducen con el idioma activo en cada render.
const slots = () => [
  { time: "16:00", state: "free", label: "Libre" },
  { time: "17:20", state: "booked", label: "Reservada" },
  { time: "18:00", state: "taken", label: "Ocupada" },
] as const;

const turns = [
  {
    who: "Ana",
    text: "Quiero una cita de medicina de familia esta tarde, si puede ser.",
    note: "Contexto: servicio y franja",
  },
  {
    who: "Asistente",
    text: "Hay huecos a las 16:00 y a las 17:20. ¿Cuál prefieres?",
    note: "Herramienta: huecos libres",
  },
  {
    who: "Ana",
    text: "La de las 17:20, por favor.",
    note: "Propuesta, sin tocar la agenda",
  },
  {
    who: "Ana",
    text: "Pulsa «Confirmar reserva».",
    note: "Revalidación y escritura",
  },
] as const;

export function LoginPage({ onLogin }: { onLogin: () => Promise<void> }) {
  const [username, setUsername] = useState("investigador");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <div className="access-page">
      <header className="access-header">
        <Brand />
        <div className="access-header-tools">
          <ThemeToggle />
          <LanguageSelect />
        </div>
      </header>
      <main className="access-main">
        <section className="access-intro">
          <h1>Pide una cita y mira cómo se decide.</h1>
          <p className="access-lede">
            CitaLab es el laboratorio de un Trabajo Fin de Máster: un asistente de
            citas de atención primaria con datos sintéticos. Cada propuesta,
            comprobación y confirmación queda registrada para estudiarla.
          </p>
          <figure className="slip" aria-label={tx("Ejemplo de una reserva en CitaLab")}>
            <div className="slip-head">
              <span>{tx("Medicina de familia")}</span>
              <span>{tx("Viernes 30 de octubre, tarde")}</span>
            </div>
            <div className="slip-body">
              <ol className="slip-agenda" aria-label={tx("Agenda de la tarde")}>
                {slots().map((slot) => (
                  <li key={slot.time} className={`slot slot-${slot.state}`}>
                    <time>{slot.time}</time>
                    {slot.state === "booked" ? (
                      <span className="slot-state">
                        <span className="slot-before">{tx("Propuesta")}</span>
                        <span className="slot-after">{tx(slot.label)}</span>
                      </span>
                    ) : (
                      <span className="slot-state">{tx(slot.label)}</span>
                    )}
                  </li>
                ))}
              </ol>
              <ol className="slip-turns">
                {turns.map((turn, index) => (
                  <li key={index}>
                    <p>
                      <b>{tx(turn.who)}</b> {tx(turn.text)}
                    </p>
                    <small>{tx(turn.note)}</small>
                  </li>
                ))}
              </ol>
            </div>
            <figcaption>
              {tx(
                "La agenda no cambia hasta que la persona confirma; entonces se vuelve a comprobar el hueco y se escribe la cita.",
              )}
            </figcaption>
          </figure>
        </section>
        <section className="access-card" aria-labelledby="access-title">
          <h2 id="access-title">Entrar</h2>
          <p>Usa una cuenta de la base de datos sintética.</p>
          <form
            onSubmit={async (event) => {
              event.preventDefault();
              setBusy(true);
              setError("");
              try {
                const result = await api<{ user: User; csrf: string }>(
                  "/auth/login",
                  "POST",
                  { username, password },
                );
                setCsrf(result.csrf);
                setPassword("");
                await onLogin();
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <Field label="Cuenta de demostración">
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
                maxLength={80}
              />
            </Field>
            <Field
              label="Código de acceso"
              hint="Usa exclusivamente el código local de esta cuenta; no una contraseña sanitaria real."
              error={error}
            >
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                maxLength={200}
              />
            </Field>
            <button className="primary full" disabled={busy}>
              {busy ? "Verificando acceso…" : "Entrar al laboratorio"}
            </button>
          </form>
          <div className="access-help">
            <h3>¿Es tu primer acceso?</h3>
            <p>
              Las cuentas y códigos iniciales están en{" "}
              <code>output/portal/accesos-iniciales.txt</code>, dentro del
              proyecto. El administrador puede generar nuevos códigos desde
              Administración.
            </p>
          </div>
        </section>
      </main>
      <footer className="access-footer">
        <p>
          Prototipo académico con datos sintéticos. No está conectado con el SAS,
          ClicSalud+ ni la Junta de Andalucía.
        </p>
      </footer>
    </div>
  );
}
