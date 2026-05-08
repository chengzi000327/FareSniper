const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("fs_token");
}

async function ensureSession(): Promise<string> {
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
  const r = await fetch(`${BASE}${path}`, {
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${token}`,
      ...(init?.headers || {}),
    },
    ...init,
  });
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
  get: () => http<{ memories: unknown[]; query_history: unknown[] }>("/api/memory"),
  patch: (body: { field: string; value: unknown }) =>
    http("/api/memory", { method: "PATCH", body: JSON.stringify(body) }),
  del: (field: string) =>
    http(`/api/memory/${encodeURIComponent(field)}`, { method: "DELETE" }),
};

export const recApi = {
  list: () => http<{ personalized: boolean; cards: unknown[] }>("/api/recommendations"),
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
