import type {
  DealCardDto,
  MemoryItemDto,
  MemoryResponseDto,
  PatchMemoryRequestDto,
  RecommendationsResponseDto,
  SearchRequestDto,
  SearchResponseDto,
} from '@/types/api'
import type {
  ExploreSearchResult,
  FlightDeal,
  MemoryWorkspaceData,
  PreferenceMemory,
} from '@/types'
import { hotDeals, mockDeals, mockMemories } from '@/lib/mocks'

const API_MODE = process.env.NEXT_PUBLIC_API_MODE ?? 'remote'
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000'
export const DEFAULT_USER_ID = process.env.NEXT_PUBLIC_DEFAULT_USER_ID ?? 'demo-user'

type FetchOptions = {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
}

function buildUrl(path: string): string {
  return `${API_URL}${path}`
}

async function requestJson<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const response = await fetch(buildUrl(path), {
    method: options.method ?? 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
    cache: 'no-store',
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed: ${response.status}`)
  }

  return response.json() as Promise<T>
}

function getGradient(id: string): { from: string; to: string } {
  const palette = [
    { from: '#0EA5E9', to: '#22D3EE' },
    { from: '#8B5CF6', to: '#C4B5FD' },
    { from: '#10B981', to: '#6EE7B7' },
    { from: '#F59E0B', to: '#FCD34D' },
    { from: '#3B82F6', to: '#93C5FD' },
  ]
  const seed = Array.from(id).reduce((total, char) => total + char.charCodeAt(0), 0)
  return palette[seed % palette.length]
}

function getMemoryAccent(field: string): { accentColor: string; rotation: string } {
  const palette: Record<string, { accentColor: string; rotation: string }> = {
    price_anchor: { accentColor: '#22C55E', rotation: '-1deg' },
    preferred_origins: { accentColor: '#1B2B5E', rotation: '2deg' },
    preferred_destinations: { accentColor: '#F59E0B', rotation: '-2deg' },
    travel_window: { accentColor: '#8B5CF6', rotation: '1.5deg' },
    cabin_preference: { accentColor: '#0EA5E9', rotation: '-1.5deg' },
  }

  return palette[field] ?? { accentColor: '#64748B', rotation: '0deg' }
}

function formatUpdatedAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  const diffHours = Math.floor((Date.now() - date.getTime()) / (1000 * 60 * 60))
  if (diffHours < 1) return '刚刚'
  if (diffHours < 24) return `${diffHours}小时前`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 30) return `${diffDays}天前`
  return `${date.getMonth() + 1}/${date.getDate()}`
}

export function mapDealDtoToUi(deal: DealCardDto): FlightDeal {
  const gradient = getGradient(deal.id)

  return {
    id: deal.id,
    platform: deal.platform,
    origin: deal.origin_city,
    originCode: deal.origin_code,
    destination: deal.destination_city,
    destinationCode: deal.destination_code,
    price: deal.price,
    originalPrice: deal.original_price ?? Math.max(deal.price, deal.price),
    departDate: deal.depart_date,
    airline: deal.airline,
    departTime: deal.depart_time,
    arriveTime: deal.arrive_time,
    signals: deal.signals,
    confidence: deal.confidence,
    systemId: deal.system_id,
    gradientFrom: gradient.from,
    gradientTo: gradient.to,
    verdict: deal.verdict,
  }
}

export function mapMemoryDtoToUi(memory: MemoryItemDto): PreferenceMemory {
  const accent = getMemoryAccent(memory.field)

  return {
    id: memory.id,
    field: memory.field,
    label: memory.label,
    value: memory.value_display,
    source: memory.source,
    updatedAt: formatUpdatedAt(memory.updated_at),
    accentColor: accent.accentColor,
    rotation: accent.rotation,
  }
}

export async function searchFlights(
  message: string,
  userId: string = DEFAULT_USER_ID,
): Promise<ExploreSearchResult> {
  if (API_MODE === 'mock') {
    return {
      userId,
      queryText: message,
      normalizedText: message,
      recommendationText: '建议现在买',
      recommendationConfidence: 'high',
      resultCount: mockDeals.length,
      deals: mockDeals,
      matchedPreferences: ['price_anchor'],
    }
  }

  const payload: SearchRequestDto = {
    user_id: userId,
    message,
  }

  const result = await requestJson<SearchResponseDto>('/api/search', {
    method: 'POST',
    body: payload,
  })

  return {
    userId: result.user_id,
    queryText: result.query.raw_text,
    normalizedText: result.query.normalized_text,
    recommendationText: result.recommendation.text,
    recommendationConfidence: result.recommendation.confidence,
    resultCount: result.meta.result_count ?? result.deals.length,
    deals: result.deals.map(mapDealDtoToUi),
    matchedPreferences: result.analysis.matched_preferences,
  }
}

export async function getMemories(userId: string = DEFAULT_USER_ID): Promise<PreferenceMemory[]> {
  const workspace = await getMemoryWorkspace(userId)
  return workspace.memories
}

export async function getMemoryWorkspace(
  userId: string = DEFAULT_USER_ID,
): Promise<MemoryWorkspaceData> {
  if (API_MODE === 'mock') {
    return {
      memories: mockMemories,
      queryHistory: [
        {
          query: {
            destination_city: '三亚',
            date_start: '2026-05-01',
          },
          createdAt: '1天前',
        },
        {
          query: {
            destination_city: '昆明',
            date_start: '2026-05-08',
          },
          createdAt: '3天前',
        },
      ],
      clickHistory: [],
    }
  }

  const result = await requestJson<MemoryResponseDto>(`/api/memory?user_id=${encodeURIComponent(userId)}`)
  return {
    memories: result.memories.map(mapMemoryDtoToUi),
    queryHistory: result.query_history.map((item) => ({
      query: item.query,
      createdAt: formatUpdatedAt(item.created_at),
    })),
    clickHistory: result.click_history.map((item) => ({
      flightInfo: item.flight_info,
      createdAt: formatUpdatedAt(item.created_at),
    })),
  }
}

export async function updateMemory(
  payload: PatchMemoryRequestDto,
): Promise<PreferenceMemory[]> {
  if (API_MODE === 'mock') {
    return mockMemories
  }

  const result = await requestJson<MemoryResponseDto>('/api/memory', {
    method: 'PATCH',
    body: payload,
  })
  return result.memories.map(mapMemoryDtoToUi)
}

export async function deleteMemory(
  field: string,
  userId: string = DEFAULT_USER_ID,
): Promise<PreferenceMemory[]> {
  if (API_MODE === 'mock') {
    return mockMemories.filter((memory) => memory.field !== field)
  }

  const result = await requestJson<MemoryResponseDto>(
    `/api/memory/${encodeURIComponent(field)}?user_id=${encodeURIComponent(userId)}`,
    { method: 'DELETE' },
  )
  return result.memories.map(mapMemoryDtoToUi)
}

export async function getRecommendationDeals(userId: string = DEFAULT_USER_ID): Promise<FlightDeal[]> {
  if (API_MODE === 'mock') {
    return hotDeals
  }

  const result = await requestJson<RecommendationsResponseDto>(
    `/api/recommendations?user_id=${encodeURIComponent(userId)}`,
  )

  return result.cards
    .map((card) => card.preview_deal)
    .filter((deal): deal is DealCardDto => deal !== null)
    .map(mapDealDtoToUi)
}
