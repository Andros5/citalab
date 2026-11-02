import { renderHook } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { Turn } from "../../api";
import { LocaleProvider } from "../../i18n";
import { useResponseLanguage } from "./useResponseLanguage";

type Props = { id: string; turn: Turn | undefined; busy: boolean };

function setup(initialProps: Props) {
  const setLanguage = vi.fn();
  const hook = renderHook(({ id, turn, busy }: Props) => useResponseLanguage(id, turn, busy), {
    initialProps,
    wrapper: ({ children }) => <LocaleProvider language="es" setLanguage={setLanguage}>{children}</LocaleProvider>,
  });
  return { setLanguage, rerender: hook.rerender };
}

it("follows each response completed while the conversation is open, once", () => {
  const { setLanguage, rerender } = setup({ id: "c1", turn: undefined, busy: false });
  const en = { id: "en-turn", response_language: "en" } as Turn;
  rerender({ id: "c1", turn: undefined, busy: true });
  rerender({ id: "c1", turn: en, busy: false });
  expect(setLanguage).toHaveBeenLastCalledWith("en");
  rerender({ id: "c1", turn: { ...en }, busy: false });
  expect(setLanguage).toHaveBeenCalledTimes(1);
  rerender({ id: "c1", turn: { id: "legacy" } as Turn, busy: false });
  rerender({ id: "c1", turn: { id: "unsupported", response_language: "fr" } as Turn, busy: false });
  expect(setLanguage).toHaveBeenCalledTimes(1);
  rerender({ id: "c1", turn: { id: "es-turn", response_language: "es" } as Turn, busy: false });
  expect(setLanguage).toHaveBeenLastCalledWith("es");
});

it("keeps the chosen interface language when opening an existing conversation", () => {
  const old = { id: "old", response_language: "es" } as Turn;
  const { setLanguage, rerender } = setup({ id: "c1", turn: old, busy: false });
  rerender({ id: "c2", turn: { id: "other", response_language: "es" } as Turn, busy: false });
  expect(setLanguage).not.toHaveBeenCalled();
});
