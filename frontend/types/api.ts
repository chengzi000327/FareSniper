export type ApiConfidence = 'high' | 'medium' | 'low'

export type ApiRecommendationAction = 'buy_now' | 'watch' | 'skip'

export type MemoryField =
  | 'price_anchor'
  | 'preferred_origins'
  | 'preferred_destinations'
  | 'travel_window'
  | 'cabin_preference'
  | (string & {})

export type MemoryValue = string | number | string[]

export type ApiMeta = {
  generated_at: string
  source?: string
  request_id?: string
  result_count?: number
  fallback_mode?: boolean
}

export type DealCardDto = {
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
  original_price: number | null
  discount_rate: number | null
  cabin: string | null
  signals: string[]
  confidence: ApiConfidence
  verdict: string
  booking_url: string | null
}

export type SearchRequestDto = {
  user_id: string
  message: string
}

export type SearchQueryDto = {
  raw_text: string
  normalized_text: string
  origin_city: string
  origin_code: string
  destination_city: string
  destination_code: string
  date_start: string
  date_end: string
  budget: number | null
}

export type SearchAnalysisDto = {
  min_price: number | null
  max_price: number | null
  avg_price: number | null
  avg_90d: number | null
  lower_than_avg: number | null
  price_spread_pct: number | null
  match_score: number
  within_budget: boolean
  matched_preferences: MemoryField[]
}

export type SearchRecommendationDto = {
  action: ApiRecommendationAction
  text: string
  confidence: ApiConfidence
  signals: string[]
}

export type SearchResponseDto = {
  user_id: string
  query: SearchQueryDto
  deals: DealCardDto[]
  analysis: SearchAnalysisDto
  recommendation: SearchRecommendationDto
  meta: ApiMeta
}

export type MemoryItemDto = {
  id: string
  field: MemoryField
  label: string
  value: MemoryValue
  value_display: string
  source: 'manual' | 'auto'
  updated_at: string
}

export type QueryHistoryItemDto = {
  query: Record<string, unknown>
  created_at: string
}

export type ClickHistoryItemDto = {
  flight_info: Record<string, unknown>
  created_at: string
}

export type MemoryResponseDto = {
  user_id: string
  memories: MemoryItemDto[]
  query_history: QueryHistoryItemDto[]
  click_history: ClickHistoryItemDto[]
  meta: ApiMeta
}

export type PatchMemoryRequestDto = {
  user_id: string
  field: MemoryField
  value: MemoryValue
  source: 'manual' | 'auto'
}

export type RecommendationCardDto = {
  id: string
  title: string
  reason: string
  query_hint: string
  tags: string[]
  preview_deal: DealCardDto | null
}

export type RecommendationsResponseDto = {
  user_id: string
  cards: RecommendationCardDto[]
  meta: ApiMeta
}

export type ApiErrorResponse = {
  error: {
    code: string
    message: string
    details?: Record<string, unknown>
  }
}
