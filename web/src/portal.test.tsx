import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import axe from "axe-core";
import {
  api,
  ApiError,
  setCsrf,
  type Bootstrap,
  type Call,
  type Conversation,
} from "./api";
import { AppContext } from "./context";
import { Field, Modal } from "./components";
import { CallInspector, ChatPage, HistoryPage } from "./pages/conversations";
import { LocaleProvider } from "./i18n";

const bootstrap: Bootstrap = {
  user: {
    username: "investigador",
    display_name: "Investigador",
    role: "admin",
    subject_id: null,
  },
  patients: [{ id: "patient-ana", name: "Ana Sintética", version: 1 }],
  providers: { groq: true },
  models: { groq: "test" },
  fixed_controls: {},
  config: {
    version: 1,
    config: {
      default_architecture: "M5",
      default_provider: "groq",
      remote_enabled: false,
      max_calls: 12,
      timeout_seconds: 20,
      temperature: 0,
      max_output_tokens: 1200,
      daily_call_limit: 120,
      retention_days: 30,
      diagnostic_days: 7,
      session_minutes: 60,
    },
  },
};
const call: Call = {
  id: "call-1",
  agent: "context",
  status: "success",
  started_at: "2026-08-30T10:00:00Z",
  prompt_version: "test-v1",
  prompt_hash: "test-hash",
  system_prompt: "Plantilla sintética",
  schema: { type: "object" },
  model: "test",
  provider: "offline",
};
function wrapper(
  component: React.ReactNode,
  path = "/asistente",
  data = bootstrap,
) {
  return render(
    <LocaleProvider language="es" setLanguage={vi.fn()}>
      <AppContext.Provider
        value={{ bootstrap: data, refresh: vi.fn(), notify: vi.fn() }}
      >
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/asistente/:id?" element={component} />
            <Route path="/conversaciones" element={component} />
          </Routes>
        </MemoryRouter>
      </AppContext.Provider>
    </LocaleProvider>,
  );
}
afterEach(() => vi.unstubAllGlobals());
describe("Contratos de presentación y acceso", () => {
  it("ignora la respuesta tardía de una conversación tras cambiar de ruta", async () => {
    let finishOld!: (value: unknown) => void;
    const current: Conversation = {
      id: "c2",
      owner: "investigador",
      subject_id: "patient-ana",
      subject_name: "Perfil actual",
      title: "Conversación actual",
      architecture: "M5",
      provider: "offline",
      status: "READY",
      diagnostic: false,
      created_at: "2026-09-05",
      updated_at: "2026-09-05",
      turn_count: 0,
      active_job: null,
      archived: false,
      can_confirm: false,
      turns: [],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        url.endsWith("/c1")
          ? new Promise((resolve) => {
              finishOld = resolve;
            })
          : Promise.resolve({ ok: true, json: async () => current }),
      ),
    );
    wrapper(
      <>
        <Link to="/asistente/c2">Cambiar conversación</Link>
        <ChatPage />
      </>,
      "/asistente/c1",
    );
    fireEvent.click(screen.getByRole("link", { name: "Cambiar conversación" }));
    expect(await screen.findByText("Perfil actual")).toBeInTheDocument();
    await act(async () =>
      finishOld({
        ok: true,
        json: async () => ({
          ...current,
          id: "c1",
          subject_name: "Perfil obsoleto",
        }),
      }),
    );
    expect(screen.queryByText("Perfil obsoleto")).not.toBeInTheDocument();
    expect(screen.getByText("Perfil actual")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Nueva conversación" }),
    ).toBeInTheDocument();
  });
  it("evita duplicar la acción de nueva conversación en la pantalla inicial", () => {
    wrapper(<ChatPage />);
    expect(
      screen.queryByRole("button", { name: "Nueva conversación" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Iniciar una conversación" }),
    ).toBeInTheDocument();
  });
  it("avisa del entorno sintético sin exigir una casilla y ofrece los dos proveedores", async () => {
    wrapper(<ChatPage />);
    fireEvent.click(
      screen.getByRole("button", { name: "Iniciar una conversación" }),
    );
    expect(
      screen.getByRole("button", { name: "Crear conversación" }),
    ).toBeEnabled();
    expect(screen.getByText("Solo datos sintéticos. No introduzcas información personal real.")).toBeInTheDocument();
    const engine = screen.getByRole("combobox", { name: "Motor de ejecución" });
    expect(
      Array.from(engine.querySelectorAll("option"), (option) => option.value),
    ).toEqual(["groq", "google"]);
    expect(
      screen.queryByRole("checkbox", {
        name: "Confirmo que usaré únicamente datos sintéticos.",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Crear conversación" }),
    ).toBeEnabled();
  });
  it("no ofrece controles de laboratorio al paciente", () => {
    wrapper(<ChatPage />, "/asistente", {
      ...bootstrap,
      user: {
        ...bootstrap.user,
        username: "patient-ana",
        role: "patient",
        subject_id: "patient-ana",
      },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Iniciar una conversación" }),
    );
    expect(
      screen.queryByRole("combobox", { name: "Arquitectura" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "Cuenta del paciente" }),
    ).toBeDisabled();
  });
  it("avisa antes de crear si el escenario no tiene disponibilidad futura", () => {
    wrapper(<ChatPage />, "/asistente", {
      ...bootstrap,
      catalog: {
        scenario: {
          id: "legacy-v1",
          version: "1.1.0",
          sha256: "test",
          require_explicit_service: false,
        },
        services: [],
        schedules: [],
        availability: { free_slots: 2, future_free_slots: 0 },
      },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Iniciar una conversación" }),
    );
    expect(screen.getByText(/Escenario activo: legacy-v1/)).toBeInTheDocument();
    expect(
      screen.getByText(/no contiene huecos libres futuros/),
    ).toBeInTheDocument();
  });
  it("no inventa entrada ni consumo ausentes", () => {
    render(<CallInspector calls={[call]} />);
    fireEvent.click(screen.getByRole("button", { name: /01 Contexto/ }));
    expect(screen.getByText("Plantilla sintética")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Entrada" }));
    expect(screen.getByText(/Contenido no capturado/)).toBeInTheDocument();
    expect(screen.getByText(/no comunicó el consumo de tokens/)).toBeInTheDocument();
    expect(screen.queryByText(/n\/d/)).not.toBeInTheDocument();
  });
  it("distingue contrato válido de uso efectivo de la salida", () => {
    render(
      <CallInspector
        calls={[call]}
        executionTrace={[
          {
            component: "context",
            contract_status: "valid",
            effective_values: { modality: "phone" },
            discard_reasons: ["requested_date:not-grounded"],
          },
        ]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /01 Contexto/ }));
    expect(screen.getByText(/Los controles del sistema deciden después/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Uso efectivo" }));
    expect(screen.getByText(/requested_date:not-grounded/)).toBeInTheDocument();
    expect(screen.getByText(/"modality": "phone"/)).toBeInTheDocument();
  });
  it("declara la ausencia de delta en turnos históricos", () => {
    render(<CallInspector calls={[call]} />);
    fireEvent.click(screen.getByRole("button", { name: /01 Contexto/ }));
    fireEvent.click(screen.getByRole("tab", { name: "Uso efectivo" }));
    expect(screen.getByText(/no conserva un delta capturado/)).toBeInTheDocument();
    expect(screen.getByText(/No se reconstruye retrospectivamente/)).toBeInTheDocument();
  });
  it("escapa HTML recibido, sin interpretar scripts", () => {
    render(
      <CallInspector
        calls={[{ ...call, system_prompt: '<img src=x onerror="alert(1)">' }]}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /01 Contexto/ }));
    expect(document.querySelector("img")).toBeNull();
    expect(screen.getByText(/<img src=x/)).toBeInTheDocument();
  });
  it("permite inspeccionar turnos anteriores y bloquea edición de otra cuenta", async () => {
    const conversation: Conversation = {
      id: "c1",
      owner: "other",
      subject_id: "patient-ana",
      subject_name: "Ana",
      title: "Prueba",
      architecture: "M5",
      provider: "offline",
      status: "COMPLETED",
      diagnostic: false,
      created_at: "2026-08-30",
      updated_at: "2026-08-30",
      turn_count: 2,
      active_job: null,
      archived: false,
      can_confirm: false,
      read_only: true,
      turns: [
        {
          id: "t1",
          number: 1,
          request: "Petición",
          response: "Propuesta",
          status: "NEEDS_CONFIRMATION",
          at: "2026-08-30",
          calls: [call],
        },
        {
          id: "t2",
          number: 2,
          request: "Confirmo",
          response: "Registrada",
          status: "COMPLETED",
          at: "2026-08-30",
          calls: [],
        },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => conversation }),
    );
    wrapper(<ChatPage />, "/asistente/c1");
    expect(
      await screen.findByText(/Revisión de otra cuenta/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: "Tu petición administrativa" }),
    ).toBeDisabled();
    fireEvent.change(
      screen.getByRole("combobox", {
        name: "Ejecución que deseas inspeccionar",
      }),
      { target: { value: "t1" } },
    );
    expect(
      screen.getByRole("button", { name: /01 Contexto/ }),
    ).toBeInTheDocument();
  });
  it("presenta el historial vacío sin métricas ficticias", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ items: [], total: 0, page: 1, page_size: 20 }),
      }),
    );
    wrapper(<HistoryPage />, "/conversaciones");
    expect(
      await screen.findByText("No hay conversaciones en esta vista"),
    ).toBeInTheDocument();
  });
  it("carga filas al acercarse al final, sin reemplazar las anteriores", async () => {
    let intersect!: IntersectionObserverCallback;
    const disconnect = vi.fn();
    vi.stubGlobal("IntersectionObserver", class {
      constructor(callback: IntersectionObserverCallback) { intersect = callback; }
      observe = vi.fn();
      disconnect = disconnect;
    });
    const historyItem = (i: number) => ({
      id: `history-${i}`, title: `Sesión ${i}`, subject_name: "Ana Sintética",
      architecture: "M5", provider: "offline", status: "READY", turn_count: 0,
    });
    const fetch = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({
      items: Array.from({ length: 20 }, (_, i) => historyItem(i)), total: 21,
    }) }).mockResolvedValueOnce({ ok: true, json: async () => ({ items: [historyItem(20)], total: 21 }) });
    vi.stubGlobal("fetch", fetch);
    const { unmount } = wrapper(<HistoryPage />, "/conversaciones");
    expect(await screen.findByText("Sesión 0")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(typeof intersect).toBe("function"));
    act(() => intersect([{ isIntersecting: true }] as IntersectionObserverEntry[], {} as IntersectionObserver));
    expect(await screen.findByText("Sesión 20")).toBeInTheDocument();
    expect(screen.getByText("Sesión 0")).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(22);
    expect(fetch).toHaveBeenCalledTimes(2);
    unmount();
    expect(disconnect).toHaveBeenCalled();
  });
  it("ofrece carga manual sin IntersectionObserver y mantiene el filtro de estado", async () => {
    vi.stubGlobal("IntersectionObserver", undefined);
    const item = (id: string) => ({ id, title: id, architecture: "M5", provider: "offline", status: "READY" });
    const fetch = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({
      items: Array.from({ length: 20 }, (_, i) => item(`c-${i}`)), total: 21,
    }) }).mockResolvedValueOnce({ ok: true, json: async () => ({ items: [item("c-20")], total: 21 }) });
    vi.stubGlobal("fetch", fetch);
    wrapper(<HistoryPage />, "/conversaciones?status=READY");
    fireEvent.click(await screen.findByRole("button", { name: "Cargar más conversaciones" }));
    expect(await screen.findByText("c-20")).toBeInTheDocument();
    expect(fetch.mock.calls[1][0]).toContain("status=READY&page=2");
  });
  it("no muestra métricas ni exportación del equipo a pacientes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({
      items: [{ id: "own", title: "Mi sesión", architecture: "M5", provider: "offline", status: "READY" }], total: 1,
    }) }));
    wrapper(<HistoryPage />, "/conversaciones?architecture=H", {
      ...bootstrap, user: { ...bootstrap.user, role: "patient", subject_id: "patient-ana" },
    });
    expect(await screen.findByText("Mi sesión")).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Filtrar por arquitectura" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Consumo" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Exportar Mi sesión" })).not.toBeInTheDocument();
  });
  it.each([
    ["offline", false, "Sin API remota"],
    ["groq", false, "No disponible"],
    ["groq", true, "tokens conocidos"],
  ])(
    "distingue consumo nulo y desconocido en historial (%s, completo=%s)",
    async (provider, tokens_complete, expected) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          json: async () => ({
            items: [
              {
                id: "c-tokens",
                title: "Prueba de consumo",
                subject_name: "Ana Sintética",
                architecture: "M5",
                provider,
                status: "READY",
                turn_count: 1,
                updated_at: "2026-09-06",
                total_known_tokens: 0,
                tokens_complete,
              },
            ],
            total: 1,
            page: 1,
            page_size: 20,
          }),
        }),
      );
      wrapper(<HistoryPage />, "/conversaciones");
      expect(await screen.findByText(expected)).toBeInTheDocument();
      expect(screen.getByText("1 turno")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Archivar Prueba de consumo" }),
      ).toBeInTheDocument();
    },
  );
  it("el diálogo tiene nombre, campos etiquetados y cierre por Escape", async () => {
    const close = vi.fn();
    const { unmount } = render(
      <Modal title="Editar preferencia" close={close}>
        <Field label="Idioma">
          <select defaultValue="es">
            <option value="es">Español</option>
          </select>
        </Field>
      </Modal>,
    );
    const dialog = screen.getByRole("dialog", { name: "Editar preferencia" });
    expect(document.documentElement.style.overflow).toBe("hidden");
    expect(document.body.style.overflow).toBe("hidden");
    expect(
      screen.getByRole("combobox", { name: "Idioma" }),
    ).toBeInTheDocument();
    // jsdom no calcula contraste o geometría: se revisan visualmente en navegador.
    const result = await axe.run(dialog, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(result.violations.map((v) => v.id)).toEqual([]);
    fireEvent(dialog, new Event("cancel", { bubbles: true, cancelable: true }));
    expect(close).toHaveBeenCalledOnce();
    unmount();
    expect(document.documentElement.style.overflow).toBe("");
    expect(document.body.style.overflow).toBe("");
  });
  it("la pantalla del asistente supera las reglas estructurales de axe", async () => {
    const { container } = wrapper(<ChatPage />);
    const result = await axe.run(container, {
      rules: {
        "color-contrast": { enabled: false },
        region: { enabled: false },
      },
    });
    expect(result.violations.map((v) => v.id)).toEqual([]);
  });
});
describe("Cliente API", () => {
  it("adjunta CSRF y las credenciales de mismo origen", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
    vi.stubGlobal("fetch", fetch);
    setCsrf("test-csrf");
    await api("/test", "POST", { value: 1 });
    expect(fetch).toHaveBeenCalledWith(
      "/api/test",
      expect.objectContaining({
        credentials: "same-origin",
        headers: expect.objectContaining({
          "X-CSRF-Token": "test-csrf",
          "X-Requested-With": "CitaLab",
        }),
      }),
    );
  });
  it("notifica caducidad sin mostrar mensajes brutos del servidor", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: { unsafe: "secret" } }),
      }),
    );
    const listener = vi.fn();
    window.addEventListener("session-expired", listener);
    await expect(api("/bootstrap")).rejects.toBeInstanceOf(ApiError);
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener("session-expired", listener);
  });
});
