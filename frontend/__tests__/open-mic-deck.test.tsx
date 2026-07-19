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

  test('explains the request lifecycle and trusted-system feedback loops', async () => {
    render(<OpenMicDeck />)

    fireEvent.click(screen.getByRole('button', { name: '第 7 页：Agent 内部' }))
    expect(await screen.findByRole('heading', { name: '一次请求，如何变成一份可验证的推荐' })).toBeInTheDocument()
    expect(screen.getByText(/LLM 8 秒超时后转入确定性槽位链/)).toBeInTheDocument()
    expect(screen.getByText(/flight_search → provider\.\* → normalize/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '第 8 页：可信闭环' }))
    expect(await screen.findByRole('heading', { name: '可信不是模型说对，而是系统让它难以说错' })).toBeInTheDocument()
    expect(screen.getByText(/ResponseFacts 深拷贝并冻结/)).toBeInTheDocument()
    expect(screen.getByText(/LangSmith Trace → Bad Case/)).toBeInTheDocument()
  })
})
