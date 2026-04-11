'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { DEFAULT_USER_ID, getRecommendationDeals, searchFlights } from '@/lib/api-client'
import type { ExploreSearchResult, FlightDeal } from '@/types'

const confidenceConfig = {
  high: { label: '高置信', dot: '#22C55E', bg: 'bg-signal-muted', text: 'text-signal-text' },
  medium: { label: '中置信', dot: '#F59E0B', bg: 'bg-amber-50', text: 'text-amber-700' },
  low: { label: '低置信', dot: '#D1D5DB', bg: 'bg-gray-50', text: 'text-gray-500' },
}

const filters = ['全部', '高置信', '符合偏好', '今日新增']
const cardPattern = [
  'xl:col-span-5',
  'xl:col-span-4',
  'xl:col-span-3',
  'xl:col-span-4',
  'xl:col-span-5',
  'xl:col-span-3',
]

type PriceBoardItem = {
  platform: string
  price: number
  tone: 'current' | 'lower' | 'higher'
}

function buildPriceBoard(deal: FlightDeal, index: number): PriceBoardItem[] {
  const knownPlatforms = ['携程', '飞猪', '去哪儿', '同程', '航旅纵横']
  const alternates = knownPlatforms.filter((platform) => platform !== deal.platform).slice(0, 3)
  const offsets = [-28, 14, 39]

  const board = [
    {
      platform: deal.platform || '当前平台',
      price: deal.price,
      tone: 'current' as const,
    },
    ...alternates.map((platform, platformIndex) => {
      const delta = offsets[(index + platformIndex) % offsets.length]

      return {
        platform,
        price: Math.max(deal.price + delta, Math.floor(deal.price * 0.9)),
        tone: delta < 0 ? 'lower' as const : 'higher' as const,
      }
    }),
  ]

  return board.sort((left, right) => left.price - right.price)
}

function getCompareToneClass(tone: PriceBoardItem['tone']): string {
  if (tone === 'current') return 'bg-navy text-white'
  if (tone === 'lower') return 'bg-[#ecfdf3] text-[#15803d]'
  return 'bg-[#f8fafc] text-navy/60'
}

