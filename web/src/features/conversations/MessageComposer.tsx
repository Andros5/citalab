import { Send } from "lucide-react";
import type { FormEvent, KeyboardEvent } from "react";

type MessageComposerProps = {
  value: string;
  busy: boolean;
  disabled: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

/** Entrada controlada del chat, incluida la protección frente a eventos IME. */
export function MessageComposer({
  value,
  busy,
  disabled,
  onChange,
  onSubmit,
}: MessageComposerProps) {
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (
      event.key === "Enter" &&
      event.ctrlKey &&
      !event.nativeEvent.isComposing &&
      value.trim() &&
      !busy &&
      !disabled
    ) {
      event.preventDefault();
      onSubmit();
    }
  };

  return (
    <form className="composer" onSubmit={submit}>
      <label htmlFor="chat-input">Tu petición administrativa</label>
      <div>
        <textarea
          id="chat-input"
          placeholder="Por ejemplo: quiero una cita por la tarde"
          value={value}
          maxLength={2000}
          rows={2}
          onChange={(event) => {
            onChange(event.target.value);
            event.target.style.height = "auto";
            event.target.style.height =
              Math.min(event.target.scrollHeight, 192) + "px";
          }}
          onKeyDown={handleKeyDown}
          disabled={busy || disabled}
        />
        <button
          className="primary"
          disabled={busy || !value.trim() || disabled}
          aria-label="Enviar mensaje"
        >
          <Send size={19} />
        </button>
      </div>
      <div className="composer-note">
        <span>No incluyas síntomas ni identificadores reales.</span>
        <span>Ctrl+Enter para enviar · {value.length}/2000</span>
      </div>
    </form>
  );
}
