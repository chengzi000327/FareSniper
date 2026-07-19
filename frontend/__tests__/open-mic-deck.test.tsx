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
    expect(screen.getByText(/中国科学院大学/)).toBeInTheDocument()
    expect(screen.getByText(/Keep · AI 平台事业部/)).toBeInTheDocument()
  })

  test('opens speaker notes for the current slide', () => {
    render(<OpenMicDeck />)

    fireEvent.click(screen.getByRole('button', { name: '打开讲稿' }))

    expect(screen.getByRole('complementary', { name: '当前页讲稿' })).toBeInTheDocument()
    expect(screen.getByText(/搜索机票并不难/)).toBeInTheDocument()
  })

  test('explains layered intent routing and the agent harness', async () => {
    render(<OpenMicDeck />)

    fireEvent.click(screen.getByRole('button', { name: '第 7 页：意图识别' }))
    expect(await screen.findByRole('heading', { name: '意图识别不是一次分类，而是一条分层路由' })).toBeInTheDocument()
    expect(screen.getByText(/当前 DeepSeek 不支持就自动跳过/)).toBeInTheDocument()
    expect(screen.getByText(/LLM 8s 超时 → deterministic fallback/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '第 8 页：Harness 工程' }))
    expect(await screen.findByRole('heading', { name: '把概率模型，装进一个可控系统' })).toBeInTheDocument()
    expect(screen.getByText(/FlightOffer 归一化、winner 资格校验、ResponseFacts 冻结同源/)).toBeInTheDocument()
    expect(screen.getByText(/Context · State · Tools · Guardrails · Truth · Evaluation/)).toBeInTheDocument()
  })
})
