'use client'

import React from 'react'
import { motion } from 'motion/react'
import { BellRing, Compass, History, MessageCircle, Plane, Radar, Send, Sparkles } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeSanitize from 'rehype-sanitize'
import { DiscoveryCardContent } from '@/components/discovery-card-content'
import { RecommendationCard } from '@/components/shared-components'
import { alertsApi, recApi, searchApi } from '@/lib/api'
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
  const mobileFlights = compact ? parseMobileFlightResults(content) : null

  if (mobileFlights) return <MobileFlightResults result={mobileFlights} />

  return (
    <>
      {compact && hasTable ? (
        <div className="mb-1.5 flex items-center gap-2 text-[9px] font-bold text-brand-orange">
          <span className="h-px flex-1 bg-brand-orange/20" />
          航班列表可左右滑动
          <span className="h-px flex-1 bg-brand-orange/20" />
        </div>
      ) : null}
      <div className={`prose prose-sm max-w-none break-words ${compact ? '[&_h1]:text-sm [&_h2]:text-[13px] [&_h3]:text-xs [&_li]:text-[11px] [&_li]:leading-[1.55] [&_p]:text-[11px] [&_p]:leading-[1.6] [&_strong]:text-[11px] [&_table]:text-[10px] [&_td]:py-1 [&_th]:py-1' : ''} prose-headings:my-2 prose-p:my-1.5 prose-table:my-2 prose-th:px-2 prose-td:px-2 prose-li:my-0.5 prose-pre:my-2 ${compact && hasTable ? 'overflow-x-auto overscroll-x-contain [&_table]:min-w-[29rem] [&_th]:whitespace-nowrap [&_td]:whitespace-nowrap' : ''}`}>
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
          {content}
        </ReactMarkdown>
      </div>
    </>
  )
}

type MobileFlightResult = {
  rows: Array<{ flight: string; platform: string; depart: string; arrive: string; price: string }>
  lowestPrice: string | null
}

function markdownCells(line: string) {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim().replace(/\*\*/g, ''))
}

