/// <reference types="vite/client" />
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Field } from "../../components";
import { AppContext } from "../../context";
import { LocaleProvider, translateText } from "../../i18n";
import type { Bootstrap } from "../../api";
import { FieldHelpContext } from "../../shared/ui/FieldInfo";
import { adminFieldHelp, fieldDescriptions, sectionHelp } from "./adminHelp";
import { AdminPage } from "./AdminPage";

afterEach(() => vi.unstubAllGlobals());

const sources = import.meta.glob("./*.tsx", {
  query: "?raw",
  import: "default",
  eager: true,
});
it("documenta cada etiqueta literal de formulario administrativo", () => {
  for (const [path, source] of Object.entries(sources)) {
    if (path.endsWith(".test.tsx")) continue;
    for (const match of String(source).matchAll(
      /<(?:Field|FieldInfo)\s+label="([^"]+)"/g,
    )) {
      expect(fieldDescriptions[match[1]], `${path}: ${match[1]}`).toBeDefined();
    }
  }
  for (const pair of Object.values(fieldDescriptions))
    expect(pair.every(Boolean)).toBe(true);
  for (const pair of Object.values(sectionHelp))
    expect(pair.every(Boolean)).toBe(true);
});

it("la ayuda es accesible, no envía formularios y se cierra con Escape", () => {
  const submit = vi.fn();
  render(
    <LocaleProvider language="es" setLanguage={vi.fn()}>
      <FieldHelpContext.Provider
        value={(label) => adminFieldHelp("config", label)}
      >
        <form onSubmit={submit}>
          <Field label="Temperatura">
            <input defaultValue="0" />
          </Field>
        </form>
      </FieldHelpContext.Provider>
    </LocaleProvider>,
  );
  const info = screen.getByRole("button", {
    name: "Información sobre Temperatura",
  });
  expect(screen.getByLabelText("Temperatura")).toHaveValue("0");
  expect(info).toHaveAttribute("type", "button");
  fireEvent.click(info);
  expect(info).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("note")).toHaveTextContent("Groq y Gemini");
  expect(screen.getByRole("note")).toHaveTextContent(
    "No cambia una campaña congelada",
  );
  fireEvent.keyDown(info, { key: "Escape" });
  expect(info).toHaveAttribute("aria-expanded", "false");
  expect(submit).not.toHaveBeenCalled();
});

it("no añade botones fuera de Administración", () => {
  render(
    <Field label="Fuera">
      <input />
    </Field>,
  );
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

it("ofrece ayuda bilingüe sin cambiar su significado ni confundir planificación y ejecución", () => {
  render(
    <LocaleProvider language="en" setLanguage={vi.fn()}>
      <FieldHelpContext.Provider
        value={(label) => adminFieldHelp("conversation-evaluation", label)}
      >
        <Field label="Modelo para M5">
          <select>
            <option>Gemini</option>
          </select>
        </Field>
      </FieldHelpContext.Provider>
    </LocaleProvider>,
  );
  fireEvent.click(screen.getByRole("button"));
  expect(screen.getByRole("note")).toHaveTextContent(
    "does not change the portal provider or start calls",
  );
  expect(screen.getByRole("note")).toHaveTextContent(
    "does not start or authorize a campaign",
  );
  const translated = adminFieldHelp(
    "config",
    translateText("Proveedor predeterminado", "en"),
  );
  expect(translated.description).toContain(
    "Groq and Gemini are equivalent alternatives",
  );
});

const bootstrap: Bootstrap = {
  user: {
    username: "test",
    display_name: "Test",
    role: "admin",
    subject_id: null,
  },
  patients: [],
  providers: { groq: true, google: true },
  models: { groq: "groq-test", google: "gemini-test" },
  fixed_controls: {},
  config: {
    version: 1,
    config: {
      default_provider: "groq",
      default_architecture: "M5",
      remote_enabled: false,
      max_calls: 12,
      daily_call_limit: 100,
      timeout_seconds: 30,
      temperature: 0,
      max_output_tokens: 1200,
      session_minutes: 60,
      retention_days: 30,
      diagnostic_days: 7,
    },
  },
};
const mount = (role: "admin" | "researcher", provider = "groq") =>
  render(
    <LocaleProvider language="es" setLanguage={vi.fn()}>
      <AppContext.Provider
        value={{
          bootstrap: {
            ...bootstrap,
            user: { ...bootstrap.user, role },
            config: {
              ...bootstrap.config,
              config: {
                ...bootstrap.config.config,
                default_provider: provider,
              },
            },
          },
          refresh: vi.fn(),
          notify: vi.fn(),
        }}
      >
        <AdminPage />
      </AppContext.Provider>
    </LocaleProvider>,
  );

it.each(["groq", "google"])(
  "el predeterminado %s no concede prioridad funcional a un proveedor",
  (provider) => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const { container } = mount("admin", provider);
    const connections = Array.from(container.querySelectorAll(".connection"));
    expect(connections).toHaveLength(2);
    expect(
      connections.map((row) => row.querySelector("strong")?.textContent),
    ).toEqual(["Groq", "Gemini"]);
    expect(
      connections.filter((row) => row.textContent?.includes("Predeterminado")),
    ).toHaveLength(1);
    expect(screen.getByLabelText("Proveedor predeterminado")).toHaveValue(
      provider,
    );
    expect(screen.getByLabelText("Temperatura")).toBeEnabled();
    expect(screen.getByLabelText("Máximo de tokens de salida")).toBeEnabled();
    expect(container.querySelectorAll(".field")).toHaveLength(
      container.querySelectorAll(".field .field-info-button").length,
    );
    fireEvent.click(
      screen.getByRole("button", {
        name: "Información sobre Proveedor predeterminado",
      }),
    );
    expect(fetch).not.toHaveBeenCalled();
  },
);

it("mantiene el modo de consulta y los apartados exclusivos de administración", () => {
  mount("researcher");
  expect(
    screen.queryByRole("button", { name: "Publicar configuración" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("tab", { name: "Cuentas" }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", {
      name: "Información sobre Proveedor predeterminado",
    }),
  ).toBeEnabled();
});

it("actualiza los parámetros y su ayuda al alternar inglés y español", () => {
  const page = (language: "en" | "es") => (
    <LocaleProvider language={language} setLanguage={vi.fn()}>
      <AppContext.Provider
        value={{ bootstrap, refresh: vi.fn(), notify: vi.fn() }}
      >
        <AdminPage />
      </AppContext.Provider>
    </LocaleProvider>
  );
  const view = render(page("en"));
  expect(screen.getByLabelText("Temperature")).toHaveValue(0);
  fireEvent.click(
    screen.getByRole("button", {
      name: "Information about Temperature",
    }),
  );
  expect(screen.getByRole("note")).toHaveTextContent(
    "Generation variability for Groq and Gemini",
  );
  view.rerender(page("es"));
  expect(screen.getByLabelText("Temperatura")).toHaveValue(0);
  expect(screen.getByRole("note")).toHaveTextContent(
    "Variación de generación para Groq y Gemini",
  );
  view.rerender(page("en"));
  expect(screen.getByLabelText("Maximum output tokens")).toHaveValue(1200);
});
