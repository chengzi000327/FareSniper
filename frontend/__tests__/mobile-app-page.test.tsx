import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import MobilePage from '@/app/mobile/page'
import { MobileAppPage } from '@/components/mobile-app-page'

const { getMemory, listRecommendations, patchMemory, authStatus, requestOtp, verifyOtp } = vi.hoisted(() => ({
  getMemory: vi.fn(),
  listRecommendations: vi.fn(),
  patchMemory: vi.fn(),
  authStatus: vi.fn(),
  requestOtp: vi.fn(),
  verifyOtp: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  memoryApi: { get: getMemory, patch: patchMemory, del: vi.fn() },
  recApi: { list: listRecommendations },
  authApi: { status: authStatus, requestOtp, verify: verifyOtp },
  api: { getMemory },
  searchApi: { stream: vi.fn() },
}))

beforeEach(() => {
  getMemory.mockReset()
  listRecommendations.mockReset()
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
  expect(await screen.findByText('云朵 在陪你找低价')).toBeInTheDocument()
  expect(screen.getByText('1 个明确关注')).toBeInTheDocument()
  expect(screen.getByText('1 次查询')).toBeInTheDocument()
  expect(screen.getByText('上海 → 三亚')).toBeInTheDocument()
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

test('shows the real guest account state when phone login is not configured', async () => {
  localStorage.setItem('fs_user_id', 'anon_mobile_test')
  localStorage.removeItem('fs_phone')
  render(<MobileAppPage />)
  await waitFor(() => expect(getMemory).toHaveBeenCalledTimes(1))

  fireEvent.click(screen.getByRole('button', { name: '我的' }))
  expect(await screen.findByText('本机游客账号')).toBeInTheDocument()
  expect(screen.getByText('手机号登录将在短信服务配置后开放')).toBeInTheDocument()
  expect(screen.getByText('账号编号 · BILETEST')).toBeInTheDocument()
})

test('binds a guest account by phone when SMS login is available', async () => {
  localStorage.setItem('fs_user_id', 'anon_mobile_test')
  localStorage.removeItem('fs_phone')
  authStatus.mockResolvedValueOnce({ phone_login_available: true })
  verifyOtp.mockImplementationOnce(async () => {
    localStorage.setItem('fs_user_id', 'user_phone_test')
    return { access_token: 'token', user_id: 'user_phone_test' }
  })
  render(<MobileAppPage />)
  await waitFor(() => expect(authStatus).toHaveBeenCalledTimes(1))

  fireEvent.click(screen.getByRole('button', { name: '我的' }))
  fireEvent.click(await screen.findByRole('button', { name: '绑定手机号，跨设备保留' }))
  fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800000000' } })
  fireEvent.click(screen.getByRole('button', { name: '获取验证码' }))
  await waitFor(() => expect(requestOtp).toHaveBeenCalledWith('+8613800000000'))
  fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '123456' } })
  fireEvent.click(screen.getByRole('button', { name: '登录并接回数据' }))

  await waitFor(() => expect(verifyOtp).toHaveBeenCalledWith('+8613800000000', '123456'))
  expect(await screen.findByText('正式账号')).toBeInTheDocument()
  expect(screen.getByText('1380****0000')).toBeInTheDocument()
})
