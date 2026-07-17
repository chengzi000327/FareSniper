const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("fs_token");
}

function clearSession() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem("fs_token");
  window.localStorage.removeItem("fs_user_id");
}

async function ensureSession(force = false, signal?: AbortSignal): Promise<string> {
  if (force) clearSession();
  let token = getToken();
  if (token) return token;
  const r = await fetch(`${BASE}/api/session`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: "{}",
    signal,
  });
  if (!r.ok) throw new Error(`session bootstrap failed: ${r.status}`);
  const body = await r.json();
  window.localStorage.setItem("fs_token", body.access_token);
  window.localStorage.setItem("fs_user_id", body.user_id);
  return body.access_token;
}

async function requestWithSession(path: string, init?: RequestInit): Promise<Response> {
  const token = await ensureSession(false, init?.signal ?? undefined);
  const request = (authToken: string) =>
    fetch(`${BASE}${path}`, {
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${authToken}`,
        ...(init?.headers || {}),
      },
      ...init,
    });

  let r = await request(token);
  if (r.status === 401) {
    const freshToken = await ensureSession(true, init?.signal ?? undefined);
    r = await request(freshToken);
  }
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r;
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await requestWithSession(path, init);
  return r.json();
}

// ── Types ────────────────────────────────────────────────────────────────────

export type ProviderDisplayStatus =
  | "loading"
  | "queued"
  | "success"
  | "empty"
  | "stale"
  | "timeout"
  | "disabled"
  | "error"
  | "view_live_price";

export interface PriceItem {
  name: string;
  price: number | null;
  lowest?: boolean;
  status: ProviderDisplayStatus;
  url?: string | null;
  data_provider?: string | null;
}

export interface DealCardDto {
  id: string;
  system_id: string;
  platform: string;
  origin_city: string;
  origin_code: string;
  destination_city: string;
  destination_code: string;
  depart_date: string;
  airline: string;
  depart_time: string;
  arrive_time: string;
  price: number | null;
  tax: number | null;
  baggage_fee: number | null;
  has_baggage: boolean | null;
  total_price: number | null;
  currency: string;
  recommend_score: string;
  prices: PriceItem[];
  original_price?: number;
  discount_rate?: number;
  cabin?: string;
  signals: string[];
  booking_url?: string | null;
  data_freshness?: string;
}

export interface ChatSearchRequest {
  message: string;
  session_id?: string | null;
}

export interface FallbackDirective {
  ui: "modal";
  fields: string[];
  reason: string;
}

export interface ChatSearchResponse {
  session_id: string;
  deals?: DealCardDto[];
  recommendation?: { text: string; action?: string; confidence?: string };
  fallback?: FallbackDirective | null;
}

export interface SearchStreamEvent {
  type: "started" | "provider_status" | "results" | "validation_error" | "complete";
  search_id: string;
  sequence: number;
  payload: {
    response?: ChatSearchResponse;
    deals?: DealCardDto[];
    provider?: string;
    status?: ProviderDisplayStatus;
    message?: string;
    [key: string]: unknown;
  };
}

function parseSearchStreamEvent(line: string): SearchStreamEvent {
  const parsed: unknown = JSON.parse(line);
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error("invalid stream event");
  }
  return parsed as SearchStreamEvent;
}

async function readNdjson(
  response: Response,
  onEvent: (event: SearchStreamEvent) => void
): Promise<ChatSearchResponse | null> {
  if (!response.body) throw new Error("stream body missing");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResponse: ChatSearchResponse | null = null;
  let completed = false;
  let failure: unknown;

  const emit = (line: string) => {
    if (!line.trim()) return;
    const event = parseSearchStreamEvent(line);
    onEvent(event);
    if (event.type === "complete" && event.payload.response) {
      finalResponse = event.payload.response;
    }
  };

  const consumeLines = () => {
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    lines.forEach(emit);
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (value) buffer += decoder.decode(value, { stream: true });
      consumeLines();
      if (done) {
        buffer += decoder.decode();
        if (buffer.trim()) emit(buffer);
        completed = true;
        return finalResponse;
      }
    }
  } catch (error) {
    failure = error;
    throw error;
  } finally {
    if (!completed) {
      try {
        await reader.cancel(failure);
      } catch {
        // Preserve the original parse, callback, or abort error.
      }
    }
    reader.releaseLock();
  }
}

// ── API clients ──────────────────────────────────────────────────────────────

export const searchApi = {
  search: (body: { session_id: string | null; message: string }) =>
    http<ChatSearchResponse>("/api/search", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  stream: async (
    body: { session_id: string | null; message: string },
    onEvent: (event: SearchStreamEvent) => void,
    signal?: AbortSignal
  ) => {
    const response = await requestWithSession("/api/search/stream", {
      method: "POST",
      body: JSON.stringify(body),
      signal,
    });
    return readNdjson(response, onEvent);
  },
};

export const memoryApi = {
  get: () => http<{ memories: MemoryItemDto[]; query_history: QueryHistoryItemDto[] }>("/api/memory"),
  patch: (body: { field: string; value: unknown }) =>
    http("/api/memory", { method: "PATCH", body: JSON.stringify(body) }),
  del: (field: string) =>
    http(`/api/memory/${encodeURIComponent(field)}`, { method: "DELETE" }),
};

export interface RecCardDto {
  id?: string;
  title?: string;
  reason?: string;
  tags?: string[];
  discount_pct?: number | null;
  preview_deal?: DealCardDto;
  query_hint?: string;
  [key: string]: unknown;
}

export interface RecommendationsResponse {
  personalized: boolean;
  cards: RecCardDto[];
  has_more: boolean;
  next_offset: number;
}

export const recApi = {
  list: (params?: { limit?: number; offset?: number }) => {
    const limit = params?.limit ?? 6;
    const offset = params?.offset ?? 0;
    return http<RecommendationsResponse>(
      `/api/recommendations?limit=${limit}&offset=${offset}`
    );
  },
};

export const alertsApi = {
  create: (body: {
    origin: string;
    destination: string;
    depart_date: string;
    target_price: number;
  }) => http("/api/alerts", { method: "POST", body: JSON.stringify(body) }),
  list: () => http<{ alerts: unknown[] }>("/api/alerts"),
};

export const authApi = {
  requestOtp: (phone: string) =>
    fetch(`${BASE}/api/auth/otp`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ phone }),
    }),
  verify: async (phone: string, code: string) => {
    const token = getToken();
    const r = await fetch(`${BASE}/api/auth/verify`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...(token ? { authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ phone, code }),
    });
    if (!r.ok) throw new Error(`verify failed: ${r.status}`);
    const body = await r.json();
    window.localStorage.setItem("fs_token", body.access_token);
    window.localStorage.setItem("fs_user_id", body.user_id);
    return body as { access_token: string; user_id: string };
  },
};

export const priceHistoryApi = {
  get: (origin: string, destination: string, days = 30) =>
    http<{ route: string; points: { at: string; price: number }[] }>(
      `/api/price_history?origin=${origin}&destination=${destination}&days=${days}`
    ),
};

export const pushApi = {
  saveSubscription: (subscription: PushSubscriptionJSON) =>
    http("/api/push/subscriptions", {
      method: "POST",
      body: JSON.stringify({ subscription }),
    }),
};

export interface MemoryItemDto {
  field: string;
  label: string;
  value_display: string;
  source: "manual" | "auto" | string;
  [key: string]: unknown;
}

export interface QueryHistoryItemDto {
  id: string;
  query: unknown;
  created_at: string;
  [key: string]: unknown;
}

/** 向后兼容的聚合 api 对象，供旧组件使用 */
export const api = {
  search: (message: string) =>
    searchApi.search({ session_id: null, message }),
  getRecommendations: () => recApi.list(),
  getMemory: () => memoryApi.get(),
};
