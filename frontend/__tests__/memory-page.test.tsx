import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import MemoryPage from '@/app/memory/page'
import { MemoryPage as SharedMemoryPage } from '@/components/memory-page'

const { getMemory, patchMemory, deleteMemory } = vi.hoisted(() => ({
  getMemory: vi.fn(),
  patchMemory: vi.fn(),
  deleteMemory: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  api: { getMemory },
  memoryApi: { patch: patchMemory, del: deleteMemory },
}))

const populatedMemory = {
  memories: [
    {
      field: 'companion_profile',
      value: { kind: 'cat', name: '云朵', proactivity: 'standard' },
      label: '旅伴档案',
      value_display: '',
      source: 'manual',
    },
    {
      field: 'travel_ideas',
      value: [{ id: 'idea-1', text: '秋天想去青岛吹吹海风', created_at: '2026-07-19T10:00:00+08:00' }],
      label: '出行想法',
      value_display: '',
      source: 'manual',
    },
    {
      field: 'budget',
      value: 1200,
      label: '心理价位',
      value_display: '¥1,200',
      source: 'auto',
    },
    {
      field: 'frequent_cities',
      value: ['三亚', '成都'],
      label: '常去城市',
      value_display: '三亚、成都',
      source: 'manual',
    },
    {
      field: 'constraints',
      value: ['direct_only', 'avoid_redeye'],
      label: '出行习惯',
      value_display: '只看直飞、避开红眼航班',
      source: 'manual',
    },
  ],
  query_history: [
    {
      id: 'query-1',
      query: {
        text: '7月25日北京到三亚的直飞机票',
        intent: {
          origin: { city_name: '北京' },
          destination: { city_name: '三亚' },
        },
      },
      created_at: '2026-07-18T14:30:00+08:00',
    },
    {
      id: 'query-2',
      query: {
        text: '上海飞成都下周五',
        intent: { origin: '上海', destination: '成都' },
      },
      created_at: '2026-07-17T09:05:00+08:00',
    },
  ],
}

beforeEach(() => {
  getMemory.mockReset()
  patchMemory.mockReset()
  deleteMemory.mockReset()
  patchMemory.mockResolvedValue({ ok: true })
  deleteMemory.mockResolvedValue(undefined)
})

test('the memory route reuses the shared journal component', () => {
  expect(MemoryPage).toBe(SharedMemoryPage)
})

test('keeps fare preferences primary and separates recent attention from a confirmed trip', async () => {
  getMemory.mockResolvedValue(populatedMemory)

  render(<MemoryPage />)
  await waitFor(() => expect(getMemory).toHaveBeenCalledTimes(1))

  expect(await screen.findByRole('heading', { name: '云朵 正在帮你记住查价条件' })).toBeInTheDocument()
  expect(screen.getByText('FareSniper · 特价机票发现')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: '心理价位' })).toBeInTheDocument()
  expect(screen.getByText('¥1,200')).toBeInTheDocument()
  expect(screen.getByText('三亚、成都')).toBeInTheDocument()
  expect(screen.getByText('只看直飞、避开红眼航班')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: '最近关注 1' }))
  expect(screen.getByText('秋天想去青岛吹吹海风')).toBeInTheDocument()
  expect(screen.queryByText('北京 → 三亚')).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: '最近查询 2' }))
  expect(screen.getByText('北京 → 三亚')).toBeInTheDocument()
  expect(screen.getByText('你查询了“7月25日北京到三亚的直飞机票”。')).toBeInTheDocument()
  expect(screen.getAllByText(/来自真实查询记录/)).toHaveLength(2)

  fireEvent.click(screen.getByRole('button', { name: '旅行手帐 0' }))
  expect(screen.getByText('这一页先留白')).toBeInTheDocument()
  expect(screen.getByText('查询、收藏或点击预订不会自动写成旅行经历。')).toBeInTheDocument()
  expect(screen.getByAltText('云朵猫·journal')).toBeInTheDocument()

  expect(screen.queryByText(/已经去了青岛/)).not.toBeInTheDocument()
  expect(screen.queryByText(/已经购买/)).not.toBeInTheDocument()
})

