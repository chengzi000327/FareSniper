import Taro from '@tarojs/taro'

import {
  MOCK_ALERTS,
  MOCK_MEMORY,
  MOCK_RECOMMENDATIONS,
  MOCK_SEARCH,
} from './mock'
import type {
  AlertItem,
  MemoryResponse,
  RecommendationCard,
  SearchResponse,
} from '../types/api'

const API_BASE = (process.env.TARO_APP_API_BASE_URL || '').replace(/\/$/, '')
const USE_MOCK = process.env.TARO_APP_USE_MOCK === 'true' || !API_BASE
const TOKEN_KEY = 'fs_wechat_token'
const USER_KEY = 'fs_wechat_user_id'

interface WechatSessionResponse {
  access_token: string
  user_id: string
}

function token() {
  return Taro.getStorageSync<string>(TOKEN_KEY) || ''
}

export async function ensureWechatSession(force = false): Promise<string> {
  if (USE_MOCK) {
    Taro.setStorageSync(USER_KEY, 'wechat_mock_user')
    return 'wechat_mock_token'
  }
  if (!force && token()) return token()

  const login = await Taro.login()
  if (!login.code) throw new Error('微信登录未返回 code')
  const response = await Taro.request<WechatSessionResponse>({
    url: `${API_BASE}/api/auth/wechat/session`,
    method: 'POST',
    header: {
      'content-type': 'application/json',
    },
    data: {
      code: login.code,
    },
  })
  if (response.statusCode !== 200) {
    throw new Error(`微信登录失败：${response.statusCode}`)
  }
  Taro.setStorageSync(TOKEN_KEY, response.data.access_token)
  Taro.setStorageSync(USER_KEY, response.data.user_id)
  return response.data.access_token
}

async function request<T>(
  path: string,
  options: {
    method?: 'GET' | 'POST' | 'PATCH'
    data?: unknown
  } = {},
): Promise<T> {
  const send = async (accessToken: string) =>
    Taro.request<T>({
      url: `${API_BASE}${path}`,
      method: options.method || 'GET',
      data: options.data,
      header: {
        'content-type': 'application/json',
        authorization: `Bearer ${accessToken}`,
      },
    })

  let response = await send(await ensureWechatSession())
  if (response.statusCode === 401) {
    response = await send(await ensureWechatSession(true))
  }
  if (response.statusCode < 200 || response.statusCode >= 300) {
    const detail =
      typeof response.data === 'object' && response.data
        ? JSON.stringify(response.data)
        : String(response.data)
    throw new Error(`${response.statusCode} ${detail}`)
  }
  return response.data
}

export const miniApi = {
  async search(
    message: string,
    sessionId: string | null,
  ): Promise<SearchResponse> {
    if (USE_MOCK) return MOCK_SEARCH
    return request<SearchResponse>('/api/search', {
      method: 'POST',
      data: {
        message,
        session_id: sessionId,
      },
    })
  },

  async recommendations(): Promise<RecommendationCard[]> {
    if (USE_MOCK) return MOCK_RECOMMENDATIONS
    const response = await request<{
      cards: RecommendationCard[]
    }>('/api/recommendations?limit=8&offset=0')
    return response.cards
  },

  async alerts(): Promise<AlertItem[]> {
    if (USE_MOCK) return MOCK_ALERTS
    const response = await request<{ alerts: AlertItem[] }>('/api/alerts')
    return response.alerts
  },

  async alert(alertId: string): Promise<AlertItem> {
    if (USE_MOCK) {
      return (
        MOCK_ALERTS.find((item) => item.id === alertId) || MOCK_ALERTS[0]
      )
    }
    return request<AlertItem>(`/api/alerts/${encodeURIComponent(alertId)}`)
  },

  async createAlert(input: {
    origin: string
    destination: string
    depart_date: string
    target_price: number
    current_price: number | null
    currency: string
    notify_wechat: boolean
  }): Promise<{ id: string; wechat_notification: string }> {
    if (USE_MOCK) {
      return {
        id: `alert_${Date.now()}`,
        wechat_notification: input.notify_wechat
          ? 'subscribed'
          : 'not_requested',
      }
    }
    return request('/api/alerts', {
      method: 'POST',
      data: input,
    })
  },

  async updateAlert(
    alertId: string,
    status: 'active' | 'paused' | 'cancelled',
  ) {
    if (USE_MOCK) return { id: alertId, status }
    return request(`/api/alerts/${encodeURIComponent(alertId)}`, {
      method: 'PATCH',
      data: { status },
    })
  },

  async subscribeAlert(alertId: string) {
    if (USE_MOCK) {
      return { id: alertId, wechat_notification: 'subscribed' }
    }
    return request<{
      id: string
      wechat_notification: string
    }>(`/api/alerts/${encodeURIComponent(alertId)}/wechat-subscription`, {
      method: 'POST',
    })
  },

  async memory(): Promise<MemoryResponse> {
    if (USE_MOCK) return MOCK_MEMORY
    return request<MemoryResponse>('/api/memory')
  },

  userId(): string {
    return Taro.getStorageSync<string>(USER_KEY) || ''
  },

  isMock(): boolean {
    return USE_MOCK
  },
}
