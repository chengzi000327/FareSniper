'use client'

import React from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Gift, MapPin, Plane, Sparkles, TrendingDown, X } from 'lucide-react'
import { DiscoveryCardContent } from '@/components/discovery-card-content'
import { recApi } from '@/lib/api'
import { EventName, track } from '@/lib/analytics'
import { dealToCardProps } from '@/lib/mappers'
import { formatCurrency } from '@/lib/currency'
import type { RecCardDto } from '@/lib/api'
import type { DiscoveryCardContentProps } from '@/components/discovery-card-content'

const PAGE_SIZE = 6

// 本地目的地图片映射（未匹配则用渐变占位）
const DEST_IMAGES: Record<string, string> = {
  SHA: '/images/destinations/SHA.jpg',
  SYX: '/images/destinations/SYX.jpg',
  CTU: '/images/destinations/CTU.jpg',
  CAN: '/images/destinations/CAN.jpg',
  XMN: '/images/destinations/XMN.jpg',
}
const DEST_CODES_BY_CITY: Record<string, string> = {
  上海: 'SHA',
  三亚: 'SYX',
  成都: 'CTU',
  广州: 'CAN',
  厦门: 'XMN',
}

type Deal = {
  id: string
  from: string
  to: string
  destCode: string
  price: string
  date: string
  reason: string
  tags: string[]
  discountPct: number | null
  image: string
  cardData: DiscoveryCardContentProps
  queryHint: string
  flightNo: string
  airline: string
  platform: string
  numericPrice: number | null
  hasPricePreview: boolean
}

function mapCard(c: RecCardDto): Deal | null {
  if (!c.preview_deal) {
    const [from, to, ...extra] = (c.title ?? '')
      .split('→')
      .map((part) => part.trim())
    const queryHint = c.query_hint?.trim() ?? ''
    if (!from || !to || extra.length > 0 || !queryHint) return null
    const destCode = DEST_CODES_BY_CITY[to] ?? to
    return {
      id: c.id ?? `route-${from}-${to}`,
      from,
      to,
      destCode,
      price: '实时查询',
      date: '',
      reason: c.reason ?? '进入对话获取最新航班与平台报价。',
      tags: c.tags ?? [],
      discountPct: null,
      image:
        DEST_IMAGES[destCode] ??
        `https://picsum.photos/seed/${encodeURIComponent(destCode)}/800/560`,
      cardData: {
        from,
        to,
        basePrice: null,
        totalPrice: null,
        tax: null,
        baggageFee: null,
        hasBaggage: null,
        currency: 'CNY',
        platform: '',
        prices: [],
        placeholder: true,
      },
      queryHint,
      flightNo: '',
      airline: '',
      platform: '',
      numericPrice: null,
      hasPricePreview: false,
    }
  }
  const deal = c.preview_deal
  const destCode = (deal.destination_code as string) ?? ''
  return {
    id: (c.id as string) ?? deal.system_id,
    from: deal.origin_city,
    to: deal.destination_city,
    destCode,
    price: formatCurrency(deal.price, deal.currency),
    date: deal.depart_date,
    reason: c.reason ?? '',
    tags: (c.tags as string[]) ?? [],
    discountPct: (c.discount_pct as number) ?? null,
    image: DEST_IMAGES[destCode] ?? `https://picsum.photos/seed/${destCode}/800/560`,
    cardData: dealToCardProps(deal),
    queryHint: c.query_hint || `${deal.depart_date} 从${deal.origin_city}到${deal.destination_city}的机票`,
    flightNo: deal.flight_no,
    airline: deal.airline,
    platform: deal.platform,
    numericPrice: deal.total_price,
    hasPricePreview: true,
  }
}

