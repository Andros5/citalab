import { useState } from "react";
import { api } from "../../api";
import { useApp } from "../../context";
import {
  useDraftStatus,
  useSessionDraft,
} from "../../shared/hooks/sessionDrafts";
import { useResource } from "../../shared/hooks/useResource";
export type Prompt = {
  role: string;
  version: number;
  instruction: string;
  base_prompt: string;
  base_hash: string;
  at?: string;
  reason?: string;
};
type PromptCollection = { active: Prompt[]; history: Prompt[] };
function isPromptCollection(value: unknown): value is PromptCollection {
  if (!value || typeof value !== "object") return false;
  const data = value as PromptCollection;
  return (
    Array.isArray(data.active) &&
    Array.isArray(data.history) &&
    [...data.active, ...data.history].every(
      (p) =>
        typeof p?.role === "string" &&
        typeof p.instruction === "string" &&
        typeof p.version === "number",
    )
  );
}
export function usePromptEditor() {
  const { bootstrap, notify } = useApp();
  const admin = bootstrap.user.role === "admin";
  const resource = useResource<PromptCollection>(
    "/admin/prompts",
    isPromptCollection,
  );
  const prompts = resource.data?.active || [];
  const history = resource.data?.history || [];
  const [role, setRole] = useSessionDraft("admin-role", "context");
  const [drafts, setDrafts] = useSessionDraft<Record<string, string>>(
    "admin-prompts",
    {},
  );
  const [reasons, setReasons] = useSessionDraft<Record<string, string>>(
    "admin-prompt-reasons",
    {},
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const prompt = prompts.find((item) => item.role === role);
  const instruction = drafts[role] ?? prompt?.instruction ?? "";
  const reason = reasons[role] ?? "";
  const setInstruction = (value: string) =>
    setDrafts((current) => ({ ...current, [role]: value }));
  const setReason = (value: string) =>
    setReasons((current) => ({ ...current, [role]: value }));
  const dirty =
    admin &&
    Object.entries(drafts).some(
      ([key, value]) =>
        value !==
        (prompts.find((item) => item.role === key)?.instruction ?? ""),
    );
  useDraftStatus("prompts", dirty);
  const publish = async () => {
    if (!prompt || busy) return;
    setBusy(true);
    setError("");
    try {
      await api("/admin/prompts", "PUT", {
        role,
        instruction,
        expected_version: prompt.version,
        reason,
      });
      setDrafts((current) => {
        const next = { ...current };
        delete next[role];
        return next;
      });
      setReason("");
      resource.retry();
      notify(
        "Instrucción publicada. Crea una conversación nueva para probarla.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const discard = () => {
    if (window.confirm("¿Descartar los borradores de instrucciones?")) {
      setDrafts({});
      setReasons({});
    }
  };
  return {
    admin,
    resource,
    history,
    role,
    setRole,
    prompt,
    instruction,
    setInstruction,
    reason,
    setReason,
    busy,
    error,
    dirty,
    publish,
    discard,
  };
}
