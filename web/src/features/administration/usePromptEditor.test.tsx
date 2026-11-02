import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import type { Bootstrap } from "../../api";
import { AppContext } from "../../context";
import { SessionDraftProvider } from "../../shared/hooks/sessionDrafts";
import { usePromptEditor } from "./usePromptEditor";

const bootstrap = {
  user: { username: "investigador", role: "admin" },
} as Bootstrap;
const collection = {
  active: ["context", "profile"].map((role) => ({
    role,
    version: 1,
    instruction: `Vigente ${role}`,
    base_prompt: "Base",
    base_hash: "synthetic",
  })),
  history: [],
};
function wrapper({ children }: { children: ReactNode }) {
  return (
    <AppContext.Provider
      value={{ bootstrap, refresh: vi.fn(), notify: vi.fn() }}
    >
      <SessionDraftProvider>{children}</SessionDraftProvider>
    </AppContext.Provider>
  );
}
afterEach(() => vi.unstubAllGlobals());

it("una lectura tardía no cambia el rol elegido ni sustituye su borrador", async () => {
  let complete!: (value: unknown) => void;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise((resolve) => {
          complete = resolve;
        }),
    ),
  );
  const { result } = renderHook(usePromptEditor, { wrapper });
  act(() => {
    result.current.setRole("profile");
  });
  act(() => {
    result.current.setInstruction("Borrador de perfil");
  });
  await act(async () =>
    complete({ ok: true, status: 200, json: async () => collection }),
  );
  expect(result.current.role).toBe("profile");
  expect(result.current.instruction).toBe("Borrador de perfil");
  act(() => result.current.setRole("context"));
  expect(result.current.instruction).toBe("Vigente context");
  act(() => result.current.setRole("profile"));
  expect(result.current.instruction).toBe("Borrador de perfil");
});

it("un conflicto conserva texto, rol y motivo; permite actualizar la versión vigente", async () => {
  const writes: Record<string, unknown>[] = [];
  const fetch = vi.fn(async (_url, init) => {
    if (init.method === "PUT") {
      writes.push(JSON.parse(init.body));
      return {
        ok: false,
        status: 409,
        json: async () => ({ detail: "Versión desactualizada" }),
      };
    }
    return { ok: true, status: 200, json: async () => collection };
  });
  vi.stubGlobal("fetch", fetch);
  const { result } = renderHook(usePromptEditor, { wrapper });
  await waitFor(() => expect(result.current.resource.loading).toBe(false));
  act(() => result.current.setRole("profile"));
  act(() => {
    result.current.setInstruction("Texto propio");
    result.current.setReason("Hipótesis sintética");
  });
  await act(async () => result.current.publish());
  expect(writes).toEqual([
    {
      role: "profile",
      instruction: "Texto propio",
      reason: "Hipótesis sintética",
      expected_version: 1,
    },
  ]);
  expect(result.current.error).toContain("desactualizada");
  act(() => result.current.resource.retry());
  await waitFor(() => expect(result.current.resource.loading).toBe(false));
  expect(result.current.instruction).toBe("Texto propio");
  expect(result.current.reason).toBe("Hipótesis sintética");
});

it("un contrato de prompts mal formado termina en error recuperable", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ active: {}, history: [] }),
    }),
  );
  const { result } = renderHook(usePromptEditor, { wrapper });
  await waitFor(() => expect(result.current.resource.loading).toBe(false));
  expect(result.current.resource.error).toContain("formato");
});
