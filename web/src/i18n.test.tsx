import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, it } from "vitest";
import { Brand } from "./shared/ui/Brand";
import {
  LanguageSelect,
  LocaleProvider,
  tx,
  useLocale,
  type UiLanguage,
} from "./i18n";

function LanguageProbe() {
  const { language } = useLocale();
  return <p>{`${language}:${tx("Idioma de la interfaz")}`}</p>;
}

function Harness() {
  const [language, setLanguage] = useState<UiLanguage>("es");
  return (
    <LocaleProvider language={language} setLanguage={setLanguage}>
      <LanguageSelect />
      <LanguageProbe />
      <Brand />
    </LocaleProvider>
  );
}

it("switches interface copy and document language between Spanish and English", () => {
  render(<Harness />);
  expect(screen.getByText("es:Idioma de la interfaz")).toBeVisible();
  expect(document.documentElement.lang).toBe("es");

  fireEvent.change(screen.getByRole("combobox", { name: "Idioma de la interfaz" }), {
    target: { value: "en" },
  });

  expect(screen.getByText("en:Interface language")).toBeVisible();
  expect(screen.getByRole("option", { name: "Spanish" })).toBeVisible();
  expect(document.documentElement.lang).toBe("en");
  expect(document.title).toBe("CitaLab · Agent laboratory");
  expect(document.querySelector(".brand > span:last-child")?.textContent).toContain("CitaLab");
  expect(document.querySelector(".brand")?.textContent).not.toContain("AppointmentLab");
  expect(tx("Cita")).toBe("Appointment");
  expect(tx("Historial de conversaciones")).toBe("Conversation history");
  expect(tx("conversaciones cargadas")).toBe("conversations loaded");
  for (const status of ["Lista para empezar", "Pendiente de confirmar", "Necesita aclaración", "Gestión completada", "Operación bloqueada", "Propuesta descartada", "Datos restaurados", "Escenario actualizado: revisar petición", "Fallida"]) {
    expect(tx(status)).not.toBe(status);
  }
});
