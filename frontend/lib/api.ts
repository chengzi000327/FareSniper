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
  if (r.status === 204) return undefined as T;
  return r.json();
}

// ── Types ────────────────────────────────────────────────────────────────────

export type ProviderStatus =
  | "loading"
  | "queued"
  | "success"
  | "empty"
  | "stale"
  | "timeout"
  | "disabled"
  | "error";

export type PriceStatus = "priced" | "view_live_price" | "stale";
export type DataFreshness = "fresh" | "stale" | "unknown";

export interface PriceItem {
  id: string;
  name: string;
  price: number | null;
  currency: string;
  lowest?: boolean | null;
  price_status: PriceStatus | null;
  provider_status: ProviderStatus;
  url?: string | null;
  data_provider: string;
  data_freshness: DataFreshness;
  expires_at?: string | null;
}

export interface DealCardDto {
  id: string;
  system_id: string;
  flight_no: string;
  platform: string;
  origin_city: string;
  origin_code: string;
  origin_airport_code?: string | null;
  destination_city: string;
  destination_code: string;
  destination_airport_code?: string | null;
  depart_date: string;
  airline: string;
  depart_time: string;
  arrive_time: string;
  duration_minutes: number | null;
  stops: number;
  price: number | null;
  lowest_price: number | null;
  base_price?: number | null;
  tax: number | null;
  tax_source?: "provider" | "regulatory_estimate" | null;
  baggage_fee: number | null;
  baggage_allowance?: string | null;
  has_baggage: boolean | null;
  total_price: number | null;
  currency: string;
  recommend_score: string | null;
  winning_price_id: string | null;
  prices: PriceItem[];
  original_price?: number | null;
  discount_rate?: number | null;
  cabin?: string | null;
  signals: string[];
  booking_url?: string | null;
  h5_fallback_url?: string | null;
  data_freshness: DataFreshness;
  inventory_expires_at?: string | null;
  confidence?: "high" | "medium" | "low";
  verdict?: string;
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
    status?: ProviderStatus;
    message?: string;
    error?: string;
    [key: string]: unknown;
  };
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasOwn(record: Record<string, unknown>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(record, key);
}

function isProviderStatus(value: unknown): value is ProviderStatus {
  return (
    value === "loading" ||
    value === "queued" ||
    value === "success" ||
    value === "empty" ||
    value === "stale" ||
    value === "timeout" ||
    value === "disabled" ||
    value === "error"
  );
}

function isPriceStatus(value: unknown): value is PriceStatus {
  return (
    value === "priced" ||
    value === "view_live_price" ||
    value === "stale"
  );
}

function isCurrency(value: unknown): value is string {
  return typeof value === "string" && /^[A-Z]{3}$/.test(value);
}

function isDataFreshness(value: unknown): value is DataFreshness {
  return value === "fresh" || value === "stale" || value === "unknown";
}

function isCompleteHttpsUrl(value: unknown): value is string {
  if (typeof value !== "string") return false;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && Boolean(url.hostname);
  } catch {
    return false;
  }
}

