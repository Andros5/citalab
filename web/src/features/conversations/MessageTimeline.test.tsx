import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import type { Conversation, Turn } from "../../api";
import { MessageTimeline } from "./MessageTimeline";

it("identifica una recuperación sin negar una operación administrativa ya completada", () => {
  const conversation = {subject_name: "Ana", provider: "google", turn_count: 1,
    turns: [{id: "t", number: 1, request: "Confirmo", response: "Cita reservada.",
      status: "COMPLETED", response_metadata: {recovery: true}}]} as unknown as Conversation;
  render(<MessageTimeline conversation={conversation} busy={false} job={null} calls={[]} />);
  expect(screen.getByText("Cita reservada.")).toBeInTheDocument();
  expect(screen.getByText("El asistente utilizó una respuesta de recuperación programada.")).toBeInTheDocument();
  expect(screen.queryByText(/no se ha ejecutado/)).not.toBeInTheDocument();
});

it("shows the outgoing message before progress and reconciles without duplicates", () => {
  const conversation = { subject_name: "Ana", provider: "offline", turn_count: 0, turns: [] } as unknown as Conversation;
  const outgoing = { request_id: "request", message: "Mensaje inmediato", expected_turn: 0, status: "sending" as const };
  const { rerender } = render(<MessageTimeline conversation={conversation} outgoing={outgoing} busy job={null} calls={[]} />);
  const message = screen.getByText("Mensaje inmediato");
  const progress = screen.getByRole("status");
  expect(message.compareDocumentPosition(progress) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  rerender(<MessageTimeline conversation={conversation} outgoing={{ ...outgoing, status: "uncertain" }} busy job={null} calls={[]} />);
  expect(screen.getByText("Envío pendiente de verificar.")).toBeInTheDocument();
  expect(screen.queryByText(/Procesando/)).not.toBeInTheDocument();
  rerender(<MessageTimeline conversation={conversation} outgoing={{ ...outgoing, status: "failed" }} busy={false} job={null} calls={[]} />);
  expect(screen.getByText("No se pudo completar el envío.")).toBeInTheDocument();
  const final = { ...conversation, turn_count: 1, turns: [{ id: "t", number: 1, request: outgoing.message, response: "Respuesta" } as Turn] };
  rerender(<MessageTimeline conversation={final} outgoing={outgoing} busy={false} job={null} calls={[]} />);
  expect(screen.getAllByText("Mensaje inmediato")).toHaveLength(1);
  expect(screen.getByText("Respuesta")).toBeInTheDocument();
});

it("muestra el aviso inicial versionado separado de los turnos", () => {
  const conversation = {
    subject_name: "Ana",
    provider: "offline",
    turn_count: 0,
    turns: [],
    welcome: {
      kind: "initial_notice",
      version: 1,
      text: "Soy un asistente de IA.\n\nPuedo gestionar citas sintéticas.",
    },
  } as unknown as Conversation;
  render(<MessageTimeline conversation={conversation} busy={false} job={null} calls={[]} />);
  expect(screen.getByText("AVISO INICIAL · SIMULACIÓN SIN LLM")).toBeInTheDocument();
  expect(screen.getByText("Soy un asistente de IA.")).toBeInTheDocument();
  expect(screen.getByText("Puedo gestionar citas sintéticas.")).toBeInTheDocument();
  expect(screen.queryByText(/TURNO 1/)).not.toBeInTheDocument();
});

it.each([100, 500, 1000])(
  "presenta 50 turnos iniciales de un corpus de %i y carga los anteriores bajo demanda",
  (count) => {
    const conversation = {
      subject_name: "Ana",
      provider: "offline",
      turn_count: count,
      turns: Array.from({ length: count }, (_, index) => ({
        id: String(index),
        number: index + 1,
        request: `Petición sintética ${index + 1}`,
        response: `Respuesta sintética ${index + 1}`,
      })),
    } as unknown as Conversation;
    render(
      <MessageTimeline
        conversation={conversation}
        busy={false}
        job={null}
        calls={[]}
      />,
    );
    expect(screen.getByText(`Petición sintética ${count}`)).toBeInTheDocument();
    expect(screen.queryByText("Petición sintética 1")).not.toBeInTheDocument();
    expect(screen.getAllByText(/^Petición sintética \d+$/)).toHaveLength(50);
    fireEvent.click(
      screen.getByRole("button", { name: /Cargar 50 turnos anteriores/ }),
    );
    expect(screen.getAllByText(/^Petición sintética \d+$/)).toHaveLength(100);
  },
);
