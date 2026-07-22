'use client'

import React from 'react'
import { motion } from 'motion/react'
import { BellRing, Compass, History, MessageCircle, Plane, Radar, Send, Sparkles } from 'lucide-react'
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
  | { id: string; role: 'assistant'; content: string; isSpecial?: boolean; hasCard?: boolean; cardData?: DiscoveryCardContentProps; retryQuery?: string }

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
function MarkdownMessage({ content, compact = false }: { content: string; compact?: boolean }) {
  const hasTable = /^\s*\|.+\|\s*$/m.test(content)
  return (
    <>
      {compact && hasTable ? (
        <div className="mb-2 flex items-center gap-2 text-[10px] font-bold text-brand-orange">
          <span className="h-px flex-1 bg-brand-orange/20" />
          航班列表可左右滑动
          <span className="h-px flex-1 bg-brand-orange/20" />
        </div>
      ) : null}
      <div className={`prose prose-sm max-w-none break-words prose-headings:my-2 prose-p:my-1.5 prose-table:my-2 prose-th:px-2 prose-td:px-2 prose-li:my-0.5 prose-pre:my-2 ${compact && hasTable ? 'overflow-x-auto overscroll-x-contain [&_table]:min-w-[34rem] [&_th]:whitespace-nowrap [&_td]:whitespace-nowrap' : ''}`}>
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
          {content}
        </ReactMarkdown>
      </div>
    </>
  )
}