function isInventoryExpiry(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isNullableFiniteNumber(value: unknown): value is number | null {
  return value === null || isFiniteNumber(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function hasOptionalField(
  record: Record<string, unknown>,
  key: string,
  isValid: (value: unknown) => boolean
): boolean {
  return !hasOwn(record, key) || isValid(record[key]);
}

function isPriceItem(value: unknown): value is PriceItem {
  if (
    !isPlainRecord(value) ||
    typeof value.id !== "string" ||
    typeof value.name !== "string" ||
    !isNullableFiniteNumber(value.price) ||
    !isCurrency(value.currency) ||
    (value.price_status !== null && !isPriceStatus(value.price_status)) ||
    !isProviderStatus(value.provider_status) ||
    typeof value.data_provider !== "string" ||
    !isDataFreshness(value.data_freshness)
  ) {
    return false;
  }
  return (
    hasOptionalField(value, "lowest", (item) => item === null || typeof item === "boolean") &&
    hasOptionalField(value, "url", (item) => item === null || isCompleteHttpsUrl(item)) &&
    hasOptionalField(value, "expires_at", (item) => item === null || isInventoryExpiry(item))
  );
}

function isDealCardDto(value: unknown): value is DealCardDto {
  if (!isPlainRecord(value)) return false;

  const requiredStrings = [
    "id",
    "system_id",
    "flight_no",
    "platform",
    "origin_city",
    "origin_code",
    "destination_city",
    "destination_code",
    "depart_date",
    "airline",
    "depart_time",
    "arrive_time",
    "currency",
  ];
  if (requiredStrings.some((key) => typeof value[key] !== "string")) return false;
  if (
    !hasOptionalField(value, "origin_airport_code", (item) => item === null || typeof item === "string") ||
    !hasOptionalField(value, "destination_airport_code", (item) => item === null || typeof item === "string") ||
    !isCurrency(value.currency) ||
    (value.recommend_score !== null && typeof value.recommend_score !== "string") ||
    (value.winning_price_id !== null && typeof value.winning_price_id !== "string") ||
    !isDataFreshness(value.data_freshness) ||
    !isNullableFiniteNumber(value.price) ||
    !isNullableFiniteNumber(value.lowest_price) ||
    !isNullableFiniteNumber(value.duration_minutes) ||
    !Number.isInteger(value.stops) ||
    !isNullableFiniteNumber(value.tax) ||
    !isNullableFiniteNumber(value.baggage_fee) ||
    !isNullableFiniteNumber(value.total_price) ||
    (value.has_baggage !== null && typeof value.has_baggage !== "boolean") ||
    !Array.isArray(value.prices) ||
    !value.prices.every(isPriceItem) ||
    !isStringArray(value.signals)
  ) {
    return false;
  }
  const optionalFieldsAreValid = (
    hasOptionalField(value, "base_price", isNullableFiniteNumber) &&
    hasOptionalField(value, "tax_source", (item) => item === null || item === "provider" || item === "regulatory_estimate") &&
    hasOptionalField(value, "baggage_allowance", (item) => item === null || typeof item === "string") &&
    hasOptionalField(value, "original_price", isNullableFiniteNumber) &&
    hasOptionalField(value, "discount_rate", isNullableFiniteNumber) &&
    hasOptionalField(value, "cabin", (item) => item === null || typeof item === "string") &&
    hasOptionalField(value, "booking_url", (item) => item === null || isCompleteHttpsUrl(item)) &&
    hasOptionalField(value, "h5_fallback_url", (item) => item === null || isCompleteHttpsUrl(item)) &&
    hasOptionalField(value, "inventory_expires_at", (item) => item === null || isInventoryExpiry(item)) &&
    hasOptionalField(value, "confidence", (item) => item === "high" || item === "medium" || item === "low") &&
    hasOptionalField(value, "verdict", (item) => typeof item === "string")
  );
  if (!optionalFieldsAreValid) return false;

  const prices = value.prices as PriceItem[];
  if (value.winning_price_id === null) {
    return (
      prices.every((price) => price.lowest === false) &&
      value.platform === "" &&
      value.price === null &&
      value.lowest_price === null &&
      (!hasOwn(value, "base_price") || value.base_price === null) &&
      value.total_price === null &&
      (!hasOwn(value, "booking_url") || value.booking_url === null) &&
      (!hasOwn(value, "h5_fallback_url") || value.h5_fallback_url === null) &&
      (!hasOwn(value, "inventory_expires_at") || value.inventory_expires_at === null)
    );
  }

  const winners = prices.filter((price) => price.id === value.winning_price_id);
  if (winners.length !== 1) return false;
  const winner = winners[0];
  const nonwinnersHaveExplicitFalse = prices.every(
    (price) => price.id === value.winning_price_id || price.lowest === false
  );
  const freshWinner =
    winner.price_status === "priced" &&
    winner.provider_status === "success" &&
    winner.data_freshness === "fresh";
  const staleCtripWinner =
    winner.data_provider === "ctrip_snapshot" &&
    winner.price_status === "stale" &&
    winner.provider_status === "stale" &&
    winner.data_freshness === "stale" &&
    isCompleteHttpsUrl(winner.url);
  return (
    nonwinnersHaveExplicitFalse &&
    winner.lowest === true &&
    winner.price !== null &&
    (freshWinner || staleCtripWinner) &&
    value.platform === winner.name &&
    value.currency === winner.currency &&
    value.price === winner.price &&
    value.lowest_price === winner.price &&
    value.total_price === winner.price &&
    value.data_freshness === winner.data_freshness &&
    (value.inventory_expires_at ?? null) === (winner.expires_at ?? null) &&
    (value.booking_url ?? null) === (winner.url ?? null) &&
    (!hasOwn(value, "h5_fallback_url") ||
      value.h5_fallback_url === null ||
      value.h5_fallback_url === winner.url)
  );
}

function isRecommendation(value: unknown): value is NonNullable<ChatSearchResponse["recommendation"]> {
  if (!isPlainRecord(value) || typeof value.text !== "string") return false;
  return (
    hasOptionalField(value, "action", (item) => typeof item === "string") &&
    hasOptionalField(value, "confidence", (item) => typeof item === "string")
  );
}

function isFallbackDirective(value: unknown): value is FallbackDirective {
  return (
    isPlainRecord(value) &&
    value.ui === "modal" &&
    isStringArray(value.fields) &&
    typeof value.reason === "string"
  );
}

function isChatSearchResponse(value: unknown): value is ChatSearchResponse {
  if (!isPlainRecord(value) || typeof value.session_id !== "string") return false;
  if (
    hasOwn(value, "deals") &&
    (!Array.isArray(value.deals) || !value.deals.every(isDealCardDto))
  ) {
    return false;
  }
  if (hasOwn(value, "recommendation") && !isRecommendation(value.recommendation)) {
    return false;
  }
  return (
    !hasOwn(value, "fallback") ||
    value.fallback === null ||
    isFallbackDirective(value.fallback)
  );
}

function hasValidKnownPayloadFields(payload: Record<string, unknown>): boolean {
  if (hasOwn(payload, "response") && !isChatSearchResponse(payload.response)) {
    return false;
  }
  if (
    hasOwn(payload, "deals") &&
    (!Array.isArray(payload.deals) || !payload.deals.every(isDealCardDto))
  ) {
    return false;
  }
  if (hasOwn(payload, "provider") && typeof payload.provider !== "string") {
    return false;
  }
  if (hasOwn(payload, "status") && !isProviderStatus(payload.status)) {
    return false;
  }
  if (hasOwn(payload, "message") && typeof payload.message !== "string") {
    return false;
  }
  return !hasOwn(payload, "error") || typeof payload.error === "string";
}

function parseSearchStreamEvent(line: string): SearchStreamEvent {
  const parsed: unknown = JSON.parse(line);
  if (
    !isPlainRecord(parsed) ||
    (parsed.type !== "started" &&
      parsed.type !== "provider_status" &&
      parsed.type !== "results" &&
      parsed.type !== "validation_error" &&
      parsed.type !== "complete") ||
    typeof parsed.search_id !== "string" ||
    !parsed.search_id.trim() ||
    typeof parsed.sequence !== "number" ||
    !Number.isInteger(parsed.sequence) ||
    parsed.sequence <= 0 ||
    !isPlainRecord(parsed.payload) ||
    !hasValidKnownPayloadFields(parsed.payload)
  ) {
    throw new Error("invalid stream event");
  }

  const payload = parsed.payload;
  if (
    (parsed.type === "provider_status" &&
      (typeof payload.provider !== "string" ||
        !isProviderStatus(payload.status))) ||
    (parsed.type === "results" && !Array.isArray(payload.deals)) ||
    (parsed.type === "validation_error" && typeof payload.message !== "string")
  ) {
    throw new Error("invalid stream event");
  }

  if (parsed.type === "complete") {
    const hasResponse = hasOwn(payload, "response");
    const isFailure =
      typeof payload.error === "string" && typeof payload.message === "string";
    if (
      (hasResponse && (hasOwn(payload, "error") || !isChatSearchResponse(payload.response))) ||
      (!hasResponse && !isFailure)
    ) {
      throw new Error("invalid stream event");
    }
  }

  return parsed as unknown as SearchStreamEvent;
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
  let terminalReceived = false;
  let failure: unknown;

  const emit = (line: string) => {
    if (!line.trim()) return;
    const event = parseSearchStreamEvent(line);
    if (terminalReceived) {
      throw new Error("stream event received after complete");
    }
    if (event.type === "complete") {
      terminalReceived = true;
      finalResponse = event.payload.response ?? null;
    }
    onEvent(event);
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
  preview_deal?: DealCardDto | null;
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
  list: () => http<{ alerts: AlertItemDto[] }>("/api/alerts"),
};

export interface AlertItemDto {
  id: string;
  origin: string;
  destination: string;
  depart_date: string;
  target_price: number;
  status: "active" | "triggered" | string;
}

export const authApi = {
  status: async () => {
    const r = await fetch(`${BASE}/api/auth/status`);
    if (!r.ok) throw new Error(`auth status failed: ${r.status}`);
    return r.json() as Promise<{ phone_login_available: boolean }>;
  },
  requestOtp: async (phone: string) => {
    const r = await fetch(`${BASE}/api/auth/otp`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ phone }),
    });
    if (!r.ok) throw new Error(`otp request failed: ${r.status}`);
  },
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
  value: unknown;
  label: string;
  value_display: string;
  source: "manual" | "auto" | string;
  [key: string]: unknown;
}

export interface QueryHistoryItemDto {
  id: string | number;
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
