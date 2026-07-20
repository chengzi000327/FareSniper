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
    expect(await screen.findByRole('heading', { name: '用户说一句话之后，系统实际做了什么' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '先知道是谁在问、他在意什么' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '把一句话整理成查询条件' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '分别去多个来源查真实航班' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '收齐可用结果，再统一比较' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '给出结果，关注后继续盯价' })).toBeInTheDocument()
    expect(screen.getByText(/飞猪查询 · 携程快照 · SerpAPI/)).toBeInTheDocument()
    expect(screen.getByText(/身份与偏好 · 查询与超时 · 价格计算 · 排序与提醒/)).toBeInTheDocument()
    expect(screen.queryByText(/FlightProvider 适配器/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Pydantic 契约/)).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '第 8 页：监控闭环' }))
    expect(await screen.findByRole('heading', { name: '当前做到哪，下一步为什么这样改' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '每 15 分钟检查' })).toBeInTheDocument()
    expect(screen.getByText(/价格 · 时间 · 行李 · 历史低位/)).toBeInTheDocument()
    expect(screen.getByText(/事件先落库、幂等去重、失败自动重试/)).toBeInTheDocument()
    expect(screen.getByText(/规则负责触发；模型只解释/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '第 9 页：评测闭环' }))
    expect(await screen.findByRole('heading', { name: 'Bad Case 不是事故记录，而是回归资产' })).toBeInTheDocument()
    expect(screen.getByText(/LangSmith span \+ 安全脱敏/)).toBeInTheDocument()
    expect(screen.getByText(/AI 说 ¥700，卡片 ¥650；未知行李被当作免费/)).toBeInTheDocument()
    expect(screen.getByText(/ResponseFacts 同源 \+ null 保真 \+ 前后端契约测试/)).toBeInTheDocument()
  })
})