function parseMobileFlightResults(content: string): MobileFlightResult | null {
  const lines = content.split('\n')
  const dividerIndex = lines.findIndex((line) => /^\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*$/.test(line))
  if (dividerIndex < 1) return null

  const headers = markdownCells(lines[dividerIndex - 1])
  const indexes = {
    flight: headers.indexOf('航班'),
    platform: headers.indexOf('平台'),
    depart: headers.indexOf('出发'),
    arrive: headers.indexOf('到达'),
    price: headers.findIndex((header) => header.includes('价')),
  }
  if (Object.values(indexes).some((index) => index < 0)) return null

  const rows: MobileFlightResult['rows'] = []
  for (const line of lines.slice(dividerIndex + 1)) {
    if (!/^\s*\|.+\|\s*$/.test(line)) break
    const cells = markdownCells(line)
    rows.push({
      flight: cells[indexes.flight] ?? '待确认',
      platform: cells[indexes.platform] ?? '来源待确认',
      depart: cells[indexes.depart] ?? '--:--',
      arrive: cells[indexes.arrive] ?? '--:--',
      price: cells[indexes.price] ?? '待确认',
    })
  }
  if (!rows.length) return null

  const lowestPrice = content.match(/平台展示价最低[:：]\s*([^\s（(。]+)/)?.[1]?.replace(/\*\*/g, '') ?? null
  return { rows, lowestPrice }
}

function MobileFlightResults({ result }: { result: MobileFlightResult }) {
  const [expanded, setExpanded] = React.useState(false)
  const visibleRows = expanded ? result.rows : result.rows.slice(0, 4)
  const hiddenCount = result.rows.length - visibleRows.length

  return (
    <section aria-label="手机端航班结果" className="w-full">
      <div className="flex items-end justify-between gap-3">
        <div>
          <div className="text-[9px] font-black tracking-[0.14em] text-brand-orange">真实来源结果</div>
          <h3 className="mt-1 text-[13px] font-black text-brand-text">找到 {result.rows.length} 个航班</h3>
        </div>
        {result.lowestPrice ? <div className="text-right"><div className="text-[8px] font-bold text-brand-muted">最低展示价</div><div className="text-sm font-black text-brand-orange">{result.lowestPrice}</div></div> : null}
      </div>

      <div role="list" className="mt-2 divide-y divide-brand-text/7 overflow-hidden rounded-2xl border border-brand-text/7 bg-brand-bg/35">
        {visibleRows.map((row, index) => (
          <div role="listitem" key={`${row.flight}-${row.platform}-${index}`} className="flex items-center justify-between gap-3 px-3 py-2.5">
            <div className="min-w-0">
              <div className="truncate text-[11px] font-black text-brand-text">{row.flight}</div>
              <div className="mt-0.5 text-[9px] font-bold text-brand-muted">{row.platform}</div>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <div className="text-right text-[9px] leading-4 text-brand-muted"><span className="font-bold text-brand-text">{row.depart}</span><span className="mx-1">→</span><span>{row.arrive}</span></div>
              <div className="w-12 text-right text-[11px] font-black text-brand-orange">{row.price}</div>
            </div>
          </div>
        ))}
      </div>

      {result.rows.length > 4 ? (
        <button type="button" onClick={() => setExpanded((value) => !value)} className="mt-2 h-8 w-full rounded-xl bg-brand-orange-light text-[10px] font-black text-brand-orange">
          {expanded ? '收起航班列表' : `查看其余 ${hiddenCount} 个航班`}
        </button>
      ) : null}
      <p className="mt-2 text-[9px] leading-4 text-brand-muted">已按平台展示价排序；点击下方推荐卡查看当前最优结果详情。</p>
    </section>
  )
}

export function ChatPage({
  initialQuery,
  onInitialQueryConsumed,
  compact = false,
  assistantName = '旅伴',
  recentQuery,
  onOpenExplore,
  onAlertCreated,
}: {
  initialQuery?: string | null
  onInitialQueryConsumed?: () => void
  compact?: boolean
  assistantName?: string
  recentQuery?: string | null
  onOpenExplore?: () => void
  onAlertCreated?: () => void
}) {
  const [messages, setMessages] = React.useState<Message[]>([])
  const [inputValue, setInputValue] = React.useState('')
  const [sessionId, setSessionId] = React.useState<string | null>(null)
  const [recommendedQuestions, setRecommendedQuestions] = React.useState<string[]>([])
  const [alertCard, setAlertCard] = React.useState<DiscoveryCardContentProps | null>(null)
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
    <div className="relative flex h-full flex-col overflow-hidden">
      <div className={`flex items-center justify-between ${compact ? 'px-5 pt-[max(1.25rem,env(safe-area-inset-top))]' : 'px-5 pt-6 sm:px-8 lg:px-12 lg:pt-8'}`}>
        <div>
          {compact ? <div className="text-[9px] font-black tracking-[0.12em] text-brand-orange">你的机票发现与出行陪伴 Agent</div> : null}
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
          messages.length === 0 ? 'flex flex-col justify-center' : compact ? 'space-y-4' : 'space-y-8'
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
                className={`max-w-3xl rounded-[28px] ${compact ? 'p-3 text-[12px] leading-5' : 'p-5 text-sm sm:text-base'} ${
                  message.role === 'user' ? 'rounded-tr-none bg-brand-text text-white' : 'rounded-tl-none border border-brand-text/5 bg-white shadow-sm'
                }`}
              >
                {'isSpecial' in message && message.isSpecial ? (
                  <div className={`flex items-center font-bold text-brand-orange ${compact ? 'gap-1.5 text-[11px]' : 'gap-2'}`}>
                    <Radar className={`${compact ? 'h-3.5 w-3.5' : 'h-4 w-4'} animate-spin`} />
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
                    className={`${compact ? 'mt-2 gap-1.5 px-2.5 py-1.5 text-[10px]' : 'mt-3 gap-2 px-3 py-2 text-xs'} inline-flex items-center rounded-xl bg-brand-orange-light font-black text-brand-orange`}
                  >
                    <Radar className="h-3.5 w-3.5" />
                    重新查询
                  </button>
                ) : null}
              </div>

              {'hasCard' in message && message.hasCard && message.cardData ? (
                <div className={`${compact ? 'mt-3' : 'mt-4'} w-full max-w-2xl`}>
                  {compact ? <div className="mb-1.5 px-1 text-[9px] font-black tracking-[0.12em] text-brand-orange">当前最优结果详情</div> : null}
                  <div className="overflow-hidden rounded-[28px] border border-brand-text/5 bg-white shadow-card">
                    <DiscoveryCardContent
                      {...message.cardData}
                      compact={compact || message.cardData.compact}
                      narrow={compact}
                      onMonitorPrice={() => setAlertCard(message.cardData ?? null)}
                    />
                  </div>
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

      {alertCard ? (
        <PriceAlertDialog
          card={alertCard}
          compact={compact}
          onClose={() => setAlertCard(null)}
          onCreated={onAlertCreated}
        />
      ) : null}
    </div>
  )
}

function PriceAlertDialog({
  card,
  compact,
  onClose,
  onCreated,
}: {
  card: DiscoveryCardContentProps
  compact: boolean
  onClose: () => void
  onCreated?: () => void
}) {
  const currentPrice = card.totalPrice ?? card.basePrice ?? null
  const [targetPrice, setTargetPrice] = React.useState(currentPrice ? String(Math.round(currentPrice)) : '')
  const [state, setState] = React.useState<'idle' | 'saving' | 'success'>('idle')
  const [error, setError] = React.useState('')

  const createAlert = async () => {
    const target = Number(targetPrice)
    if (!card.date) {
      setError('这条航班缺少出发日期，暂时不能创建提醒。')
      return
    }
    if (card.currency !== 'CNY') {
      setError('当前价格提醒先支持人民币报价。')
      return
    }
    if (!Number.isInteger(target) || target <= 0) {
      setError('请输入正确的目标价格。')
      return
    }

    setState('saving')
    setError('')
    try {
      await alertsApi.create({
        origin: card.originCode ?? card.from,
        destination: card.destinationCode ?? card.to,
        depart_date: card.date,
        target_price: target,
      })
      setState('success')
      onCreated?.()
    } catch {
      setState('idle')
      setError('提醒没有保存成功，请稍后再试。')
    }
  }

  return (
    <div className="absolute inset-0 z-50 flex items-end justify-center bg-brand-text/30 p-3 backdrop-blur-sm sm:items-center sm:p-6" role="dialog" aria-modal="true" aria-label="创建价格提醒">
      <section className={`w-full max-w-md rounded-[28px] bg-white shadow-card ${compact ? 'p-4' : 'p-6'}`}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-[10px] font-black tracking-[0.16em] text-brand-orange">接入后端价格监控</div>
            <h2 className="mt-1 text-xl font-black text-brand-text">{card.from} → {card.to}</h2>
            <p className="mt-1 text-xs text-brand-muted">{card.date ?? '日期待确认'} · 当前展示 {formatCurrency(currentPrice, card.currency)}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="关闭价格提醒" className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-brand-bg text-brand-muted">×</button>
        </div>

        {state === 'success' ? (
          <div className="mt-5 rounded-2xl bg-emerald-50 px-4 py-5 text-center">
            <div className="text-base font-black text-emerald-800">提醒已经保存到你的账号</div>
            <p className="mt-1 text-xs leading-5 text-emerald-700">Mobile 与网页端都会读取到这条提醒。</p>
            <button type="button" onClick={onClose} className="mt-4 h-10 w-full rounded-xl bg-brand-text text-xs font-black text-white">完成</button>
          </div>
        ) : (
          <>
            <label htmlFor="alert-target-price" className="mt-5 block text-xs font-black text-brand-text">目标价格（人民币）</label>
            <div className="mt-2 flex h-12 items-center rounded-xl border border-brand-text/10 bg-brand-bg px-3">
              <span className="text-sm font-black text-brand-muted">¥</span>
              <input id="alert-target-price" value={targetPrice} onChange={(event) => setTargetPrice(event.target.value)} inputMode="numeric" className="min-w-0 flex-1 bg-transparent px-2 text-base font-black text-brand-text" />
            </div>
            <p className="mt-2 text-[11px] leading-5 text-brand-muted">后端会按这条航线和日期持续检查，达到目标价后触发提醒。</p>
            {error ? <p className="mt-3 text-xs font-bold text-red-700">{error}</p> : null}
            <button type="button" disabled={state === 'saving'} onClick={() => void createAlert()} className="mt-4 h-11 w-full rounded-xl bg-brand-orange text-sm font-black text-white disabled:opacity-45">{state === 'saving' ? '正在保存…' : '创建价格提醒'}</button>
          </>
        )}
      </section>
    </div>
  )
}
