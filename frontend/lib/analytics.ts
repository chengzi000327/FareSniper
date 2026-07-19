export const EventName = {
  SearchSubmitted: "search_submitted",
  IntentParsed: "intent_parsed",
  ResultViewed: "result_viewed",
  TicketClicked: "ticket_clicked",
  PurchaseJumped: "purchase_jumped",
  MemoryEdited: "memory_edited",
  MemoryCleared: "memory_cleared",
  FallbackTriggered: "fallback_triggered",
} as const;

type EventNameValue = typeof EventName[keyof typeof EventName];

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export async function track(event: EventNameValue, payload: Record<string, unknown>) {
  const token =
    typeof window === "undefined" ? null : window.localStorage.getItem("fs_token");
  await fetch(`${BASE}/api/track`, {
    method: "POST",
    keepalive: true,
    headers: {
      "content-type": "application/json",
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ event, payload }),
  });
}
