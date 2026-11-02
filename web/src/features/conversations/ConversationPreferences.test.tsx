import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Conversation } from "../../api";
import { ConversationPreferences } from "./ConversationPreferences";

const apiMock = vi.hoisted(() => vi.fn());
vi.mock("../../api", async (load) => ({
  ...(await load<typeof import("../../api")>()),
  api: apiMock,
}));

const conversation = {
  id: "conversation-preferencias",
  turn_count: 2,
  archived: false,
  read_only: false,
  preferences: {
    schema_version: 1,
    values: {},
    effective: {
      "preferred-language": "es",
      "preferred-detail-level": "concise",
      "preferred-treatment": "formal",
    },
    sources: {
      "preferred-language": "profile",
      "preferred-detail-level": "profile",
      "preferred-treatment": "profile",
    },
    revision: 0,
    profile_opt_out: false,
  },
} as unknown as Conversation;

afterEach(() => {
  apiMock.mockReset();
});

it("aplica un control efímero versionado y explica que no persiste el perfil", async () => {
  const onSaved = vi.fn().mockResolvedValue(undefined);
  apiMock.mockResolvedValue({
    ...conversation,
    preference_update: {
      scope: "conversation",
      persisted_to_profile: false,
      proposal_invalidated: false,
    },
  });
  render(
    <ConversationPreferences
      conversation={conversation}
      busy={false}
      onSaved={onSaved}
    />,
  );

  fireEvent.click(screen.getByText("Preferencias"));
  // Language here is the assistant's response preference, separate from the
  // global interface locale. The current supported preference set is es/en.
  fireEvent.change(screen.getByLabelText("Idioma"), {
    target: { value: "en" },
  });
  fireEvent.change(screen.getByLabelText("Nivel de detalle"), {
    target: { value: "step-by-step" },
  });
  fireEvent.click(screen.getByRole("button", { name: /aplicar/i }));

  await waitFor(() =>
    expect(apiMock).toHaveBeenCalledWith(
      "/conversations/conversation-preferencias/preferences",
      "PUT",
      {
        expected_turn: 2,
        scope: "conversation",
        enabled: true,
        language: "en",
        detail: "step-by-step",
      },
    ),
  );
  expect(await screen.findByText(/perfil persistente no ha cambiado/i)).toBeVisible();
  expect(onSaved).toHaveBeenCalledOnce();
});

it("bloquea controles en una conversación de solo lectura", () => {
  render(
    <ConversationPreferences
      conversation={{ ...conversation, read_only: true } as Conversation}
      busy={false}
      onSaved={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByText("Preferencias"));
  expect(screen.getByRole("button", { name: /aplicar/i })).toBeDisabled();
  expect(
    screen.getByLabelText("Usar preferencias autorizadas en esta conversación"),
  ).toBeDisabled();
});

it("explica los valores generales cuando aún no existe una fuente conversacional", () => {
  render(
    <ConversationPreferences
      conversation={
        {
          ...conversation,
          preferences: { ...conversation.preferences, sources: {} },
        } as Conversation
      }
      busy={false}
      onSaved={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByText("Preferencias"));

  expect(
    screen.getByText(
      "Origen: idioma: valor general · detalle: valor general · tratamiento: valor general · franja: valor general · canal de recordatorio: valor general",
    ),
  ).toBeVisible();
});

it("crea una propuesta separada antes de guardar una preferencia en el perfil", async () => {
  apiMock.mockImplementation(() => Promise.resolve(conversation));
  render(
    <ConversationPreferences
      conversation={conversation}
      busy={false}
      canPersistProfile
      onSaved={vi.fn().mockResolvedValue(undefined)}
    />,
  );

  fireEvent.click(screen.getByText("Preferencias"));
  fireEvent.change(screen.getByLabelText("Alcance"), {
    target: { value: "profile" },
  });
  fireEvent.change(screen.getByLabelText("Idioma"), {
    target: { value: "en" },
  });
  fireEvent.click(screen.getByRole("button", { name: /crear propuesta persistente/i }));

  await waitFor(() =>
    expect(apiMock).toHaveBeenCalledWith(
      "/conversations/conversation-preferencias/preferences",
      "PUT",
      expect.objectContaining({
        expected_turn: 2,
        scope: "profile",
        enabled: true,
        language: "en",
        request_id: expect.any(String),
      }),
    ),
  );
  expect(
    await screen.findByText(/debes confirmar la propuesta/i),
  ).toBeVisible();
});
