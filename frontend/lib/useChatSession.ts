import { useState, useCallback } from "react";
import { searchApi, FallbackDirective } from "./api";

export type { FallbackDirective };

export function useChatSession() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [fallback, setFallback] = useState<FallbackDirective | null>(null);

  const send = useCallback(
    async (text: string) => {
      const rsp = await searchApi.search({ message: text, session_id: sessionId });
      setSessionId(rsp.session_id);
      setFallback(rsp.fallback ?? null);
      setMessages((prev) => [
        ...prev,
        { role: "user", content: text },
        { role: "assistant", content: rsp.recommendation?.text ?? "" },
      ]);
      return rsp;
    },
    [sessionId],
  );

  const dismissFallback = useCallback(() => setFallback(null), []);

  return { sessionId, messages, fallback, send, dismissFallback };
}
