import React from 'react'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import MobilePage from '@/app/mobile/page'
import { MobileAppPage } from '@/components/mobile-app-page'

const { getMemory, listRecommendations, listAlerts, patchMemory, authStatus, requestOtp, verifyOtp } = vi.hoisted(() => ({
  getMemory: vi.fn(),
  listRecommendations: vi.fn(),
  listAlerts: vi.fn(),
  patchMemory: vi.fn(),
  authStatus: vi.fn(),
  requestOtp: vi.fn(),
  verifyOtp: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  memoryApi: { get: getMemory, patch: patchMemory, del: vi.fn() },
  recApi: { list: listRecommendations },
  alertsApi: { list: listAlerts },
  authApi: { status: authStatus, requestOtp, verify: verifyOtp },
  api: { getMemory },
  searchApi: { stream: vi.fn() },
}))

beforeEach(() => {
  getMemory.mockReset()
  listRecommendations.mockReset()
  listAlerts.mockReset()
  patchMemory.mockReset()
  authStatus.mockReset()
  requestOtp.mockReset()
  verifyOtp.mockReset()
  localStorage.setItem('fs_user_id', 'u_test')
  localStorage.setItem('fs_phone', '+8613800000000')
  patchMemory.mockResolvedValue({})
  authStatus.mockResolvedValue({ phone_login_available: false })
  requestOtp.mockResolvedValue(undefined)
  verifyOtp.mockResolvedValue({ access_token: 'token', user_id: 'u_phone' })
  getMemory.mockResolvedValue({
    memories: [
      { field: 'companion_profile', value: { kind: 'cat', name: '云朵' }, label: '旅伴档案', value_display: '', source: 'manual' },
      { field: 'travel_ideas', value: [{ id: '1', text: '秋天想去青岛', created_at: '2026-07-22T10:00:00+08:00' }], label: '出行想法', value_display: '', source: 'manual' },
      { field: 'budget', value: 800, label: '心理价位', value_display: '¥800', source: 'manual' },
      { field: 'constraints', value: ['avoid_stopover'], label: '出行习惯', value_display: '不要中转', source: 'auto' },
    ],
    query_history: [{ id: '1', query: { text: '上海去三亚' }, created_at: '2026-07-22T10:00:00+08:00' }],
  })
  listRecommendations.mockResolvedValue({
    personalized: true,
    cards: [{ id: 'route-1', title: '上海 → 三亚', query_hint: '下周上海去三亚', reason: '进入对话获取实时价格' }],
    has_more: false,
    next_offset: 1,
  })
  listAlerts.mockResolvedValue({
    alerts: [{ id: 'a1', origin: 'BJS', destination: 'SHA', depart_date: '2026-08-01', target_price: 500, status: 'active' }],
  })
})

test('the mobile route uses the dedicated app interface', () => {
  expect(MobilePage()).toEqual(<MobileAppPage />)
})

test('shows a four-item mobile navigation and real memory summaries', async () => {
  render(<MobileAppPage />)

  await waitFor(() => expect(getMemory).toHaveBeenCalledTimes(1))
  expect(screen.getByRole('navigation', { name: '手机端主导航' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '探索' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '对话' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '记忆' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '我的' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '首页' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '对话' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByText('你的机票发现与出行陪伴 Agent')).toBeInTheDocument()
  expect(screen.getByText('先说一个想法就好')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /查一趟具体航班/ })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /还没想好，先逛探索/ })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /继续上次的查询/ })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '历史对话' })).not.toBeInTheDocument()
  expect(screen.queryByText('¥399')).not.toBeInTheDocument()
  expect(screen.queryByText('¥568')).not.toBeInTheDocument()
  await waitFor(() => expect(listRecommendations).toHaveBeenCalledTimes(2))
  fireEvent.click(screen.getByRole('button', { name: /查一趟具体航班/ }))
  await waitFor(() => expect(screen.getByRole('textbox')).toHaveValue('下周上海去三亚'))
  fireEvent.click(screen.getByRole('button', { name: /还没想好，先逛探索/ }))
  expect(await screen.findByText('从真实推荐里发现下一程')).toBeInTheDocument()
  expect(screen.getByText('1 个关注')).toBeInTheDocument()
  expect(screen.getByText('为你发现')).toBeInTheDocument()
  expect(screen.getByText('上海 → 三亚')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '盲盒抽' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '查看推荐 上海 → 三亚' })).toHaveClass('break-inside-avoid')
  expect(screen.queryByText('看看它记住了什么')).not.toBeInTheDocument()
  expect(screen.getByLabelText('继续加载推荐')).toBeInTheDocument()
  expect(screen.getByText('这次先逛到这里')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: '盲盒抽' }))
  expect(screen.getByRole('region', { name: '盲盒结果' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '去查票' })).toBeInTheDocument()
})

