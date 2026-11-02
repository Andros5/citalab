import { render } from "@testing-library/react";
import { expect, it } from "vitest";
import { AssistantText, plainAssistantText } from "./assistantText";

it("muestra como texto las entidades y etiquetas que devuelve el modelo", () => {
  expect(plainAssistantText(
    "huecos de enfermer<span></span>ía para el mi&eacute;rcoles por la ma&ntilde;ana. &iquest;Cuál le viene bien?",
  )).toBe("huecos de enfermería para el miércoles por la mañana. ¿Cuál le viene bien?");
  expect(plainAssistantText("Menos de 2 horas: 1 < 2")).toBe("Menos de 2 horas: 1 < 2");
});

it("no ejecuta ni inserta marcado y aplica solo la negrita de Markdown", () => {
  const { container } = render(
    <AssistantText text={"<img src=x onerror=alert(1)>Propuesta:\n- **Viernes a las 11:00**"} />,
  );
  expect(container.querySelector("img")).toBeNull();
  expect(container.querySelector("strong")).toHaveTextContent("Viernes a las 11:00");
  expect(container).toHaveTextContent("Propuesta: - Viernes a las 11:00");
});
