import type { Metadata } from 'next'
import { OpenMicDeck } from '@/components/open-mic-deck'

export const metadata: Metadata = {
  title: 'FareSniper | 产品开放麦',
  description: '会记住你如何定义特价的机票决策 Agent。',
}

export default function OpenMicPage() {
  return <OpenMicDeck />
}
