import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { OpenMicDeck } from '@/components/open-mic-deck'

describe('OpenMicDeck', () => {
  beforeEach(() => {
    window.location.hash = ''
  })

  test('starts with the FareSniper product thesis and keeps private resume contacts out', () => {
    const { container } = render(<OpenMicDeck />)

    expect(screen.getByRole('heading', { name: 'FareSniper' })).toBeInTheDocument()
    expect(screen.getByText(/会记住你如何定义“特价”/)).toBeInTheDocument()
    expect(container.querySelector('a[href^="tel:"]')).not.toBeInTheDocument()
    expect(container.querySelector('a[href^="mailto:"]')).not.toBeInTheDocument()
  })

  test('supports keyboard navigation and renders the resume-based profile', async () => {
    render(<OpenMicDeck />)

    fireEvent.keyDown(window, { key: 'ArrowRight' })

    expect(await screen.findByRole('heading', { name: '陈永琪' })).toBeInTheDocument()
    expect(screen.getByText('AI 产品经理')).toBeInTheDocument()
    expect(screen.getByText('Agent 产品实践者')).toBeInTheDocument()
    expect(screen.getByText(/中国科学院大学/)).toBeInTheDocument()
    expect(screen.getByText(/Keep · AI 平台事业部/)).toBeInTheDocument()
  })

  test('opens speaker notes for the current slide', () => {
    render(<OpenMicDeck />)

    fireEvent.click(screen.getByRole('button', { name: '打开讲稿' }))

    expect(screen.getByRole('complementary', { name: '当前页讲稿' })).toBeInTheDocument()
    expect(screen.getByText(/搜索机票并不难/)).toBeInTheDocument()
  })

  test('connects volatile prices, user segments, and competitive gaps', async () => {
    render(<OpenMicDeck />)

    fireEvent.click(screen.getByRole('button', { name: '第 3 页：用户洞察' }))
    expect(await screen.findByRole('heading', { name: '用户不是在找最低价，而是在等购买窗口' })).toBeInTheDocument()
    expect(screen.getByText(/机票价格随库存持续变化/)).toBeInTheDocument()
    expect(screen.getAllByText('核心竞争力')).toHaveLength(3)

    fireEvent.click(screen.getByRole('button', { name: '第 4 页：竞品与缺口' }))
    expect(await screen.findByRole('heading', { name: '不是没有单点能力，而是缺少同一个决策闭环' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '什么时候买？' })).toBeInTheDocument()
    expect(screen.getByText(/动态价格 × 完整成本 × 个人约束/)).toBeInTheDocument()
  })

  test('explains the end-to-end architecture and evaluation harness', async () => {
    render(<OpenMicDeck />)

    fireEvent.click(screen.getByRole('button', { name: '第 7 页：技术架构' }))
    expect(await screen.findByRole('heading', { name: '一次请求，如何成为可验证的购买建议' })).toBeInTheDocument()
    expect(screen.getByText(/Registry → slots → required/)).toBeInTheDocument()
    expect(screen.getByText(/as_completed · partial SSE/)).toBeInTheDocument()
    expect(screen.getByText(/eligibility · full cost · rank/)).toBeInTheDocument()
    expect(screen.getByText(/State · Auth · Timeout · Eligibility · Grounding/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '第 8 页：主动监控' }))
    expect(await screen.findByRole('heading', { name: '搜索结束后，Agent 仍在工作' })).toBeInTheDocument()
    expect(screen.getByText(/15m check · Ctrip 1h refresh/)).toBeInTheDocument()
    expect(screen.getByText(/constraints_ok ∧ offer_eligible/)).toBeInTheDocument()
    expect(screen.getByText(/PurchaseWindowOpened\(alert_id, offer_id, reason_codes, freshness\)/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '第 9 页：评测闭环' }))
    expect(await screen.findByRole('heading', { name: 'Bad Case 不是事故记录，而是回归资产' })).toBeInTheDocument()
    expect(screen.getByText(/LangSmith span \+ 安全脱敏/)).toBeInTheDocument()
    expect(screen.getByText(/AI 说 ¥700，卡片 ¥650；未知行李被当作免费/)).toBeInTheDocument()
    expect(screen.getByText(/ResponseFacts 同源 \+ null 保真 \+ 前后端契约测试/)).toBeInTheDocument()
  })
})
