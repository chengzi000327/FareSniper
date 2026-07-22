import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import MobilePage from '@/app/mobile/page'
import { MobileAppPage } from '@/components/mobile-app-page'

const { getMemory, listRecommendations } = vi.hoisted(() => ({
  getMemory: vi.fn(),
  listRecommendations: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  memoryApi: { get: getMemory, patch: vi.fn(), del: vi.fn() },
  recApi: { list: listRecommendations },
  api: { getMemory },
  searchApi: { stream: vi.fn() },
}))

beforeEach(() => {
  getMemory.mockReset()
  listRecommendations.mockReset()
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
  fireEvent.click(screen.getByRole('button', { name: '探索' }))
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
