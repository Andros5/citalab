import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ArchitectureGuide } from "./ArchitectureGuide";

// Los diagramas se sirven como ficheros estáticos: se simula fetch del manifiesto.
const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);
const manifest = (diagrams: unknown) => ({ ok: true, json: async () => ({ diagrams }) });
const catalog = Object.fromEntries(
  ["sistema", "agentes", "reserva"].map((id) => [
    id,
    { title: id, artifact_sha256: "a".repeat(64) },
  ]),
);
afterEach(() => {
  cleanup();
  fetchMock.mockReset();
});

it("carga un único visor aislado y cambia la vista mediante teclado", async () => {
  fetchMock.mockResolvedValue(manifest(catalog));
  render(<ArchitectureGuide />);
  expect(screen.getByRole("status")).toHaveTextContent("Comprobando diagramas");
  const frame = await screen.findByTitle("Vista previa del diagrama: sistema");
  expect(frame).toHaveAttribute("sandbox", "allow-scripts allow-downloads");
  expect(frame).toHaveAttribute("src", "/architecture/sistema.html?embed=1");
  fireEvent.load(frame);
  expect(
    screen.queryByText("Cargando diagrama local…"),
  ).not.toBeInTheDocument();
  fireEvent.keyDown(screen.getByRole("tab", { name: "01 · Sistema" }), {
    key: "ArrowRight",
  });
  expect(
    screen.getByTitle("Vista previa del diagrama: agentes"),
  ).toBeInTheDocument();
  expect(
    screen.queryByTitle("Vista previa del diagrama: sistema"),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Descargar HTML" })).toHaveAttribute(
    "download",
    "citalab-agentes.html",
  );
});

it("conserva la explicación cuando falla la API y permite reintentar", async () => {
  fetchMock
    .mockRejectedValueOnce(new Error("Servidor no disponible"))
    .mockResolvedValueOnce(manifest(catalog));
  render(<ArchitectureGuide />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Servidor no disponible",
  );
  expect(
    screen.getByText("Lectura guiada y alternativa textual"),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));
  await screen.findByTitle("Vista previa del diagrama: sistema");
});

it("rechaza metadatos incompletos en vez de montar un iframe inválido", async () => {
  fetchMock.mockResolvedValue(manifest({ sistema: { title: "incompleto" } }));
  render(<ArchitectureGuide />);
  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent("formato esperado"),
  );
  expect(document.querySelector("iframe")).toBeNull();
});

it("ofrece descarga y apertura separada sin acceso al documento padre", async () => {
  fetchMock.mockResolvedValue(manifest(catalog));
  render(<ArchitectureGuide />);
  await screen.findByTitle("Vista previa del diagrama: sistema");
  const link = screen.getByRole("link", { name: "Abrir visor amplio" });
  expect(link).toHaveAttribute("rel", "noopener noreferrer");
  expect(link).toHaveAttribute("target", "_blank");
  expect(
    screen.getByText("Lectura guiada y alternativa textual"),
  ).toBeInTheDocument();
});
