import type { ReactNode } from "react";

const MARKUP = /&(?:[a-z]+|#\d+|#x[\da-f]+);|<\/?[a-z][^>]*>/i;

/**
 * Texto que el modelo devolvió con marcas de HTML (entidades como `&eacute;` o
 * etiquetas vacías). Se interpreta solo para leer su texto: el resultado se
 * pinta como texto plano y nunca se inserta como HTML.
 */
export function plainAssistantText(text: string): string {
  if (!MARKUP.test(text) || typeof DOMParser === "undefined") return text;
  const parsed = new DOMParser().parseFromString(text, "text/html");
  return parsed.body.textContent ?? text;
}

/** Párrafos del asistente con la negrita de Markdown (`**texto**`) aplicada. */
export function AssistantText({ text }: { text: string }) {
  return (
    <p>
      {plainAssistantText(text)
        .split(/(\*\*[^*\n]+\*\*)/)
        .map((part, index): ReactNode =>
          part.length > 4 && part.startsWith("**") && part.endsWith("**")
            ? <strong key={index}>{part.slice(2, -2)}</strong>
            : part,
        )}
    </p>
  );
}