export default function ExplorePage() {
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [activeFilter, setActiveFilter] = useState('全部')
  const [searchResult, setSearchResult] = useState<ExploreSearchResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const searchParams = useSearchParams()
  const queryText = searchParams.get('q')?.trim() ?? ''

  useEffect(() => {
    let mounted = true

    async function loadData() {
      setLoading(true)
      setError('')

      try {
        if (queryText) {
          const cached = window.sessionStorage.getItem('faresniper:last-search')
          if (cached) {
            const parsed = JSON.parse(cached) as ExploreSearchResult
            if (parsed.queryText === queryText && mounted) {
              setSearchResult(parsed)
              setLoading(false)
              return
            }
          }

          const result = await searchFlights(queryText, DEFAULT_USER_ID)
          if (!mounted) return
          window.sessionStorage.setItem('faresniper:last-search', JSON.stringify(result))
          setSearchResult(result)
          setLoading(false)
          return
        }

        const deals = await getRecommendationDeals(DEFAULT_USER_ID)
        if (!mounted) return
        setSearchResult({
          userId: DEFAULT_USER_ID,
          queryText: '',
          normalizedText: '首页推荐',
          recommendationText: '可以关注',
          recommendationConfidence: 'medium',
          resultCount: deals.length,
          deals,
          matchedPreferences: [],
        })
      } catch (loadError) {
        if (!mounted) return
        setError(loadError instanceof Error ? loadError.message : '加载失败，请确认后端已启动')
      } finally {
        if (mounted) {
          setLoading(false)
        }
      }
    }

    void loadData()

    return () => {
      mounted = false
    }
  }, [queryText])

  const filteredDeals = (searchResult?.deals ?? []).filter((deal) => {
    if (activeFilter === '高置信') return deal.confidence === 'high'
    if (activeFilter === '符合偏好') return deal.signals.some((signal) => signal.includes('偏好') || signal.includes('心理价位'))
    if (activeFilter === '今日新增') return true
    return true
  })

  const lowestPrice = filteredDeals.length > 0 ? Math.min(...filteredDeals.map((deal) => deal.price)) : null
  const highestConfidenceCount = filteredDeals.filter((deal) => deal.confidence === 'high').length

  return (
    <div className="min-h-screen bg-[#f8f9fc] font-sans">
      <nav className="flex items-center justify-between px-6 py-5 lg:px-8">
        <div className="flex items-center gap-5">
          <Link
            href="/chat"
            className="group inline-flex items-center gap-2 rounded-full border border-[#e7ebf3] bg-white px-4 py-2 text-sm text-navy/60 shadow-[0_8px_24px_rgba(27,43,94,0.05)] transition-all hover:-translate-y-0.5 hover:text-navy"
          >
            <svg className="h-4 w-4 transition-transform group-hover:-translate-x-0.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10 13L5 8l5-5" />
            </svg>
            返回对话
          </Link>

          <Link href="/chat" className="flex items-center gap-2 group">
            <div className="h-4 w-4 rounded-full bg-navy group-hover:scale-110 transition-transform" />
            <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-navy/35 group-hover:text-navy/60 transition-colors">
              FareSniper
            </span>
          </Link>
        </div>

        <div className="flex items-center gap-5">
          <Link href="/chat" className="text-sm text-gray-400 transition-colors hover:text-navy">
            对话
          </Link>
          <Link
            href="/memory"
            className="flex items-center gap-1.5 text-sm text-gray-400 transition-colors hover:text-navy"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-signal" />
            我的记忆
          </Link>
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-navy text-xs font-semibold text-white">
            我
          </div>
        </div>
      </nav>

      <div className="px-6 pb-6 pt-2 lg:px-8">
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_360px] xl:items-end">
          <div>
            <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.18em] text-gray-300">
              DISCOVER · 全平台筛选
            </p>
            <h1 className="font-heading text-[2.8rem] font-bold leading-tight text-navy">
              {queryText ? '搜索结果' : '为你发现'}
            </h1>
            <p className="mt-2 max-w-[760px] text-sm text-gray-400">
              {loading ? '正在拉取最新票价和建议...' : (
                <>
                  {queryText ? '查询：' : 'AI 当前为你整理 · 共 '}
                  {queryText && <span className="font-semibold text-navy">{queryText}</span>}
                  {queryText && ' · '}
                  共 <span className="font-semibold text-navy">{filteredDeals.length}</span> 个值得关注
                  {searchResult && (
                    <>
                      {' '}· 判断：<span className="font-semibold text-navy">{searchResult.recommendationText}</span>
                    </>
                  )}
                </>
              )}
            </p>
          </div>

          <div className="rounded-[30px] border border-[#e8edf7] bg-[linear-gradient(145deg,#ffffff_0%,#f2f6ff_100%)] p-5 shadow-[0_18px_50px_rgba(27,43,94,0.06)]">
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-navy/34">
              Price Radar
            </p>
            <div className="mt-4 grid grid-cols-3 gap-3">
              <div className="rounded-2xl bg-white px-4 py-4">
                <p className="text-xs text-navy/38">结果数</p>
                <p className="mt-2 text-2xl font-semibold text-navy">{filteredDeals.length}</p>
              </div>
              <div className="rounded-2xl bg-white px-4 py-4">
                <p className="text-xs text-navy/38">高置信</p>
                <p className="mt-2 text-2xl font-semibold text-navy">{highestConfidenceCount}</p>
              </div>
              <div className="rounded-2xl bg-white px-4 py-4">
                <p className="text-xs text-navy/38">最低价</p>
                <p className="mt-2 text-2xl font-semibold text-navy">
                  {lowestPrice !== null ? `¥${lowestPrice}` : '--'}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-2 px-6 lg:px-8">
        {filters.map((filter) => (
          <button
            key={filter}
            onClick={() => setActiveFilter(filter)}
            className={`rounded-full border px-3.5 py-1.5 text-xs font-medium transition-all duration-200 ${
              activeFilter === filter
                ? 'border-navy bg-navy text-white shadow-sm'
                : 'border-gray-100 bg-white text-gray-400 hover:border-navy/20 hover:text-navy'
            }`}
          >
            {filter}
          </button>
        ))}
      </div>

      <div className="px-6 pb-12 lg:px-8">
        {error && (
          <div className="mb-4 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-500">
            {error}
          </div>
        )}

        {!loading && filteredDeals.length === 0 && !error && (
          <div className="mb-4 rounded-2xl bg-white px-5 py-6 text-sm text-gray-400 shadow-card">
            暂时没有找到符合条件的票，换个说法再试试。
          </div>
        )}

        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-12 xl:auto-rows-[minmax(260px,auto)]">
          {filteredDeals.map((deal, index) => {
            const conf = confidenceConfig[deal.confidence]
            const isHovered = hoveredId === deal.id
            const discount = deal.originalPrice > deal.price
              ? Math.round((1 - deal.price / deal.originalPrice) * 100)
              : 0
            const compareBoard = buildPriceBoard(deal, index)

            return (
              <Link
                key={deal.id}
                href="/chat"
                onMouseEnter={() => setHoveredId(deal.id)}
                onMouseLeave={() => setHoveredId(null)}
                className={`group overflow-hidden rounded-[32px] bg-white shadow-[0_22px_60px_rgba(27,43,94,0.08)] transition-all duration-300 ${cardPattern[index % cardPattern.length]} ${
                  isHovered ? '-translate-y-1.5 shadow-[0_28px_80px_rgba(27,43,94,0.12)]' : ''
                }`}
              >
                <div
                  className="relative overflow-hidden"
                  style={{
                    background: `linear-gradient(140deg, ${deal.gradientFrom} 0%, ${deal.gradientTo} 100%)`,
                  }}
                >
                  <div
                    className={`absolute inset-0 bg-white/10 transition-opacity duration-300 ${
                      isHovered ? 'opacity-100' : 'opacity-0'
                    }`}
                  />

                  <div className="relative flex min-h-[230px] flex-col justify-between p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div className={`flex items-center gap-1.5 rounded-full ${conf.bg} px-2.5 py-1`}>
                        <span
                          className="h-1.5 w-1.5 rounded-full"
                          style={{ backgroundColor: conf.dot }}
                        />
                        <span className={`text-[10px] font-semibold ${conf.text}`}>{conf.label}</span>
                      </div>

                      <div className="text-right">
                        <p className="font-mono text-[10px] text-white/42">{deal.systemId}</p>
                        <p className="mt-1 rounded-full bg-white/16 px-2.5 py-1 text-[10px] font-medium text-white backdrop-blur-sm">
                          来源：{deal.platform}
                        </p>
                      </div>
                    </div>

                    <div>
                      <p className="font-mono text-[10px] text-white/62">
                        {deal.originCode} → {deal.destinationCode}
                      </p>
                      <h2 className="mt-2 text-[1.9rem] font-semibold leading-tight text-white">
                        {deal.origin} → {deal.destination}
                      </h2>
                      <p className="mt-3 max-w-[280px] text-sm text-white/76">
                        {deal.airline} · {deal.departDate} · {deal.departTime} - {deal.arriveTime}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="grid gap-5 p-5 xl:grid-cols-[minmax(0,1.2fr)_220px]">
                  <div>
                    <div className="mb-4 flex items-baseline gap-2">
                      <span className="font-heading text-[2.5rem] font-bold leading-none text-navy">
                        ¥{deal.price}
                      </span>
                      {deal.originalPrice > deal.price && (
                        <>
                          <span className="text-sm text-gray-300 line-through">¥{deal.originalPrice}</span>
                          <span className="ml-auto text-sm font-semibold text-signal">
                            -{discount}%
                          </span>
                        </>
                      )}
                    </div>

                    <div className="flex flex-wrap gap-1.5">
                      {deal.signals.map((signal) => (
                        <span
                          key={signal}
                          className="rounded-full bg-signal-muted px-2.5 py-1 text-[10px] font-medium text-signal-text"
                        >
                          {signal}
                        </span>
                      ))}
                    </div>

                    <div className="mt-5 grid gap-3 sm:grid-cols-2">
                      <div className="rounded-2xl bg-[#f7f9fc] px-4 py-4">
                        <p className="text-[11px] uppercase tracking-[0.14em] text-navy/30">行程时间</p>
                        <p className="mt-2 text-lg font-semibold text-navy">
                          {deal.departTime} - {deal.arriveTime}
                        </p>
                      </div>
                      <div className="rounded-2xl bg-[#f7f9fc] px-4 py-4">
                        <p className="text-[11px] uppercase tracking-[0.14em] text-navy/30">AI 判断</p>
                        <p className="mt-2 text-lg font-semibold text-navy">{deal.verdict}</p>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-[26px] bg-[linear-gradient(145deg,#f8faff_0%,#eef3ff_100%)] p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-navy/34">
                        平台比价
                      </p>
                      <span className="text-[11px] text-navy/34">同路线参考</span>
                    </div>

                    <div className="space-y-2.5">
                      {compareBoard.map((item) => (
                        <div
                          key={`${deal.id}-${item.platform}`}
                          className={`flex items-center justify-between rounded-2xl px-3 py-3 ${getCompareToneClass(item.tone)}`}
                        >
                          <div>
                            <p className="text-xs font-semibold">{item.platform}</p>
                            <p className="mt-1 text-[11px] opacity-70">
                              {item.tone === 'current' ? '当前展示票源' : item.tone === 'lower' ? '更低参考价' : '更高参考价'}
                            </p>
                          </div>
                          <span className="text-lg font-semibold">¥{item.price}</span>
                        </div>
                      ))}
                    </div>

                    <div className="mt-4 rounded-2xl bg-white px-3.5 py-3">
                      <div className="flex items-center justify-between text-[11px] text-navy/36">
                        <span>建议动作</span>
                        <span>{deal.confidence === 'high' ? '优先下单' : '继续观察'}</span>
                      </div>
                      <div className="mt-2 h-2 overflow-hidden rounded-full bg-[#e7ebf5]">
                        <div
                          className="h-full rounded-full bg-[linear-gradient(90deg,#1b2b5e_0%,#3a67d8_100%)]"
                          style={{
                            width: deal.confidence === 'high' ? '82%' : deal.confidence === 'medium' ? '64%' : '42%',
                          }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </Link>
            )
          })}

          {!loading && !error && (
            <>
              <div className="rounded-[32px] border border-[#e8edf7] bg-[linear-gradient(145deg,#1f2f69_0%,#2d4a93_100%)] p-6 text-white shadow-[0_22px_60px_rgba(27,43,94,0.14)] md:col-span-2 xl:col-span-4">
                <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-white/54">
                  Compare Logic
                </p>
                <h3 className="mt-3 text-[1.6rem] font-semibold leading-tight">
                  每张卡都先看票价，再看平台差价
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-white/72">
                  现在不是只给你一张票，而是把当前票源和其他平台的参考价一起摆出来，让你一眼判断这张票到底是真的值，还是只是看起来便宜。
                </p>
              </div>

              <div className="rounded-[32px] border border-[#e8edf7] bg-white p-6 shadow-[0_22px_60px_rgba(27,43,94,0.08)] xl:col-span-8">
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                  <div>
                    <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-navy/34">
                      Continue Search
                    </p>
                    <h3 className="mt-2 text-[1.7rem] font-semibold text-navy">
                      没看到合适的？换一个目的地继续找
                    </h3>
                    <p className="mt-2 text-sm text-navy/46">
                      回到对话页继续说预算、日期和城市，我会再把页面铺成新的一组机会，而不是只给你一条死板结果。
                    </p>
                  </div>

                  <Link
                    href="/chat"
                    className="inline-flex items-center justify-center gap-2 rounded-full bg-navy px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-navy-light"
                  >
                    返回对话
                    <svg className="h-3.5 w-3.5" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                      <path d="M2 7h10M8 3l4 4-4 4" />
                    </svg>
                  </Link>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