test('lets the user choose and name a companion without touching other memories', async () => {
  getMemory.mockResolvedValue({ memories: [], query_history: [] })

  render(<MemoryPage />)
  expect(await screen.findByRole('heading', { name: '云朵 正在帮你记住查价条件' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '选择旅伴' }))

  fireEvent.click(screen.getByRole('button', { name: '选择登机柯基' }))
  fireEvent.change(screen.getByLabelText('旅伴名字'), { target: { value: '旺仔' } })
  fireEvent.click(screen.getByRole('button', { name: '保存旅伴' }))

  await waitFor(() => expect(patchMemory).toHaveBeenCalledWith({
    field: 'companion_profile',
    value: { kind: 'corgi', name: '旺仔', proactivity: 'standard' },
  }))
  expect(await screen.findByRole('heading', { name: '旺仔 正在帮你记住查价条件' })).toBeInTheDocument()
})

test('saves a dated travel idea and keeps it distinct from a confirmed trip', async () => {
  getMemory.mockResolvedValue(populatedMemory)

  render(<MemoryPage />)
  await screen.findByRole('heading', { name: '云朵 正在帮你记住查价条件' })

  fireEvent.change(screen.getByLabelText('想去哪里，或者为什么想出发'), {
    target: { value: '春节想带爸妈回家' },
  })
  fireEvent.click(screen.getByRole('button', { name: '记入最近关注' }))

  await waitFor(() => expect(patchMemory).toHaveBeenCalledWith(expect.objectContaining({
    field: 'travel_ideas',
  })))
  expect(await screen.findByText('春节想带爸妈回家')).toBeInTheDocument()
  expect(screen.getAllByText('这是你亲自记下的一个出行念头，还不代表已经确定行程。')).toHaveLength(2)
  expect(screen.getAllByText(/不代表已经购票/)).toHaveLength(2)
})

test('edits and forgets fare preferences through the backend memory API', async () => {
  getMemory.mockResolvedValue(populatedMemory)

  render(<MemoryPage />)
  await screen.findByRole('heading', { name: '心理价位' })

  fireEvent.click(screen.getByRole('button', { name: '编辑心理价位' }))
  fireEvent.change(screen.getByLabelText('修改心理价位'), { target: { value: '850' } })
  fireEvent.click(screen.getByRole('button', { name: '保存修改' }))

  await waitFor(() => expect(patchMemory).toHaveBeenCalledWith({ field: 'budget', value: 850 }))

  fireEvent.click(screen.getByRole('button', { name: '忘记常去城市' }))
  expect(screen.getByText('忘记后，这项偏好也不会再参与航班匹配和推荐。')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '确认忘记' }))

  await waitFor(() => expect(deleteMemory).toHaveBeenCalledWith('frequent_cities'))
})

test('lets an empty memory create a fare preference manually', async () => {
  getMemory.mockResolvedValue({ memories: [], query_history: [] })

  render(<MemoryPage />)
  await screen.findByText('还没有形成机票偏好')

  fireEvent.click(screen.getByRole('button', { name: '添加偏好' }))
  fireEvent.change(screen.getByLabelText('偏好内容'), { target: { value: '900' } })
  fireEvent.click(screen.getByRole('button', { name: '保存偏好' }))

  await waitFor(() => expect(patchMemory).toHaveBeenCalledWith({ field: 'budget', value: 900 }))
})

test('shows neutral empty states instead of invented stories', async () => {
  getMemory.mockResolvedValue({ memories: [], query_history: [] })

  render(<MemoryPage />)

  expect(await screen.findByText('还没有形成机票偏好')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '最近关注 0' }))
  expect(screen.getByText('最近还没有明确关注的出行')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '最近查询 0' }))
  expect(screen.getByText('最近还没有机票查询')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '旅行手帐 0' }))
  expect(screen.getByText('这一页先留白')).toBeInTheDocument()

  expect(screen.queryByText(/海岛与松弛感/)).not.toBeInTheDocument()
  expect(screen.queryByText(/五一、端午、暑假/)).not.toBeInTheDocument()
})

test('keeps the journal neutral when memory loading fails', async () => {
  getMemory.mockRejectedValue(new Error('offline'))

  render(<MemoryPage />)

  expect(await screen.findByText('暂时无法读取记忆')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '重新读取' })).toBeInTheDocument()
  expect(screen.queryByText(/更容易被海岛/)).not.toBeInTheDocument()
})
