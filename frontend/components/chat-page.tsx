'use client'

import React from 'react'
import { motion } from 'motion/react'
import { History, Radar, Send } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'
import { DiscoveryCardContent } from '@/components/discovery-card-content'
import { RecommendationCard } from '@/components/shared-components'
import { recApi, searchApi } from '@/lib/api'
import { formatCurrency } from '@/lib/currency'
import { dealToCardProps } from '@/lib/mappers'
import type { DiscoveryCardContentProps } from '@/components/discovery-card-content'
import type { ChatSearchResponse, DealCardDto, SearchStreamEvent } from '@/lib/api'

type Message =
  | { id: string; role: 'user'; content: string }
  | { id: string; role: 'assistant'; content: string; isSpecial?: boolean; hasCard?: boolean; cardData?: DiscoveryCardContentProps }

type ActiveSearch = {
  id: string
  assistantMessageId: string
  controller: AbortController
  awaitingCanonicalAfterValidation?: boolean
}

function assistantText(response: ChatSearchResponse) {
  const deals = response.deals ?? []
  const bestDeal = deals[0]

  if (response.recommendation?.text) return response.recommendation.text
  if (!bestDeal) return '暂未找到符合条件的航班，请换个搜索词试试。'
  return bestDeal.price === null
    ? `为您找到 ${deals.length} 个航班，请查看实时价格。`
    : `为您找到 ${deals.length} 个航班，最低价 ${formatCurrency(bestDeal.price, bestDeal.currency)}`
}

function cardPropsFromDeal(deal: DealCardDto): DiscoveryCardContentProps {
  return { ...dealToCardProps(deal), totalPrice: deal.total_price }
}

function finalizeCard(cardData: DiscoveryCardContentProps): DiscoveryCardContentProps {
  return {
    ...cardData,
    prices: cardData.prices.map((price) =>
      price.provider_status === 'loading'
        ? {
            ...price,
            provider_status:
              price.data_provider === 'ctrip_snapshot' ? 'queued' : 'timeout',
          }
        : price
    ),
  }
}

function applyProviderStatus(
  cardData: DiscoveryCardContentProps,
  event: SearchStreamEvent
): DiscoveryCardContentProps {
  const provider = event.payload.provider
  const status = event.payload.status
  if (!provider || !status) return cardData

  return {
    ...cardData,
    prices: cardData.prices.map((price) =>
      price.data_provider === provider ||
      (provider === 'ctrip' && price.data_provider === 'ctrip_snapshot') ||
      (provider === 'serpapi' && price.data_provider === 'serpapi_google_flights') ||
      price.name === provider
        ? { ...price, provider_status: status }
        : price
    ),
  }
}

// 助手气泡用 Markdown 渲染：支持 GFM 表格/标题/加粗/列表，rehypeSanitize 防 XSS。
// prose 限定在气泡内，避免 LLM 输出的 ### / |表格| 直接暴露成纯文本。
function MarkdownMessage({ content }: { content: string }) {
  return (
    <div className="prose prose-sm max-w-none break-words prose-headings:my-2 prose-p:my-1.5 prose-table:my-2 prose-th:px-2 prose-td:px-2 prose-li:my-0.5 prose-pre:my-2">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
        {content}
      </ReactMarkdown>
    </div>
  )
}

