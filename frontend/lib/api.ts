const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export interface PriceItem {
  name: string
  price: number
  lowest?: boolean
}

export interface DealCardDto {
  id: string
  system_id: string
  platform: string
  origin_city: string
  origin_code: string
  destination_city: string
  destination_code: string
  depart_date: string
  airline: string
  depart_time: string
  arrive_time: string
  price: number
  tax: number
  baggage_fee: number
  has_baggage: boolean
  recommend_score: string
  prices: PriceItem[]
  original_price?: number
  discount_rate?: number
  cabin?: string
  signals: string[]
  confidence: 'high' | 'medium' | 'low'
  verdict: string
  booking_url?: string
}

export interface SearchQueryDto {
  raw_text: string
  normalized_text: string
  origin_city: string
  origin_code: string
  destination_city: string
  destination_code: string
  date_start: string
  date_end: string
  budget?: number
}

export interface SearchAnalysisDto {
  min_price?: number
  max_price?: number
  avg_price?: number
  avg_90d?: number
  lower_than_avg?: number
  price_spread_pct?: number
  match_score: number
  within_budget: boolean
  matched_preferences: string[]
}

export interface SearchRecommendationDto {
  action: 'buy_now' | 'watch' | 'skip'
  text: string
  confidence: 'high' | 'medium' | 'low'
  signals: string[]
}

export interface ApiMeta {
  generated_at: string
  source?: string
  request_id?: string
  result_count?: number
  fallback_mode?: boolean
}

export interface SearchResponseDto {
  user_id: string
  query: SearchQueryDto
  deals: DealCardDto[]
  analysis: SearchAnalysisDto
  recommendation: SearchRecommendationDto
  meta: ApiMeta
}

export interface MemoryItemDto {
  id: string
  field: string
  label: string
  value: string | number | string[]
  value_display: string
  source: 'manual' | 'auto'
  updated_at: string
}

export interface QueryHistoryItemDto {
  query: Record<string, unknown>
  created_at: string
}

export interface ClickHistoryItemDto {
  flight_info: Record<string, unknown>
  created_at: string
}

export interface MemoryResponseDto {
  user_id: string
  memories: MemoryItemDto[]
  query_history: QueryHistoryItemDto[]
  click_history: ClickHistoryItemDto[]
  meta: ApiMeta
}

export interface RecommendationCardDto {
  id: string
  title: string
  reason: string
  query_hint: string
  tags: string[]
  preview_deal?: DealCardDto
}

export interface RecommendationsResponseDto {
  user_id: string
  cards: RecommendationCardDto[]
  meta: ApiMeta
}

export const api = {
  search: (message: string, userId = 'demo-user'): Promise<SearchResponseDto> =>
    fetch(`${BASE}/api/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, message }),
    }).then((r) => r.json()),

  getMemory: (userId = 'demo-user'): Promise<MemoryResponseDto> =>
    fetch(`${BASE}/api/memory?user_id=${userId}`).then((r) => r.json()),

  patchMemory: (
    userId: string,
    field: string,
    value: string | number | string[],
    source: 'manual' | 'auto' = 'manual',
  ): Promise<MemoryResponseDto> =>
    fetch(`${BASE}/api/memory`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, field, value, source }),
    }).then((r) => r.json()),

  deleteMemoryField: (userId: string, field: string): Promise<MemoryResponseDto> =>
    fetch(`${BASE}/api/memory/${field}?user_id=${userId}`, {
      method: 'DELETE',
    }).then((r) => r.json()),

  getRecommendations: (userId = 'demo-user'): Promise<RecommendationsResponseDto> =>
    fetch(`${BASE}/api/recommendations?user_id=${userId}`).then((r) => r.json()),
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
  recommendation?: { text: string };
  fallback?: FallbackDirective | null;
}

export const searchApi = {
  search: (req: ChatSearchRequest): Promise<ChatSearchResponse> =>
    fetch(`${BASE}/api/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    }).then((r) => r.json()),
};
