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
})
