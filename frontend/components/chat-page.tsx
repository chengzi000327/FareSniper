'use client'

import React from 'react'
import { motion } from 'motion/react'
import { History, Radar, Send } from 'lucide-react'
import { DiscoveryCardContent } from '@/components/discovery-card-content'
import { RecommendationCard } from '@/components/shared-components'
import { api } from '@/lib/api'
import { dealToCardProps } from '@/lib/mappers'
import type { DiscoveryCardContentProps } from '@/components/discovery-card-content'

type Message =
  | { role: 'user'; content: string }
  | { role: 'assistant'; content: string; isSpecial?: boolean; hasCard?: boolean; cardData?: DiscoveryCardContentProps }

export function ChatPage() {
  const [messages, setMessages] = React.useState<Message[]>([])
  const [inputValue, setInputValue] = React.useState('')
  const [recommendedQuestions, setRecommendedQuestions] = React.useState<string[]>([])

  React.useEffect(() => {
    const fetchQuestions = async () => {
      try {
        const resp = await api.getRecommendations()
        const hints = resp.cards.map((c) => c.query_hint).filter((h): h is string => !!h)
        if (hints.length > 0) {
          setRecommendedQuestions(hints.slice(0, 4))
          return
        }
      } catch {
        // fall through to local route
      }
      try {
        const response = await fetch('/api/recommended-questions')
        const data = (await response.json()) as string[]
        setRecommendedQuestions(data)
      } catch (error) {
        console.error(error)
      }
    }

    fetchQuestions()
  }, [])

  const handleSend = async () => {
    const value = inputValue.trim()
    if (!value) return

    setMessages((prev) => [...prev, { role: 'user', content: value }])
    setInputValue('')

    setMessages((prev) => [
      ...prev,
      { role: 'assistant', content: '正在为您深度扫描全网特价资源...', isSpecial: true },
    ])

    try {
      const resp = await api.search(value)
      const deals = resp.deals ?? []
      const bestDeal = deals[0]
      const assistantText =
        resp.recommendation?.text ||
        (bestDeal ? `为您找到 ${deals.length} 个航班，最低价 ¥${bestDeal.price}` : '暂未找到符合条件的航班，请换个搜索词试试。')

      setMessages((prev) => {
        const filtered = prev.filter((m) => !('isSpecial' in m && m.isSpecial))
        return [
          ...filtered,
          {
            role: 'assistant',
            content: assistantText,
            hasCard: !!bestDeal,
            cardData: bestDeal ? dealToCardProps(bestDeal) : undefined,
          },
        ]
      })
    } catch {
      setMessages((prev) => {
        const filtered = prev.filter((m) => !('isSpecial' in m && m.isSpecial))
        return [...filtered, { role: 'assistant', content: '搜索失败，请检查网络后重试。' }]
      })
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center justify-between px-5 pt-6 sm:px-8 lg:px-12 lg:pt-8">
        <h1 className="text-3xl font-bold text-brand-text sm:text-4xl">对话空间</h1>
        <button className="flex items-center gap-2 text-sm text-brand-muted transition hover:text-brand-text">
          <History className="h-4 w-4" />
          历史对话
        </button>
      </div>

      <div
        className={`thin-scrollbar flex-1 overflow-y-auto px-5 py-8 sm:px-8 lg:px-[12vw] lg:py-12 ${
          messages.length === 0 ? 'flex flex-col justify-center' : 'space-y-8'
        }`}
      >
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center">
            <motion.h2 className="mb-4 text-center font-serif text-5xl text-brand-text sm:text-6xl">想去哪？</motion.h2>
            <p className="mb-10 max-w-[34rem] text-center text-base leading-8 text-brand-muted text-balance sm:text-lg">
              用自然语言告诉我你的出发地、目的地、时间和预算，我来帮你发现特价机票，监控价格。
            </p>

            <div className="grid w-full max-w-4xl gap-4 md:grid-cols-2">
              <RecommendationCard from="上海" to="三亚" price="399" date="五一假期" />
              <RecommendationCard from="北京" to="大理" price="568" date="下周末" />
              <RecommendationCard from="成都" to="丽江" price="420" date="六月出行" />
              <RecommendationCard from="广州" to="青岛" price="480" date="端午假期" />
            </div>
          </div>
        ) : (
          messages.map((message, index) => (
            <motion.div key={`${message.role}-${index}`} className={`flex flex-col ${message.role === 'user' ? 'items-end' : 'items-start'}`}>
              <div
                className={`max-w-3xl rounded-[28px] p-5 text-sm sm:text-base ${
                  message.role === 'user' ? 'rounded-tr-none bg-brand-text text-white' : 'rounded-tl-none border border-brand-text/5 bg-white shadow-sm'
                }`}
              >
                {'isSpecial' in message && message.isSpecial ? (
                  <div className="flex items-center gap-2 font-bold text-brand-orange">
                    <Radar className="h-4 w-4 animate-spin" />
                    <span>{message.content}</span>
                  </div>
                ) : (
                  message.content
                )}
              </div>

              {'hasCard' in message && message.hasCard && message.cardData ? (
                <div className="mt-4 w-full max-w-2xl overflow-hidden rounded-[28px] border border-brand-text/5 bg-white shadow-card">
                  <DiscoveryCardContent {...message.cardData} />
                </div>
              ) : null}
            </motion.div>
          ))
        )}
      </div>

      <div className={`px-5 pb-6 pt-2 sm:px-8 lg:px-[12vw] ${messages.length === 0 ? 'lg:pb-12' : 'lg:pb-8'}`}>
        <div className="flex items-center rounded-[28px] border border-brand-text/5 bg-white p-2 shadow-card">
          <input
            type="text"
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            onKeyDown={(event) => event.key === 'Enter' && handleSend()}
            placeholder="比如：五一去三亚，预算 600..."
            className="flex-1 bg-transparent px-4 py-3 text-sm sm:text-base"
          />
          <motion.button
            type="button"
            onClick={handleSend}
            whileTap={{ scale: 0.96 }}
            className="rounded-2xl bg-brand-text p-3 text-white transition hover:bg-brand-orange"
          >
            <Send className="h-5 w-5" />
          </motion.button>
        </div>

        {messages.length === 0 ? (
          <div className="mt-4 flex flex-wrap items-center justify-center gap-3">
            {recommendedQuestions.map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => setInputValue(tag)}
                className="rounded-full border border-brand-text/5 px-4 py-2 text-xs text-brand-muted transition hover:bg-white hover:text-brand-orange sm:text-sm"
              >
                {tag}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}
