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

async function ensureSession(force = false): Promise<string> {
  if (force) clearSession();
  let token = getToken();
  if (token) return token;
  const r = await fetch(`${BASE}/api/session`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: "{}",
  });
  if (!r.ok) throw new Error(`session bootstrap failed: ${r.status}`);
  const body = await r.json();
  window.localStorage.setItem("fs_token", body.access_token);
  window.localStorage.setItem("fs_user_id", body.user_id);
  return body.access_token;
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await ensureSession();
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
    const freshToken = await ensureSession(true);
    r = await request(freshToken);
  }
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

// ── Types ────────────────────────────────────────────────────────────────────

export interface PriceItem {
  name: string;
  price: number;
  lowest?: boolean;
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
  price: number;
  tax: number;
  baggage_fee: number;
  has_baggage: boolean;
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

// ── API clients ──────────────────────────────────────────────────────────────

export const searchApi = {
  search: (body: { session_id: string | null; message: string }) =>
    http<ChatSearchResponse>("/api/search", {
      method: "POST",
      body: JSON.stringify(body),
    }),
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
