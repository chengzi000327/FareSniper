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
  await fetch(`${BASE}/api/track`, {
    method: "POST",
    keepalive: true,
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ event, payload }),
  });
}
