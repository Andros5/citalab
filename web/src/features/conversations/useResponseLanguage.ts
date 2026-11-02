import { useEffect, useRef } from "react";
import type { Turn } from "../../api";
import { useLocale } from "../../i18n";

/**
 * Follow the language of each response completed while the conversation is open.
 * Opening an existing conversation keeps the interface language the person chose.
 */
export function useResponseLanguage(
  conversationId: string | undefined,
  turn: Turn | undefined,
  busy: boolean,
) {
  const { setLanguage } = useLocale();
  const seen = useRef<{ conversation: string; turn: string | null } | null>(null);
  useEffect(() => {
    if (!conversationId) return;
    if (seen.current?.conversation !== conversationId) {
      seen.current = { conversation: conversationId, turn: turn?.id ?? null };
      return;
    }
    if (busy || !turn || seen.current.turn === turn.id) return;
    seen.current.turn = turn.id;
    if (turn.response_language === "es" || turn.response_language === "en") {
      setLanguage(turn.response_language);
    }
  }, [conversationId, turn, busy, setLanguage]);
}
