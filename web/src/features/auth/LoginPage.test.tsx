import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { LocaleProvider } from "../../i18n";
import { LoginPage } from "./LoginPage";

it("mantiene el acceso sin el aviso sintético redundante", () => {
  render(
    <LocaleProvider language="es" setLanguage={vi.fn()}>
      <LoginPage onLogin={vi.fn()} />
    </LocaleProvider>,
  );
  expect(screen.getByRole("button", { name: "Entrar al laboratorio" })).toBeVisible();
  expect(screen.getByLabelText("Código de acceso")).toHaveAttribute("required");
  expect(screen.queryByText(/No introduzcas DNI/)).not.toBeInTheDocument();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});