export function ExplorePage({ onSearch }: { onSearch?: (query: string) => void }) {
  const [deals, setDeals] = React.useState<Deal[]>([])
  const [loading, setLoading] = React.useState(true)
  const [loadingMore, setLoadingMore] = React.useState(false)
  const [departure, setDeparture] = React.useState('')
  const [selectedDeal, setSelectedDeal] = React.useState<Deal | null>(null)
  const [isDrawing, setIsDrawing] = React.useState(false)
  const [personalized, setPersonalized] = React.useState(false)
  const [hasMore, setHasMore] = React.useState(false)
  const [nextOffset, setNextOffset] = React.useState(0)

  const sentinelRef = React.useRef<HTMLDivElement | null>(null)
  // 用 ref 镜像分页状态,避免 IntersectionObserver 回调闭包读到旧值
  const stateRef = React.useRef({ hasMore: false, loadingMore: false, nextOffset: 0 })
  stateRef.current = { hasMore, loadingMore, nextOffset }

  const loadPage = React.useCallback(async (initialOffset: number) => {
    let offset = initialOffset
    let mapped: Deal[] = []
    let personalized = false
    let hasMore = false
    let nextOffset = initialOffset
    const visitedOffsets = new Set<number>()

    while (!visitedOffsets.has(offset)) {
      visitedOffsets.add(offset)
      const resp = await recApi.list({ limit: PAGE_SIZE, offset })
      personalized = resp.personalized ?? false
      hasMore = resp.has_more ?? false
      nextOffset = resp.next_offset ?? offset + PAGE_SIZE
      mapped = [
        ...mapped,
        ...resp.cards.map(mapCard).filter((deal): deal is Deal => deal !== null),
      ]
      if (mapped.length > 0 || !hasMore || nextOffset <= offset) break
      offset = nextOffset
    }

    setPersonalized(personalized)
    setHasMore(hasMore)
    setNextOffset(nextOffset)
    setDeals((prev) => {
      if (initialOffset === 0) return mapped
      const seen = new Set(prev.map((d) => d.id))
      return [...prev, ...mapped.filter((d) => !seen.has(d.id))]
    })
  }, [])

  // 首屏加载
  React.useEffect(() => {
    loadPage(0)
      .catch(() => {/* keep empty */})
      .finally(() => setLoading(false))
  }, [loadPage])

  // 触底无限滚动:IntersectionObserver 监听 sentinel 进入视口即追加下一页
  React.useEffect(() => {
    const node = sentinelRef.current
    if (!node || typeof IntersectionObserver === 'undefined') return
    const observer = new IntersectionObserver(
      (entries) => {
        const { hasMore: more, loadingMore: busy, nextOffset: off } = stateRef.current
        if (entries[0].isIntersecting && more && !busy) {
          setLoadingMore(true)
          loadPage(off)
            .catch(() => {/* keep prev */})
            .finally(() => setLoadingMore(false))
        }
      },
      { rootMargin: '200px' }
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [hasMore, loadPage, loading])

  const loadMore = () => {
    const { hasMore: more, loadingMore: busy, nextOffset: off } = stateRef.current
    if (!more || busy) return
    setLoadingMore(true)
    loadPage(off)
      .catch(() => {/* keep prev */})
      .finally(() => setLoadingMore(false))
  }

  const visibleDeals = deals.filter((deal) => !departure || deal.from.includes(departure) || deal.to.includes(departure))

  const handleDrawBlindBox = () => {
    setIsDrawing(true)
    window.setTimeout(() => {
      const pool = visibleDeals.length ? visibleDeals : deals
      if (pool.length > 0) {
        setSelectedDeal(pool[Math.floor(Math.random() * pool.length)])
      }
      setIsDrawing(false)
    }, 1400)
  }

  const selectDeal = (deal: Deal) => {
    setSelectedDeal(deal)
    if (!deal.flightNo) return
    void track(EventName.TicketClicked, {
      flight_no: deal.flightNo,
      platform: deal.platform,
      price: deal.numericPrice,
      signals: deal.tags,
      airline: deal.airline,
      origin: deal.from,
      destination: deal.to,
      depart_date: deal.date,
    }).catch(() => undefined)
  }

  const searchSelectedDeal = () => {
    if (!selectedDeal || !onSearch) return
    const query = selectedDeal.queryHint
    setSelectedDeal(null)
    onSearch(query)
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 px-5 pt-6 sm:px-8 lg:flex-row lg:items-center lg:justify-between lg:px-12 lg:pt-8">
        <div>
          <h1 className="text-3xl font-bold text-brand-text sm:text-4xl">探索发现</h1>
          {personalized && (
            <div className="mt-1 flex items-center gap-1.5 text-xs text-brand-orange">
              <Sparkles className="h-3.5 w-3.5" />
              <span>已根据你的偏好个性化排序</span>
            </div>
          )}
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="relative">
            <MapPin className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-muted" />
            <input
              type="text"
              placeholder="搜索出发地或目的地"
              value={departure}
              onChange={(e) => setDeparture(e.target.value)}
              className="w-full rounded-2xl border border-brand-text/10 bg-white py-3 pl-11 pr-4 text-sm transition focus:border-brand-orange sm:w-64"
            />
          </div>
          <button
            type="button"
            onClick={handleDrawBlindBox}
            disabled={isDrawing || deals.length === 0}
            className="flex items-center justify-center gap-2 rounded-2xl bg-brand-text px-5 py-3 text-sm font-bold text-white transition hover:bg-brand-orange disabled:opacity-60"
          >
            <motion.div
              animate={isDrawing ? { rotate: 360 } : { rotate: 0 }}
              transition={isDrawing ? { repeat: Infinity, duration: 1, ease: 'linear' } : undefined}
            >
              <Gift className="h-4 w-4" />
            </motion.div>
            {isDrawing ? '抽取中...' : '盲盒抽目的地'}
          </button>
        </div>
      </div>

      {/* Card grid */}
      <div className="thin-scrollbar flex-1 overflow-y-auto px-5 pb-8 sm:px-8 lg:px-12">
        {loading ? (
          <div className="columns-1 gap-5 space-y-5 md:columns-2 xl:columns-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="mb-5 h-96 animate-pulse break-inside-avoid rounded-[28px] bg-white/60" />
            ))}
          </div>
        ) : visibleDeals.length === 0 ? (
          <div className="flex h-48 items-center justify-center rounded-[28px] border border-dashed border-brand-text/10 text-brand-muted">
            {deals.length === 0 ? '暂无推荐，请稍后重试' : '没有匹配的城市'}
          </div>
        ) : (
          <>
            <div className="columns-1 gap-5 space-y-5 md:columns-2 xl:columns-3">
              {visibleDeals.map((deal) => (
                <DealCard key={deal.id} deal={deal} onSelect={() => selectDeal(deal)} />
              ))}
            </div>
            {/* 无限滚动 sentinel + 加载态 */}
            {!departure && hasMore && (
              <div ref={sentinelRef} className="flex h-20 items-center justify-center">
                {loadingMore ? (
                  <div className="flex items-center gap-2 text-sm text-brand-muted">
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-brand-orange border-t-transparent" />
                    加载更多...
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={loadMore}
                    className="rounded-2xl border border-brand-text/10 bg-white px-5 py-2.5 text-sm font-bold text-brand-text transition hover:border-brand-orange hover:text-brand-orange"
                  >
                    加载更多目的地
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Detail modal */}
      <AnimatePresence>
        {selectedDeal ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-brand-text/25 p-4 backdrop-blur-sm"
            onClick={() => setSelectedDeal(null)}
          >
            <motion.div
              initial={{ scale: 0.92, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.92, opacity: 0 }}
              className="relative w-full max-w-2xl overflow-hidden rounded-[32px] bg-white shadow-[0_32px_120px_-32px_rgba(67,44,27,0.4)]"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                type="button"
                onClick={() => setSelectedDeal(null)}
                className="absolute right-4 top-4 z-10 rounded-full bg-white/90 p-2 transition hover:bg-white"
              >
                <X className="h-5 w-5 text-brand-text" />
              </button>
              <DiscoveryCardContent
                {...selectedDeal.cardData}
                onSearch={onSearch ? searchSelectedDeal : undefined}
              />
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  )
}

// ── 单张卡片 ──────────────────────────────────────────────────────────────────

function DealCard({ deal, onSelect }: { deal: Deal; onSelect: () => void }) {
  return (
    <motion.div
      whileHover={{ y: -4 }}
      className="mb-5 break-inside-avoid overflow-hidden rounded-[28px] border border-brand-text/5 bg-white shadow-sm"
    >
      {/* 目的地图片 */}
      <div className="relative overflow-hidden">
        <img
          src={deal.image}
          alt={deal.to}
          className="h-52 w-full object-cover transition-transform duration-500 hover:scale-105"
          referrerPolicy="no-referrer"
        />
        {/* 折扣徽章 */}
        {deal.discountPct !== null && deal.discountPct >= 5 && (
          <div className="absolute left-4 top-4 flex items-center gap-1 rounded-full bg-brand-orange px-3 py-1 text-xs font-bold text-white shadow">
            <TrendingDown className="h-3 w-3" />
            比均价低 {deal.discountPct}%
          </div>
        )}
        {/* 城市名渐变叠加 */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent px-5 pb-4 pt-8">
          <div className="flex items-center gap-2">
            <Plane className="h-4 w-4 text-white/80" />
            <span className="text-lg font-bold text-white">
              {deal.from} → {deal.to}
            </span>
          </div>
        </div>
      </div>

      {/* 卡片内容 */}
      <div className="p-5">
        {/* 标签 */}
        {deal.tags.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-1.5">
            {deal.tags.map((tag) => (
              <span
                key={tag}
                className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  tag === '符合偏好'
                    ? 'bg-brand-orange/10 text-brand-orange'
                    : 'bg-brand-bg text-brand-muted'
                }`}
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* 价格 */}
        <div className="mb-1 flex items-baseline gap-2">
          <span className="text-3xl font-black text-brand-text">{deal.price}</span>
          <span className="text-sm text-brand-muted">
            {deal.hasPricePreview ? `起 · ${deal.date}` : '点击获取最新报价'}
          </span>
        </div>

        {/* 推荐理由 */}
        <p className="mb-4 text-sm leading-6 text-brand-muted">{deal.reason}</p>

        <button
          type="button"
          onClick={onSelect}
          className="w-full rounded-2xl bg-brand-bg px-4 py-3 text-sm font-bold text-brand-text transition hover:bg-brand-text hover:text-white"
        >
          {deal.hasPricePreview ? '查看详情' : '查询实时价格'}
        </button>
      </div>
    </motion.div>
  )
}