export function ChatPage({
  initialQuery,
  onInitialQueryConsumed,
}: {
  initialQuery?: string | null
  onInitialQueryConsumed?: () => void
}) {
  const [messages, setMessages] = React.useState<Message[]>([])
  const [inputValue, setInputValue] = React.useState('')
  const [sessionId, setSessionId] = React.useState<string | null>(null)
  const [recommendedQuestions, setRecommendedQuestions] = React.useState<string[]>([])
  const activeSearchRef = React.useRef<ActiveSearch | null>(null)
  const sessionIdRef = React.useRef(sessionId)
  const pendingFollowUpRef = React.useRef<string | null>(null)
  const startSearchRef = React.useRef<((value: string) => void) | null>(null)
  const isMountedRef = React.useRef(true)
  const nextMessageIdRef = React.useRef(0)

  React.useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
      pendingFollowUpRef.current = null
      const activeSearch = activeSearchRef.current
      activeSearchRef.current = null
      activeSearch?.controller.abort()
    }
  }, [])

  React.useEffect(() => {
    const fetchQuestions = async () => {
      try {
        const resp = await recApi.list()
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

  const setCurrentSessionId = (nextSessionId: string | null) => {
    sessionIdRef.current = nextSessionId
    setSessionId(nextSessionId)
  }

  const flushPendingFollowUp = () => {
    if (!isMountedRef.current || activeSearchRef.current) return

    const pendingFollowUp = pendingFollowUpRef.current
    if (!pendingFollowUp) return

    pendingFollowUpRef.current = null
    startSearchRef.current?.(pendingFollowUp)
  }

  const startSearch = async (value: string) => {

    const previousSearch = activeSearchRef.current
    if (previousSearch) {
      activeSearchRef.current = null
      previousSearch.controller.abort()
      setMessages((prev) =>
        prev.map((message) => {
          if (message.role !== 'assistant' || message.id !== previousSearch.assistantMessageId) return message

          const cardData = message.cardData ? finalizeCard(message.cardData) : undefined
          return {
            ...message,
            content: cardData ? '已保留当前报价，其余来源已停止更新。' : '已取消本次搜索。',
            isSpecial: false,
            hasCard: !!cardData,
            cardData,
          }
        })
      )
    }
    const clientSearchId = `search-${++nextMessageIdRef.current}`
    const assistantMessageId = `assistant-${++nextMessageIdRef.current}`
    const controller = new AbortController()
    activeSearchRef.current = { id: clientSearchId, assistantMessageId, controller }

    setMessages((prev) => [...prev, { id: `user-${++nextMessageIdRef.current}`, role: 'user', content: value }])

    setMessages((prev) => [
      ...prev,
      { id: assistantMessageId, role: 'assistant', content: '正在为您深度扫描全网特价资源...', isSpecial: true },
    ])

    const updateAssistant = (update: (message: Extract<Message, { role: 'assistant' }>) => Extract<Message, { role: 'assistant' }>) => {
      setMessages((prev) =>
        prev.map((message) =>
          message.role === 'assistant' && message.id === assistantMessageId ? update(message) : message
        )
      )
    }

    const completeSearch = (response: ChatSearchResponse) => {
      const bestDeal = response.deals?.[0]
      updateAssistant((message) => ({
        ...message,
        content: assistantText(response),
        isSpecial: false,
        hasCard: !!bestDeal,
        cardData: bestDeal ? finalizeCard(cardPropsFromDeal(bestDeal)) : undefined,
      }))
    }

    let latestSequence = 0
    let completeEventReceived = false
    let validationErrorShown = false
    const isActiveSearch = () => activeSearchRef.current?.id === clientSearchId
    const settleIncompleteSearch = () => {
      updateAssistant((message) => {
        const hasCard = !!message.cardData
        return {
          ...message,
          content: hasCard ? '已收到部分结果，其余来源暂时超时。' : '搜索未完整结束，请重试。',
          isSpecial: false,
          hasCard,
          cardData: hasCard && message.cardData ? finalizeCard(message.cardData) : undefined,
        }
      })
    }
    const handleEvent = (event: SearchStreamEvent) => {
      if (!isActiveSearch() || completeEventReceived || event.sequence <= latestSequence) return
      latestSequence = event.sequence

      if (validationErrorShown && event.type !== 'complete') return

      if (event.type === 'provider_status') {
        updateAssistant((message) =>
          message.cardData ? { ...message, cardData: applyProviderStatus(message.cardData, event) } : message
        )
        return
      }

      if (event.type === 'results') {
        const bestDeal = event.payload.deals?.[0]
        if (!bestDeal) return
        updateAssistant((message) => ({
          ...message,
          isSpecial: true,
          hasCard: true,
          cardData: cardPropsFromDeal(bestDeal),
        }))
        return
      }

      if (event.type === 'validation_error') {
        validationErrorShown = true
        if (isActiveSearch() && activeSearchRef.current) {
          activeSearchRef.current.awaitingCanonicalAfterValidation = true
        }
        updateAssistant((message) => ({
          ...message,
          content: event.payload.message ?? '请输入完整的航班信息。',
          isSpecial: false,
          hasCard: false,
          cardData: undefined,
        }))
        return
      }

      if (event.type === 'complete') {
        completeEventReceived = true
        if (event.payload.response) {
          setCurrentSessionId(event.payload.response.session_id ?? null)
          if (!validationErrorShown) completeSearch(event.payload.response)
          if (isActiveSearch()) {
            activeSearchRef.current = null
            flushPendingFollowUp()
          }
          return
        }
        if (!validationErrorShown) {
          updateAssistant((message) => ({
            ...message,
            content: event.payload.message ?? event.payload.error ?? '搜索失败，请检查网络后重试。',
            isSpecial: false,
            hasCard: false,
            cardData: undefined,
          }))
        }
        if (isActiveSearch()) {
          activeSearchRef.current = null
          flushPendingFollowUp()
        }
      }
    }

    try {
      await searchApi.stream(
        { message: value, session_id: sessionIdRef.current },
        handleEvent,
        controller.signal
      )
      if (isActiveSearch() && !completeEventReceived && !validationErrorShown) settleIncompleteSearch()
    } catch {
      if (isActiveSearch() && !completeEventReceived && !validationErrorShown) settleIncompleteSearch()
    } finally {
      if (isActiveSearch()) activeSearchRef.current = null
      flushPendingFollowUp()
    }
  }

  startSearchRef.current = startSearch

  React.useEffect(() => {
    const query = initialQuery?.trim()
    if (!query || activeSearchRef.current) return
    onInitialQueryConsumed?.()
    void startSearchRef.current?.(query)
  }, [initialQuery, onInitialQueryConsumed])

  const handleSend = () => {
    const value = inputValue.trim()
    if (!value) return

    setInputValue('')
    if (activeSearchRef.current?.awaitingCanonicalAfterValidation) {
      pendingFollowUpRef.current = value
      return
    }

    void startSearch(value)
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
          messages.map((message) => (
            <motion.div key={message.id} className={`flex flex-col ${message.role === 'user' ? 'items-end' : 'items-start'}`}>
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
                ) : message.role === 'assistant' ? (
                  <MarkdownMessage content={message.content} />
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
