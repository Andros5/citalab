import { act, fireEvent, render, screen } from "@testing-library/react";
import { StrictMode, useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "../../app/ErrorBoundary";
import { Field, Modal, Tabs } from "../../components";

describe("Accesibilidad y recuperación compartidas", () => {
  it("asocia ayuda y error a campos con identificadores únicos", () => {
    render(
      <>
        <Field
          label="Nombre"
          hint="Ejemplo sintético"
          error="Campo obligatorio"
        >
          <input />
        </Field>
        <Field label="Motivo">
          <input />
        </Field>
      </>,
    );
    const input = screen.getByRole("textbox", { name: "Nombre" });
    expect(input).toHaveAccessibleDescription(
      "Ejemplo sintético Campo obligatorio",
    );
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input.id).not.toBe(
      screen.getByRole("textbox", { name: "Motivo" }).id,
    );
  });
  it("mantiene el bloqueo con dos diálogos y restaura estilos en StrictMode", () => {
    document.documentElement.style.overflow = "scroll";
    const view = render(
      <StrictMode>
        <Modal title="Uno" close={() => {}}>
          Uno
        </Modal>
        <Modal title="Dos" close={() => {}}>
          Dos
        </Modal>
      </StrictMode>,
    );
    view.rerender(
      <StrictMode>
        <Modal title="Uno" close={() => {}}>
          Uno
        </Modal>
      </StrictMode>,
    );
    expect(document.documentElement.style.overflow).toBe("hidden");
    view.unmount();
    expect(document.documentElement.style.overflow).toBe("scroll");
    document.documentElement.style.removeProperty("overflow");
  });
  it("libera el scroll si el navegador no puede abrir el diálogo", () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    const show = vi
      .spyOn(HTMLDialogElement.prototype, "showModal")
      .mockImplementation(() => {
        throw new Error("failure");
      });
    render(
      <ErrorBoundary>
        <Modal title="Prueba" close={() => {}}>
          Contenido
        </Modal>
      </ErrorBoundary>,
    );
    expect(
      screen.getByRole("heading", { name: "Esta vista no está disponible" }),
    ).toBeInTheDocument();
    expect(document.body.style.overflow).not.toBe("hidden");
    expect(
      screen.getByRole("button", { name: "Recargar aplicación" }),
    ).toBeInTheDocument();
    show.mockRestore();
    consoleError.mockRestore();
  });
  it("cierra el ciclo de Tab y Mayús+Tab sin enfocar controles ocultos o desactivados", () => {
    const geometry = vi
      .spyOn(HTMLElement.prototype, "getClientRects")
      .mockReturnValue([{}] as unknown as DOMRectList);
    try {
      render(
        <Modal title="Ciclo de foco" close={() => {}}>
          <button disabled>No disponible</button>
          <button hidden>Oculto</button>
          <button>Última acción</button>
        </Modal>,
      );
      const first = screen.getByRole("button", { name: "Cerrar diálogo" });
      const last = screen.getByRole("button", { name: "Última acción" });
      act(() => first.focus());
      fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
      expect(last).toHaveFocus();
      fireEvent.keyDown(last, { key: "Tab" });
      expect(first).toHaveFocus();
    } finally {
      geometry.mockRestore();
    }
  });
  it("las flechas y Home activan y enfocan la pestaña correspondiente", () => {
    function Example() {
      const [selected, setSelected] = useState("a");
      return (
        <Tabs
          label="Secciones"
          value={selected}
          onChange={setSelected}
          items={[
            { value: "a", label: "Agenda" },
            { value: "b", label: "Perfiles" },
          ]}
        >
          {selected === "a" ? "Citas" : "Preferencias"}
        </Tabs>
      );
    }
    render(<Example />);
    act(() => screen.getByRole("tab", { name: "Agenda" }).focus());
    fireEvent.keyDown(document.activeElement!, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Perfiles" })).toHaveFocus();
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Preferencias");
    fireEvent.keyDown(document.activeElement!, { key: "Home" });
    expect(screen.getByRole("tab", { name: "Agenda" })).toHaveFocus();
  });
});