test('loads another recommendation page when the mobile waterfall reaches its end', async () => {
  let intersectionCallback: IntersectionObserverCallback | null = null
  class MockIntersectionObserver {
    constructor(callback: IntersectionObserverCallback) {
      intersectionCallback = callback
    }
    observe() {}
    disconnect() {}
    unobserve() {}
    takeRecords() { return [] }
    root = null
    rootMargin = ''
    thresholds = []
  }
  vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)

  listRecommendations
    .mockReset()
    .mockResolvedValueOnce({
      personalized: true,
      cards: [{ id: 'route-1', title: '上海 → 三亚', query_hint: '下周上海去三亚', reason: '第一批推荐' }],
      has_more: true,
      next_offset: 6,
    })
    .mockResolvedValueOnce({
      personalized: true,
      cards: [],
      has_more: false,
      next_offset: 0,
    })
    .mockResolvedValueOnce({
      personalized: true,
      cards: [{ id: 'route-2', title: '上海 → 厦门', query_hint: '下周上海去厦门', reason: '继续下滑发现' }],
      has_more: false,
      next_offset: 7,
    })

  render(<MobileAppPage />)
  await waitFor(() => expect(listRecommendations).toHaveBeenCalledTimes(2))
  fireEvent.click(screen.getByRole('button', { name: '探索' }))
  await waitFor(() => expect(intersectionCallback).not.toBeNull())

  act(() => {
    intersectionCallback?.([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver)
  })

  await waitFor(() => expect(listRecommendations).toHaveBeenLastCalledWith({ limit: 6, offset: 6 }))
  expect(await screen.findByRole('button', { name: '查看推荐 上海 → 厦门' })).toBeInTheDocument()
  expect(screen.getByText('这次先逛到这里')).toBeInTheDocument()
})

test('uses a dedicated compact memory layout with Chinese preference values', async () => {
  render(<MobileAppPage />)
  await waitFor(() => expect(getMemory).toHaveBeenCalledTimes(1))

  fireEvent.click(screen.getByRole('button', { name: '记忆' }))
  expect(screen.getByRole('navigation', { name: '手机端记忆分类' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '偏好 2' })).toBeInTheDocument()
  expect(screen.getByText('不要中转')).toBeInTheDocument()
  expect(screen.queryByText('avoid_stopover')).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: '关注 1' }))
  expect(screen.getByText('秋天想去青岛')).toBeInTheDocument()
  expect(screen.queryByText('上海去三亚')).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: '查询 1' }))
  expect(screen.getByText('上海去三亚')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: '手帐 0' }))
  expect(screen.getByRole('region', { name: '旅行手帐留白页' })).toBeInTheDocument()
  expect(screen.getByText('把真正出发的那天，留给手帐')).toBeInTheDocument()
  expect(screen.getByText('未来的一页会记录')).toBeInTheDocument()
})

test('asks a first-time user to choose and name a companion before entering the app', async () => {
  getMemory.mockResolvedValueOnce({ memories: [], query_history: [] })
  render(<MobileAppPage />)

  expect(await screen.findByText('先选一个旅伴吧')).toBeInTheDocument()
  expect(screen.queryByRole('navigation', { name: '手机端主导航' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /登登柯基/ }))
  fireEvent.change(screen.getByLabelText('旅伴名字'), { target: { value: '旺仔' } })
  fireEvent.click(screen.getByRole('button', { name: '和旺仔一起开始' }))

  await waitFor(() => expect(patchMemory).toHaveBeenCalledWith({
    field: 'companion_profile',
    value: { kind: 'corgi', name: '旺仔' },
  }))
  expect(await screen.findByRole('navigation', { name: '手机端主导航' })).toBeInTheDocument()
  expect(screen.getByText('旺仔 在这里')).toBeInTheDocument()
})

test('keeps the profile header to avatar and nickname only', async () => {
  localStorage.setItem('fs_user_id', 'anon_mobile_test')
  localStorage.removeItem('fs_phone')
  render(<MobileAppPage />)
  await waitFor(() => expect(getMemory).toHaveBeenCalledTimes(1))

  fireEvent.click(screen.getByRole('button', { name: '我的' }))
  expect(await screen.findByRole('region', { name: '账号资料' })).toBeInTheDocument()
  expect(screen.getByLabelText('账号头像')).toBeInTheDocument()
  expect(screen.getByText('旅行者')).toBeInTheDocument()
  expect(screen.queryByText('游客模式')).not.toBeInTheDocument()
  expect(screen.queryByText(/跨设备同步/)).not.toBeInTheDocument()
  expect(screen.queryByText(/编号/)).not.toBeInTheDocument()
  expect(screen.queryByRole('region', { name: '账号数据概览' })).not.toBeInTheDocument()
  expect(screen.queryByText('偏好', { selector: 'div' })).not.toBeInTheDocument()
  expect(screen.queryByText('查询', { selector: 'div' })).not.toBeInTheDocument()
  expect(screen.queryByText('提醒', { selector: 'div' })).not.toBeInTheDocument()
  expect(screen.getByText('1 条提醒已保存到后端')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /价格提醒/ }))
  expect(screen.getByRole('region', { name: '手机端价格提醒列表' })).toBeInTheDocument()
  expect(screen.getByText('BJS → SHA')).toBeInTheDocument()
})

test('does not expose phone or account diagnostics for a stored account', async () => {
  render(<MobileAppPage />)
  await waitFor(() => expect(getMemory).toHaveBeenCalledTimes(1))

  fireEvent.click(screen.getByRole('button', { name: '我的' }))
  expect(await screen.findByText('旅行者')).toBeInTheDocument()
  expect(screen.queryByText('1380****0000')).not.toBeInTheDocument()
  expect(screen.queryByText(/已登录/)).not.toBeInTheDocument()
})
