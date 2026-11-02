import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { Conversation } from "../../api";
import { OperationPanel } from "./OperationPanel";

const base: Conversation = {
  id: "conversation-operation",
  owner: "patient-ana",
  subject_id: "patient-ana",
  subject_name: "Ana Sintética",
  title: "Gestión",
  status: "NEEDS_CONFIRMATION",
  architecture: "M5",
  provider: "offline",
  diagnostic: false,
  created_at: "2026-09-21T08:00:00Z",
  updated_at: "2026-09-21T08:00:00Z",
  turn_count: 1,
  turns: [],
  can_confirm: true,
  active_job: null,
  archived: false,
};

describe("Proyección de operaciones conversacionales", () => {
  it("nombra el efecto y el sujeto antes de confirmar una cancelación", () => {
    const confirm = vi.fn();
    render(
      <MemoryRouter>
        <OperationPanel
          conversation={{
            ...base,
            operation_proposal: {
              proposal_id: "cancel:apt-0001:test",
              revision: 1,
              operation: "cancel",
              subject_id: "patient-ana",
              appointment_id: "apt-0001",
              expires_at: "2026-09-21T09:00:00Z",
              appointment: {
                id: "apt-0001",
                status: "booked",
                service_code: "nursing",
                service_display: "Enfermería",
                start: "2026-09-25T10:00:00+02:00",
                end: "2026-09-25T10:20:00+02:00",
              },
            },
          }}
          busy={false}
          onConfirm={confirm}
          onDiscard={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("Cancelación pendiente")).toBeInTheDocument();
    expect(screen.getByText("Ana Sintética")).toBeInTheDocument();
    expect(screen.getByText("apt-0001")).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Confirmar cancelación" }),
    );
    expect(confirm).toHaveBeenCalledOnce();
  });

  it("presenta una consulta como resultados y no como acción confirmable", () => {
    render(
      <MemoryRouter>
        <OperationPanel
          conversation={{
            ...base,
            status: "COMPLETED",
            can_confirm: false,
            appointment_results: [
              {
                id: "apt-0002",
                status: "booked",
                service_code: "general-practice",
                service_display: "Medicina de familia",
                start: "2026-09-26T09:00:00+02:00",
                end: "2026-09-26T09:20:00+02:00",
              },
            ],
          }}
          busy={false}
          onConfirm={vi.fn()}
          onDiscard={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("Citas encontradas")).toBeInTheDocument();
    expect(screen.getByText("Medicina de familia")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Confirmar/ })).toBeNull();
  });

  it("distingue la cita original del nuevo horario tras un cambio", () => {
    render(
      <MemoryRouter>
        <OperationPanel
          conversation={{
            ...base,
            status: "COMPLETED",
            can_confirm: false,
            operation_proposal: {
              proposal_id: "reschedule:apt-0003:test",
              revision: 1,
              operation: "reschedule",
              subject_id: "patient-ana",
              appointment_id: "apt-0003",
              expires_at: "2026-09-24T20:00:00Z",
              appointment: {
                id: "apt-0003",
                status: "booked",
                service_code: "general-practice",
                service_display: "Medicina de familia",
                start: "2026-09-25T09:00:00+02:00",
                end: "2026-09-25T09:20:00+02:00",
              },
              target_offer: {
                start: "2026-09-28T09:00:00+02:00",
                end: "2026-09-28T09:20:00+02:00",
                service_display: "Medicina de familia",
                modality_display: "Presencial",
                location_display: "Centro de Salud Demo",
              },
            },
            operation_receipt: {
              status: "completed",
              operation: "reschedule",
              idempotency_key: "test-reschedule",
            },
          }}
          busy={false}
          onConfirm={vi.fn()}
          onDiscard={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(
      screen.getByText("Datos de la cita antes de esta gestión:"),
    ).toBeInTheDocument();
    expect(screen.getByText("Nuevo horario confirmado")).toBeInTheDocument();
    expect(screen.queryByText("Nuevo horario solicitado")).toBeNull();
  });
});
