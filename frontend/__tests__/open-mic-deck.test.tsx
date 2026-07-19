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

  test('explains the end-to-end architecture and evaluation harness', async () => {
    render(<OpenMicDeck />)

    fireEvent.click(screen.getByRole('button', { name: '第 7 页：技术架构' }))
    expect(await screen.findByRole('heading', { name: '一条请求，如何穿过完整 Agent 系统' })).toBeInTheDocument()
    expect(screen.getByText(/Intent Registry 规则召回并缓存 60 秒/)).toBeInTheDocument()
    expect(screen.getByText(/ReAct ⇄ tools · 8s fallback/)).toBeInTheDocument()
    expect(screen.getByText(/Context · State · Tools · Guardrails · Truth · Evaluation/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '第 8 页：评测闭环' }))
    expect(await screen.findByRole('heading', { name: 'Bad Case 不是事故记录，而是回归资产' })).toBeInTheDocument()
    expect(screen.getByText(/LangSmith span \+ 安全脱敏/)).toBeInTheDocument()
    expect(screen.getByText(/AI 说 ¥700，卡片 ¥650；未知行李被当作免费/)).toBeInTheDocument()
    expect(screen.getByText(/ResponseFacts 同源 \+ null 保真 \+ 前后端契约测试/)).toBeInTheDocument()
  })
})