export function ChatPage({
  initialQuery,
  onInitialQueryConsumed,
  compact = false,
  assistantName = '旅伴',
  recentQuery,
  onOpenExplore,
}: {
  initialQuery?: string | null
  onInitialQueryConsumed?: () => void
  compact?: boolean
  assistantName?: string
  recentQuery?: string | null
  onOpenExplore?: () => void
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
          content: hasCard ? '已收到部分结果，其余来源暂时超时。' : '这次没有拿到完整结果，可以重新查询刚才的条件。',
          isSpecial: false,
          hasCard,
          cardData: hasCard && message.cardData ? finalizeCard(message.cardData) : undefined,
          retryQuery: hasCard ? undefined : value,
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

  const compactStarters = [
    {
      title: '查一趟具体航班',
      detail: '已经知道大概去哪、什么时候走',
      prompt: recommendedQuestions[0] || '下周五上海去三亚，预算 800 元',
      icon: <Plane className="h-4 w-4" />,
    },
    {
      title: '还没想好，先逛探索',
      detail: '从真实推荐里发现想去的地方',
      prompt: null,
      icon: <Compass className="h-4 w-4" />,
    },
    recentQuery
      ? {
          title: '继续上次的查询',
          detail: recentQuery,
          prompt: recentQuery,
          icon: <History className="h-4 w-4" />,
        }
      : {
          title: '关注一条航线价格',
          detail: '有目标价后，交给我持续检查',
          prompt: '我想关注上海到三亚的机票，低于 800 元时提醒我',
          icon: <BellRing className="h-4 w-4" />,
        },
  ]

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className={`flex items-center justify-between ${compact ? 'px-5 pt-[max(1.25rem,env(safe-area-inset-top))]' : 'px-5 pt-6 sm:px-8 lg:px-12 lg:pt-8'}`}>
        <div>
          {compact ? <div className="text-[10px] font-black tracking-[0.2em] text-brand-orange">特价机票发现</div> : null}
          <h1 className={`font-bold text-brand-text ${compact ? 'mt-1 font-serif text-[2rem] leading-tight' : 'text-3xl sm:text-4xl'}`}>对话空间</h1>
        </div>
        {compact ? (
          <div className="flex items-center gap-1.5 rounded-full bg-white px-3 py-2 text-[11px] font-bold text-brand-muted shadow-sm">
            <MessageCircle className="h-3.5 w-3.5" />
            当前对话
          </div>
        ) : (
          <button className="flex items-center gap-2 text-sm text-brand-muted transition hover:text-brand-text">
            <History className="h-4 w-4" />
            历史对话
          </button>
        )}
      </div>

      <div
        className={`thin-scrollbar flex-1 overflow-y-auto ${compact ? 'px-5 py-5' : 'px-5 py-8 sm:px-8 lg:px-[12vw] lg:py-12'} ${
          messages.length === 0 ? 'flex flex-col justify-center' : 'space-y-8'
        }`}
      >
        {messages.length === 0 ? (
          compact ? (
            <div className="flex min-h-full flex-col justify-center">
              <div className="flex items-center gap-2 text-[11px] font-black text-brand-orange">
                <span className="grid h-7 w-7 place-items-center rounded-xl bg-brand-orange-light"><Sparkles className="h-3.5 w-3.5" /></span>
                {assistantName} 在这里
              </div>
              <motion.h2 className="mt-3 font-serif text-[2rem] font-black leading-tight text-brand-text">先说一个想法就好</motion.h2>
              <p className="mt-2 text-[13px] leading-6 text-brand-muted">不必一次把条件说全。我会接着当前对话，只追问真正缺少的内容。</p>

              <div className="mt-5 space-y-2.5">
                {compactStarters.map((starter) => (
                  <button
                    key={starter.title}
                    type="button"
                    onClick={() => starter.prompt ? setInputValue(starter.prompt) : onOpenExplore?.()}
                    className="flex w-full items-center gap-3 rounded-[20px] border border-brand-text/7 bg-white px-4 py-3 text-left shadow-sm transition active:scale-[0.99]"
                  >
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-2xl bg-brand-orange-light text-brand-orange">{starter.icon}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-black text-brand-text">{starter.title}</span>
                      <span className="mt-0.5 block truncate text-[11px] text-brand-muted">{starter.detail}</span>
                    </span>
                    <span className="text-lg text-brand-muted/60">›</span>
                  </button>
                ))}
              </div>

              <div className="mt-4 flex items-center gap-2 text-[10px] font-semibold leading-5 text-brand-muted">
                <span className="h-px flex-1 bg-brand-text/8" />
                查询后再比较真实报价
                <span className="h-px flex-1 bg-brand-text/8" />
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center">
              <motion.div className="mb-5 grid h-16 w-16 place-items-center rounded-[26px] bg-brand-orange-light text-brand-orange">
                <Plane className="h-7 w-7" />
              </motion.div>
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
          )
        ) : (
          messages.map((message) => (
            <motion.div key={message.id} className={`flex flex-col ${message.role === 'user' ? 'items-end' : 'items-start'}`}>
              <div
                className={`max-w-3xl rounded-[28px] text-sm ${compact ? 'p-4' : 'p-5 sm:text-base'} ${
                  message.role === 'user' ? 'rounded-tr-none bg-brand-text text-white' : 'rounded-tl-none border border-brand-text/5 bg-white shadow-sm'
                }`}
              >
                {'isSpecial' in message && message.isSpecial ? (
                  <div className="flex items-center gap-2 font-bold text-brand-orange">
                    <Radar className="h-4 w-4 animate-spin" />
                    <span>{message.content}</span>
                  </div>
                ) : message.role === 'assistant' ? (
                  <MarkdownMessage content={message.content} compact={compact} />
                ) : (
                  message.content
                )}
                {message.role === 'assistant' && message.retryQuery ? (
                  <button
                    type="button"
                    onClick={() => void startSearch(message.retryQuery as string)}
                    className="mt-3 inline-flex items-center gap-2 rounded-xl bg-brand-orange-light px-3 py-2 text-xs font-black text-brand-orange"
                  >
                    <Radar className="h-3.5 w-3.5" />
                    重新查询
                  </button>
                ) : null}
              </div>

              {'hasCard' in message && message.hasCard && message.cardData ? (
                <div className="mt-4 w-full max-w-2xl overflow-hidden rounded-[28px] border border-brand-text/5 bg-white shadow-card">
                  <DiscoveryCardContent {...message.cardData} compact={compact || message.cardData.compact} narrow={compact} />
                </div>
              ) : null}
            </motion.div>
          ))
        )}
      </div>

      <div className={`${compact ? 'px-4 pb-3 pt-2' : `px-5 pb-6 pt-2 sm:px-8 lg:px-[12vw] ${messages.length === 0 ? 'lg:pb-12' : 'lg:pb-8'}`}`}>
        <div className="flex items-center rounded-[28px] border border-brand-text/5 bg-white p-2 shadow-card">
          <input
            type="text"
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            onKeyDown={(event) => event.key === 'Enter' && handleSend()}
            placeholder={compact ? '说出发地、目的地和时间…' : '比如：五一去三亚，预算 600...'}
            className={`min-w-0 flex-1 bg-transparent px-4 py-3 text-sm ${compact ? '' : 'sm:text-base'}`}
          />
          <motion.button
            type="button"
            aria-label="发送消息"
            onClick={handleSend}
            whileTap={{ scale: 0.96 }}
            className="rounded-2xl bg-brand-text p-3 text-white transition hover:bg-brand-orange"
          >
            <Send className="h-5 w-5" />
          </motion.button>
        </div>

        {messages.length === 0 && !compact ? (
          <div className={`mt-3 flex items-center gap-2 overflow-x-auto pb-1 ${compact ? 'justify-start' : 'flex-wrap justify-center'}`}>
            {recommendedQuestions.slice(0, compact ? 3 : recommendedQuestions.length).map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => setInputValue(tag)}
                className={`shrink-0 rounded-full border border-brand-text/5 px-4 py-2 text-xs text-brand-muted transition hover:bg-white hover:text-brand-orange ${compact ? '' : 'sm:text-sm'}`}
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
