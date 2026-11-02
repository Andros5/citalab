import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, it } from "vitest";
import { SessionDraftProvider, useSessionDraft } from "./sessionDrafts";

function Editor() {
  const [value, setValue] = useSessionDraft("test", "");
  return (
    <input
      aria-label="Borrador"
      value={value}
      onChange={(e) => setValue(e.target.value)}
    />
  );
}
function Views() {
  const [visible, setVisible] = useState(true);
  return (
    <>
      <button onClick={() => setVisible((v) => !v)}>Otra sección</button>
      {visible && <Editor />}
    </>
  );
}
it("conserva el borrador entre secciones, pero no entre sesiones", () => {
  const view = render(
    <SessionDraftProvider>
      <Views />
    </SessionDraftProvider>,
  );
  fireEvent.change(screen.getByRole("textbox"), {
    target: { value: "Texto no publicado" },
  });
  fireEvent.click(screen.getByRole("button"));
  fireEvent.click(screen.getByRole("button"));
  expect(screen.getByRole("textbox")).toHaveValue("Texto no publicado");
  view.unmount();
  render(
    <SessionDraftProvider>
      <Views />
    </SessionDraftProvider>,
  );
  expect(screen.getByRole("textbox")).toHaveValue("");
});
