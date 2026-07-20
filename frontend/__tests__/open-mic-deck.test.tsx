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
    expect(await screen.findByRole('heading', { name: 'FareSniper Agent：从自然语言到可信决策' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /A\. 交互与上下文层/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /B\. 意图与编排层/ })).toBeInTheDocument()
    expect(screen.getByText(/意图识别与要素校验/)).toBeInTheDocument()
    expect(screen.getByText(/资格过滤 · 完整成本 · 排序/)).toBeInTheDocument()
    expect(screen.getByText(/鉴权 · 状态 · 数据契约 · 超时熔断 · 事实约束 · 幂等/)).toBeInTheDocument()
    expect(screen.getAllByTestId(/architecture-handoff-/)).toHaveLength(4)

    fireEvent.click(screen.getByRole('button', { name: '第 8 页：分层实现' }))
    expect(await screen.findByRole('heading', { name: '每一层，都回答三个工程问题' })).toBeInTheDocument()
    expect(screen.getByText('有什么用')).toBeInTheDocument()
    expect(screen.getByText('怎么使用')).toBeInTheDocument()
    expect(screen.getByText('如何实现')).toBeInTheDocument()
    expect(screen.getByText(/意图注册表 \+ 向量 FastPath \+ 确定性解析/)).toBeInTheDocument()
    expect(screen.getByText(/FlightProvider 接口/)).toBeInTheDocument()
    expect(screen.getByText(/Pydantic FlightOffer 契约/)).toBeInTheDocument()
    expect(screen.getByText(/平台边界/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '第 9 页：工程演进' }))
    expect(await screen.findByRole('heading', { name: '从能运行，到可靠、可扩展、可回滚' })).toBeInTheDocument()
    expect(screen.getByText(/15m check · 1h refresh/)).toBeInTheDocument()
    expect(screen.getByText(/constraints_ok ∧ offer_eligible/)).toBeInTheDocument()
    expect(screen.getByText(/transactional outbox · idempotency · retry \/ DLQ/)).toBeInTheDocument()
    expect(screen.getByText(/metrics SLO · feature flag · canary · rollback/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '第 10 页：评测闭环' }))
    expect(await screen.findByRole('heading', { name: 'Bad Case 不是事故记录，而是回归资产' })).toBeInTheDocument()
    expect(screen.getByText(/LangSmith span \+ 安全脱敏/)).toBeInTheDocument()
    expect(screen.getByText(/AI 说 ¥700，卡片 ¥650；未知行李被当作免费/)).toBeInTheDocument()
    expect(screen.getByText(/ResponseFacts 同源 \+ null 保真 \+ 前后端契约测试/)).toBeInTheDocument()
  })
})
