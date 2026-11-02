import { AlertCircle, CheckCircle2, Info, LoaderCircle, X } from "lucide-react";
import {
  cloneElement,
  isValidElement,
  useEffect,
  useId,
  useMemo,
  useRef,
  type HTMLAttributes,
  type ReactElement,
  type ReactNode,
} from "react";
import { statusLabels } from "./api";
import { acquireScrollLock } from "./shared/hooks/scrollLock";
import { tx } from "./i18n";
import { FieldInfo } from "./shared/ui/FieldInfo";

function localizeNode(node: ReactNode): ReactNode {
  if (typeof node === "string") return tx(node);
  if (Array.isArray(node)) return node.map(localizeNode);
  if (isValidElement<{ children?: ReactNode }>(node) && node.props.children)
    return cloneElement(node, undefined, localizeNode(node.props.children));
  return node;
}

export function Notice({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: "info" | "error" | "success";
}) {
  const Icon =
    tone === "error" ? AlertCircle : tone === "success" ? CheckCircle2 : Info;
  return (
    <div
      className={`notice ${tone}`}
      role={tone === "error" ? "alert" : "status"}
    >
      <Icon size={18} aria-hidden="true" />
      <div>{localizeNode(children)}</div>
    </div>
  );
}
export function Status({ value }: { value: string }) {
  return (
    <span className={`status status-${value.toLowerCase()}`}>
      <span aria-hidden="true" />
      {tx(statusLabels[value] || value)}
    </span>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="empty">
      <h3>{tx(title)}</h3>
      <p>{localizeNode(children)}</p>
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={20} /> Cargando el laboratorio…
    </div>
  );
}
export function Skeleton({
  label = "Cargando contenido…",
}: {
  label?: string;
}) {
  return (
    <div className="skeleton" role="status" aria-busy="true">
      <span className="sr-only">{tx(label)}</span>
      <span aria-hidden="true" />
      <span aria-hidden="true" />
      <span aria-hidden="true" />
    </div>
  );
}
export function ErrorState({
  message,
  retry,
  title = "No se ha podido cargar esta sección",
}: {
  message: string;
  retry?: () => void;
  title?: string;
}) {
  return (
    <section className="error-state" role="alert">
      <AlertCircle aria-hidden="true" size={24} />
      <h2>{tx(title)}</h2>
      <p>{tx(message)}</p>
      {retry && (
        <button type="button" onClick={retry}>
          {tx("Reintentar")}
        </button>
      )}
    </section>
  );
}

export function Tabs({
  label,
  value,
  onChange,
  items,
  children,
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  items: readonly { value: string; label: string }[];
  children: ReactNode;
  disabled?: boolean;
}) {
  const id = useId();
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  return (
    <>
      <div className="tabs" role="tablist" aria-label={label}>
        {items.map((item, index) => (
          <button
            key={item.value}
            type="button"
            role="tab"
            disabled={disabled}
            ref={(node) => {
              buttons.current[index] = node;
            }}
            id={`${id}-${item.value}`}
            aria-controls={`${id}-panel`}
            aria-selected={value === item.value}
            tabIndex={value === item.value ? 0 : -1}
            className={value === item.value ? "active" : ""}
            onClick={() => onChange(item.value)}
            onKeyDown={(event) => {
              let next = index;
              if (event.key === "ArrowRight") next = (index + 1) % items.length;
              else if (event.key === "ArrowLeft")
                next = (index + items.length - 1) % items.length;
              else if (event.key === "Home") next = 0;
              else if (event.key === "End") next = items.length - 1;
              else return;
              event.preventDefault();
              buttons.current[next]?.focus();
              onChange(items[next].value);
            }}
          >
            {tx(item.label)}
          </button>
        ))}
      </div>
      <div
        id={`${id}-panel`}
        role="tabpanel"
        aria-labelledby={`${id}-${value}`}
        tabIndex={0}
      >
        {children}
      </div>
    </>
  );
}
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <p className="eyebrow">{tx(eyebrow)}</p>
        <h1 tabIndex={-1}>{tx(title)}</h1>
        <p className="lede">{tx(description)}</p>
      </div>
      {actions && <div className="actions">{actions}</div>}
    </header>
  );
}
export function JsonBlock({
  data,
  label = "Datos estructurados",
}: {
  data: unknown;
  label?: string;
}) {
  const serialized = useMemo(() => JSON.stringify(data, null, 2), [data]);
  return (
      <pre className="json" tabIndex={0} aria-label={tx(label)}>
      {serialized}
    </pre>
  );
}
export function Modal({
  title,
  children,
  close,
  className,
  dialogId,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
  className?: string;
  dialogId?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  // El diálogo nativo aporta semántica; este efecto coordina scroll y devuelve
  // el foco al control que lo abrió cuando termina la interacción.
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = ref.current;
    const release = acquireScrollLock();
    try {
      dialog?.showModal();
    } catch (error) {
      release();
      throw error;
    }
    return () => {
      dialog?.close();
      release();
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, []);
  return (
    <dialog
      ref={ref}
      id={dialogId}
      className={className}
      aria-labelledby={id}
      onKeyDown={(event) => {
        if (event.key !== "Tab" || event.defaultPrevented) return;
        const dialog = event.currentTarget;
        const controls = Array.from(
          dialog.querySelectorAll<HTMLElement>(
            'a[href], button, input, select, textarea, [tabindex], [contenteditable="true"]',
          ),
        ).filter(
          (element) =>
            element.tabIndex >= 0 &&
            !element.matches(":disabled") &&
            !element.closest('[hidden], [inert], [aria-hidden="true"]') &&
            element.getClientRects().length > 0 &&
            getComputedStyle(element).visibility !== "hidden",
        );
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (!first || !last) return;
        if (
          event.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === dialog)
        ) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }}
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
    >
      <header>
        <h2 id={id}>{tx(title)}</h2>
        <button
          className="icon-button"
          type="button"
          aria-label="Cerrar diálogo"
          onClick={close}
        >
          <X size={20} />
        </button>
      </header>
      <div className="dialog-content">{children}</div>
    </dialog>
  );
}
export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  const id = useId();
  const child = isValidElement(children)
    ? (children as ReactElement<HTMLAttributes<HTMLElement>>)
    : null;
  const controlId = child?.props.id || `${id}-control`;
  const description = [
    child?.props["aria-describedby"],
    hint ? `${id}-hint` : "",
    error ? `${id}-error` : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={`field${error ? " field-invalid" : ""}`}>
      <label htmlFor={controlId}>{tx(label)}</label>
      <FieldInfo label={label} hint={hint} />
      {child
        ? cloneElement(child, {
            id: controlId,
            "aria-describedby": description || undefined,
            "aria-invalid": error ? true : child.props["aria-invalid"],
          })
        : children}
      {hint && <small id={`${id}-hint`}>{tx(hint)}</small>}
      {error && (
        <small id={`${id}-error`} className="field-error" role="alert">
          {tx(error)}
        </small>
      )}
    </div>
  );
}
