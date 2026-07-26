import Taro from '@tarojs/taro'

import {
  MOCK_ALERTS,
  MOCK_MEMORY,
  MOCK_RECOMMENDATIONS,
  MOCK_SEARCH,
} from './mock'
import type {
  AlertItem,
  MemoryItem,
  MemoryResponse,
  RecommendationPage,
  RecommendationCard,
  SearchResponse,
} from '../types/api'

const API_BASE = (process.env.TARO_APP_API_BASE_URL || '').replace(/\/$/, '')
const USE_MOCK = process.env.TARO_APP_USE_MOCK === 'true'
const TOKEN_KEY = 'fs_wechat_token'
const USER_KEY = 'fs_wechat_user_id'
const AUTH_MODE_KEY = 'fs_auth_mode'

interface WechatSessionResponse {
  access_token: string
  user_id: string
}

interface VisitorSessionResponse extends WechatSessionResponse {
  session_id: string
}

interface WechatAuthStatus {
  configured: boolean
}

function token() {
  return Taro.getStorageSync<string>(TOKEN_KEY) || ''
}

async function exchangeWechatSession(): Promise<string> {
  const login = await Taro.login()
  if (!login.code) throw new Error('微信登录未返回 code')
  const response = await Taro.request<
    WechatSessionResponse | { detail?: string }
  >({
    url: `${API_BASE}/api/auth/wechat/session`,
    method: 'POST',
    header: {
      'content-type': 'application/json',
      ...(token() ? { authorization: `Bearer ${token()}` } : {}),
    },
    data: {
      code: login.code,
    },
  })
  if (response.statusCode === 200 && 'access_token' in response.data) {
    Taro.setStorageSync(TOKEN_KEY, response.data.access_token)
    Taro.setStorageSync(USER_KEY, response.data.user_id)
    Taro.setStorageSync(AUTH_MODE_KEY, 'wechat')
    return response.data.access_token
  }
  throw new Error(
    response.statusCode === 503
      ? '微信登录服务尚未配置'
      : `微信登录失败：${response.statusCode}`,
  )
}

export async function connectWechatSession(): Promise<string> {
  if (USE_MOCK) {
    Taro.setStorageSync(USER_KEY, 'wechat_mock_user')
    Taro.setStorageSync(AUTH_MODE_KEY, 'mock')
    return 'wechat_mock_token'
  }
  if (!API_BASE) throw new Error('未配置 TARO_APP_API_BASE_URL')
  return exchangeWechatSession()
}

export async function ensureWechatSession(force = false): Promise<string> {
  if (USE_MOCK) return connectWechatSession()
  if (!API_BASE) {
    throw new Error('未配置 TARO_APP_API_BASE_URL')
  }
  if (!force && token()) return token()

  try {
    return await exchangeWechatSession()
  } catch {
    // Browsing and search remain usable before the operator configures AppSecret.
  }
  const visitor = await Taro.request<VisitorSessionResponse>({
    url: `${API_BASE}/api/session`,
    method: 'POST',
    header: {
      'content-type': 'application/json',
    },
    data: {},
  })
  if (visitor.statusCode !== 200) {
    throw new Error(`访客会话创建失败：${visitor.statusCode}`)
  }
  Taro.setStorageSync(TOKEN_KEY, visitor.data.access_token)
  Taro.setStorageSync(USER_KEY, visitor.data.user_id)
  Taro.setStorageSync(AUTH_MODE_KEY, 'visitor')
  return visitor.data.access_token
}

async function request<T>(
  path: string,
  options: {
    method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
    data?: unknown
  } = {},
): Promise<T> {
  if (!API_BASE) {
    throw new Error(
      '未配置 TARO_APP_API_BASE_URL。正式构建不会自动回退到演示票价。',
    )
  }
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
  async wechatAuthStatus(): Promise<WechatAuthStatus> {
    if (USE_MOCK) return { configured: true }
    if (!API_BASE) return { configured: false }
    const response = await Taro.request<WechatAuthStatus>({
      url: `${API_BASE}/api/auth/wechat/status`,
      method: 'GET',
    })
    return response.statusCode === 200
      ? response.data
      : { configured: false }
  },

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

  async recommendationPage(
    limit = 8,
    offset = 0,
  ): Promise<RecommendationPage> {
    if (USE_MOCK) {
      const cards = MOCK_RECOMMENDATIONS.slice(offset, offset + limit)
      return {
        cards,
        has_more: offset + cards.length < MOCK_RECOMMENDATIONS.length,
        next_offset: offset + cards.length,
      }
    }
    return request<RecommendationPage>(
      `/api/recommendations?limit=${limit}&offset=${offset}`,
    )
  },

  async recommendations(): Promise<RecommendationCard[]> {
    return (await this.recommendationPage()).cards
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
      const id = `alert_${Date.now()}`
      MOCK_ALERTS.unshift({
        id,
        origin: input.origin,
        destination: input.destination,
        depart_date: input.depart_date,
        target_price: input.target_price,
        current_price: input.current_price,
        latest_price: input.current_price,
        latest_provider: '演示报价',
        latest_quote_at: new Date().toISOString(),
        currency: input.currency,
        notification_status: input.notify_wechat
          ? 'subscribed'
          : 'not_requested',
        status: 'active',
      })
      return {
        id,
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
    if (USE_MOCK) {
      const alert = MOCK_ALERTS.find((item) => item.id === alertId)
      if (alert) alert.status = status
      return { id: alertId, status }
    }
    return request(`/api/alerts/${encodeURIComponent(alertId)}`, {
      method: 'PATCH',
      data: { status },
    })
  },

  async subscribeAlert(alertId: string) {
    if (USE_MOCK) {
      const alert = MOCK_ALERTS.find((item) => item.id === alertId)
      if (alert) alert.notification_status = 'subscribed'
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

  async patchMemory(field: string, value: unknown) {
    if (USE_MOCK) {
      const existing = MOCK_MEMORY.memories.find((item) => item.field === field)
      const next: MemoryItem = {
        field,
        value,
        label: existing?.label || field,
        value_display:
          typeof value === 'number'
            ? `¥${value}`
            : Array.isArray(value)
              ? value.join('、')
              : typeof value === 'object'
                ? String((value as Record<string, unknown>)?.name || '已保存')
                : String(value),
        source: 'manual',
      }
      MOCK_MEMORY.memories = [
        next,
        ...MOCK_MEMORY.memories.filter((item) => item.field !== field),
      ]
      return { ok: true }
    }
    return request<{ ok: boolean }>('/api/memory', {
      method: 'PATCH',
      data: { field, value },
    })
  },

  async deleteMemory(field: string) {
    if (USE_MOCK) {
      MOCK_MEMORY.memories = MOCK_MEMORY.memories.filter(
        (item) => item.field !== field,
      )
      return
    }
    await request<void>(`/api/memory/${encodeURIComponent(field)}`, {
      method: 'DELETE',
    })
  },

  userId(): string {
    return Taro.getStorageSync<string>(USER_KEY) || ''
  },

  authMode(): 'wechat' | 'visitor' | 'mock' | '' {
    return Taro.getStorageSync(AUTH_MODE_KEY) || ''
  },

  isMock(): boolean {
    return USE_MOCK
  },
}
