export interface PriceItem {
  id: string
  name: string
  price: number | null
  currency: string
  lowest?: boolean | null
  data_freshness?: 'fresh' | 'stale' | 'unknown'
}

export interface DealCard {
  id: string
  flight_no: string
  platform: string
  origin_city: string
  origin_code: string
  destination_city: string
  destination_code: string
  depart_date: string
  airline: string
  depart_time: string
  arrive_time: string
  stops: number
  base_price?: number | null
  tax: number | null
  baggage_allowance?: string | null
  total_price: number | null
  currency: string
  prices: PriceItem[]
  data_freshness: 'fresh' | 'stale' | 'unknown'
}

export interface SearchResponse {
  session_id: string
  deals?: DealCard[]
  recommendation?: {
    text: string
    action?: string
    confidence?: string
  }
  fallback?: {
    ui: 'modal'
    fields: string[]
    reason: string
  } | null
}

export interface RecommendationCard {
  id?: string
  title?: string
  reason?: string
  tags?: string[]
  query_hint?: string
  preview_deal?: DealCard | null
}

export interface AlertItem {
  id: string
  origin: string
  destination: string
  depart_date: string
  target_price: number
  current_price?: number | null
  latest_price?: number | null
  latest_provider?: string | null
  latest_quote_at?: string | null
  currency: string
  notification_status: string
  status: string
}

export interface MemoryResponse {
  memories: Array<{
    field: string
    value: unknown
    source?: string
  }>
  query_history: Array<{
    id?: string | number
    query?: string
    query_text?: string
    created_at?: string
  }>
}
