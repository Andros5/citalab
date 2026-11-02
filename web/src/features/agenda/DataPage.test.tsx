import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import type { Bootstrap } from "../../api";
import { AppContext } from "../../context";
import { LocaleProvider } from "../../i18n";
import { DataPage } from "./DataPage";

const patient = {
  user: { username: "ana", display_name: "Ana Sintética", role: "patient", subject_id: "patient-ana" },
  patients: [{ id: "patient-ana", name: "Ana Sintética", version: 1 }],
  providers: {}, models: {}, fixed_controls: {},
  config: { version: 1, config: {} },
} as unknown as Bootstrap;

afterEach(() => vi.unstubAllGlobals());

it("la agenda de un paciente no pide recursos del equipo y explica cómo consultar sus citas", async () => {
  const fetch = vi.fn(async (url: string) => ({
    ok: true,
    json: async () => url.includes("/profiles/")
      ? { subject_id: "patient-ana", version: 1, attributes: [] }
      : {},
  }));
  vi.stubGlobal("fetch", fetch);
  render(
    <LocaleProvider language="es" setLanguage={vi.fn()}>
      <AppContext.Provider value={{ bootstrap: patient, refresh: vi.fn(), notify: vi.fn() }}>
        <MemoryRouter><DataPage /></MemoryRouter>
      </AppContext.Provider>
    </LocaleProvider>,
  );
  expect(screen.getByRole("heading", { name: "Mi agenda" })).toBeInTheDocument();
  expect(screen.getByText("Consulta tus citas con el asistente")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Ir al asistente/ })).toHaveAttribute("href", "/asistente");
  expect(screen.queryByText(/Solo para el equipo investigador/)).not.toBeInTheDocument();
  await waitFor(() => expect(fetch.mock.calls.every(([url]) => !/\/(resources|catalog)\b/.test(url))).toBe(true));
});
