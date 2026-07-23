'use client'

import React from 'react'
import { ArrowRight, Bell, Briefcase, Equal, ExternalLink, Plane, Plus, ShieldCheck } from 'lucide-react'
import { formatCurrency } from '@/lib/currency'
import { EventName, track } from '@/lib/analytics'
import type { DataFreshness, PriceItem, ProviderStatus } from '@/lib/api'

const MAX_TIMER_DELAY_MS = 2_147_483_647

function useExpiryClock(
  values: ReadonlyArray<string | null | undefined>,
): number | null {
  const expiryKey = values
    .filter((value): value is string => typeof value === 'string')
    .sort()
    .join('|')
  const expiryInstants = React.useMemo(
    () =>
      expiryKey
        .split('|')
        .filter(Boolean)
        .map((value) => Date.parse(value))
        .filter(Number.isFinite),
    [expiryKey],
  )
  const [now, setNow] = React.useState<number | null>(null)

  React.useEffect(() => {
    if (expiryInstants.length === 0) return

    let timer: number | undefined
    let disposed = false

    const clearTimer = () => {
      if (timer !== undefined) {
        window.clearTimeout(timer)
        timer = undefined
      }
    }
    const refresh = () => {
      if (disposed) return
      const current = Date.now()
      setNow(current)
      clearTimer()
      const nextExpiry = expiryInstants
        .filter((expiry) => expiry > current)
        .sort((left, right) => left - right)[0]
      if (nextExpiry !== undefined) {
        const delay = Math.min(
          Math.max(0, nextExpiry - current),
          MAX_TIMER_DELAY_MS,
        )
        timer = window.setTimeout(refresh, delay)
      }
    }
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') refresh()
    }

    refresh()
    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      disposed = true
      clearTimer()
      window.removeEventListener('focus', refresh)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [expiryInstants])

  return now
}

function isExpiryCurrent(
  value: string | null | undefined,
  now: number | null,
): boolean {
  if (value === null || value === undefined) return true
  const expiry = Date.parse(value)
  return now !== null && Number.isFinite(expiry) && expiry > now
}

export type DiscoveryCardContentProps = {
  from: string
  to: string
  originCode?: string
  destinationCode?: string
  date?: string
  flightNo?: string
  airline?: string
  stops?: number
  signals?: string[]
  basePrice: number | null
  totalPrice?: number | null
  tax: number | null
  taxSource?: 'provider' | 'regulatory_estimate' | null
  baggageFee: number | null
  baggageAllowance?: string | null
  hasBaggage: boolean | null
  currency: string
  originalPrice?: number
  platform: string
  recommendScore?: string
  winningPriceId?: string | null
  dataFreshness?: DataFreshness
  inventoryExpiresAt?: string | null
  prices: PriceItem[]
  compact?: boolean
  narrow?: boolean
  onMonitorPrice?: () => void
  bookingUrl?: string | null
  onSearch?: () => void
  placeholder?: boolean
  demo?: boolean
}

export function DiscoveryCardContent({
  from,
  to,
  date,
  flightNo,
  airline,
  stops,
  signals = [],
  basePrice,
  totalPrice,
  tax,
  taxSource,
  baggageFee,
  baggageAllowance,
  hasBaggage,
  currency,
  platform,
  recommendScore,
  winningPriceId,
  dataFreshness,
  inventoryExpiresAt,
  prices,
  compact,
  narrow = false,
  onMonitorPrice,
  bookingUrl,
  onSearch,
  placeholder = false,
  demo = false,
}: DiscoveryCardContentProps) {
  const componentTotal =
    basePrice !== null && tax !== null && baggageFee !== null
      ? basePrice + tax + baggageFee
      : null
  const computedTotal = totalPrice ?? componentTotal
  const displayedTicketPrice = basePrice ?? totalPrice ?? null
  const usesPlatformQuoteAsTicket =
    basePrice === null && displayedTicketPrice !== null
  const feeBreakdownComplete =
    componentTotal !== null &&
    hasBaggage !== null &&
    (totalPrice === null || totalPrice === undefined || totalPrice === componentTotal)
  const money = (value: number | null) => formatCurrency(value, currency)
  const statusText: Partial<Record<ProviderStatus, string>> = {
    loading: '正在获取数据',
    queued: '等待下次刷新',
    stale: '价格可能已更新',
    timeout: '暂时超时',
    disabled: '尚未配置',
    error: '暂时不可用',
    empty: '暂无结果',
  }
  const hasFreeBaggage = hasBaggage === true && baggageFee === 0
  const expiryNow = useExpiryClock([
    inventoryExpiresAt,
    ...prices.map((price) => price.expires_at),
  ])
  const isSelectedWinner = (price: PriceItem) => {
    const freshWinner =
      price.provider_status === 'success' &&
      price.price_status === 'priced' &&
      price.data_freshness === 'fresh' &&
      isExpiryCurrent(inventoryExpiresAt, expiryNow) &&
      isExpiryCurrent(price.expires_at, expiryNow)
    const staleCtripWinner =
      price.data_provider === 'ctrip_snapshot' &&
      price.provider_status === 'stale' &&
      price.price_status === 'stale' &&
      price.data_freshness === 'stale'

    return (
      price.id === winningPriceId &&
      price.price !== null &&
      computedTotal !== null &&
      price.price === computedTotal &&
      price.currency === currency &&
      price.name === platform &&
      price.data_freshness === dataFreshness &&
      (freshWinner || (staleCtripWinner && isHttpsUrl(price.url)))
    )
  }
  const selectedWinner = prices.find(isSelectedWinner)
  const hasSelectedWinner = selectedWinner !== undefined
  const hasRealtimeWinner =
    selectedWinner !== undefined &&
    selectedWinner.provider_status === 'success' &&
    selectedWinner.price_status === 'priced' &&
    selectedWinner.data_freshness === 'fresh' &&
    dataFreshness === 'fresh' &&
    isExpiryCurrent(inventoryExpiresAt, expiryNow) &&
    isExpiryCurrent(selectedWinner.expires_at, expiryNow)
  const safeBookingUrl =
    hasSelectedWinner &&
    selectedWinner &&
    isHttpsUrl(bookingUrl) &&
    bookingUrl === selectedWinner.url
      ? bookingUrl
      : null
  const trackPurchaseJump = () => {
    if (!flightNo) return
    void track(EventName.PurchaseJumped, {
      flight_no: flightNo,
      platform,
      price: computedTotal,
      signals,
      airline,
      origin: from,
      destination: to,
      depart_date: date,
    }).catch(() => undefined)
  }
  const cardPadding = narrow ? 'p-2.5' : compact ? 'p-3.5 sm:p-4' : 'p-5 sm:p-6'
  const sectionGap = narrow ? 'mb-2' : compact ? 'mb-3.5' : 'mb-5'
  const numericRecommendScore = Number(recommendScore)
  const visibleRecommendScore =
    recommendScore &&
    Number.isFinite(numericRecommendScore) &&
    numericRecommendScore > 0
      ? recommendScore
      : null
  const routeKind =
    stops === 0
      ? '直飞特惠'
      : typeof stops === 'number' && stops > 0
        ? `中转 ${stops} 次`
        : '实时航班'

  return (
    <div className={`flex h-full flex-col ${cardPadding}`}>
      <div className={`flex ${narrow ? 'items-start justify-between gap-2' : 'flex-col gap-3 sm:flex-row sm:items-start sm:justify-between'} ${narrow ? 'mb-2' : compact ? 'mb-2.5' : 'mb-5'}`}>
        <div className={`flex items-center ${narrow ? 'gap-2.5' : 'gap-3'}`}>
          <div
            className={`flex items-center justify-center rounded-2xl bg-brand-orange/10 ${narrow ? 'h-8 w-8' : compact ? 'h-10 w-10' : 'h-12 w-12'}`}
          >
            <Plane className={`text-brand-orange ${narrow ? 'h-4 w-4' : compact ? 'h-5 w-5' : 'h-6 w-6'}`} />
          </div>
          <div>
            <div className={`flex items-center ${narrow ? 'mb-0.5 gap-1.5' : 'mb-1 gap-2'}`}>
              <h3 className={`font-black leading-none ${narrow ? 'text-sm' : compact ? 'text-lg' : 'text-xl sm:text-2xl'}`}>{from}</h3>
              <ArrowRight className={`${narrow ? 'h-3.5 w-3.5' : 'h-4 w-4'} text-brand-muted/60`} />
              <h3 className={`font-black leading-none ${narrow ? 'text-sm' : compact ? 'text-lg' : 'text-xl sm:text-2xl'}`}>{to}</h3>
            </div>
            <p className={`font-medium text-brand-muted ${narrow ? 'text-[9px] leading-4' : compact ? 'text-xs' : 'text-sm'}`}>
              {demo
                ? '虚拟示例价 · 查询后更新'
                : placeholder
                  ? '待查询 · 正在获取数据'
                : hasRealtimeWinner
                  ? `${routeKind} · ${date || '实时价格'}`
                  : `航班价格参考${date ? ` · ${date}` : ''}`}
            </p>
          </div>
        </div>
        {visibleRecommendScore ? (
          <div className={`flex shrink-0 flex-col ${narrow ? 'items-end' : 'items-start sm:items-end'}`}>
            <div className={`${narrow ? 'mb-1 px-1.5 py-0.5 text-[8px]' : 'mb-2 px-2 py-1 text-[10px]'} rounded-md bg-green-500 font-bold uppercase tracking-[0.25em] text-white shadow-sm shadow-green-500/20`}>
              发现指数
            </div>
            <span className={`font-black leading-none tracking-tight text-green-500 ${narrow ? 'text-lg' : compact ? 'text-2xl' : 'text-3xl'}`}>
              {visibleRecommendScore}
            </span>
          </div>
        ) : null}
      </div>

      <div
        className={`relative ${sectionGap} grid items-center overflow-hidden rounded-2xl border border-brand-text/5 bg-brand-bg/70 ${narrow ? 'grid-cols-4 gap-1' : 'grid-cols-2 gap-3 sm:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr] sm:gap-2'} ${
          narrow ? 'p-2' : compact ? 'p-3 sm:p-3.5' : 'p-4 sm:p-[18px]'
        }`}
      >
        <div className="absolute left-0 top-0 h-1 w-full bg-gradient-to-r from-transparent via-brand-orange/20 to-transparent" />
        <PriceBlock label="票价" value={money(displayedTicketPrice)} compact={compact} narrow={narrow} />
        <Plus className={`hidden h-4 w-4 text-brand-muted/40 ${narrow ? '' : 'sm:block'}`} />
        <PriceBlock
          label={taxSource === 'regulatory_estimate' ? '机建燃油（现行）' : '机建燃油'}
          value={money(tax)}
          compact={compact}
          narrow={narrow}
        />
        <Plus className={`hidden h-4 w-4 text-brand-muted/40 ${narrow ? '' : 'sm:block'}`} />
        <PriceBlock
          label="行李额"
          value={
            baggageAllowance
              ? baggageAllowance
              : baggageFee !== null && baggageFee > 0
              ? '+' + money(baggageFee)
              : hasFreeBaggage
                ? '免费'
                : hasBaggage === false
                  ? '不含'
                  : placeholder
                    ? '待确认'
                    : '平台未返回'
          }
          compact={compact}
          narrow={narrow}
          highlight={baggageFee !== null && baggageFee > 0}
        />
        <Equal className={`hidden h-4 w-4 text-brand-muted/40 ${narrow ? '' : 'sm:block'}`} />
        <div className={`flex flex-col ${narrow ? 'col-span-1 items-center border-l border-brand-text/5 pl-1' : 'col-span-2 items-start border-t border-brand-text/5 pt-3 sm:col-span-1 sm:items-end sm:border-t-0 sm:pt-0'}`}>
          <span className={`${narrow ? 'mb-0.5 text-[9px]' : 'mb-1 text-[11px] sm:text-xs'} font-bold text-brand-orange`}>
            {demo
              ? '示例总价'
              : feeBreakdownComplete
                ? '综合总价'
                : '平台展示价'}
          </span>
          <span className={`font-black leading-none text-brand-orange ${narrow ? 'text-lg' : compact ? 'text-2xl' : 'text-3xl'}`}>{money(computedTotal)}</span>
        </div>
      </div>

      <div className={`${sectionGap} ${narrow ? 'space-y-2' : 'space-y-2.5'}`}>
        <div className={`flex items-center rounded-2xl border border-brand-text/5 bg-white shadow-sm ${narrow ? 'gap-2 px-3 py-2' : 'gap-3 px-4 py-2'}`}>
          <div className={`flex shrink-0 items-center justify-center rounded-full ${narrow ? 'h-8 w-8' : 'h-9 w-9'} ${hasBaggage === true ? 'bg-green-50' : 'bg-brand-orange/5'}`}>
            <Briefcase className={`${narrow ? 'h-3.5 w-3.5' : 'h-4 w-4'} ${hasBaggage === true ? 'text-green-500' : 'text-brand-orange'}`} />
          </div>
          <span className={`${narrow ? 'text-[10px] leading-[1.5]' : 'text-sm leading-6'} font-medium ${hasFreeBaggage ? 'text-green-600' : 'text-brand-orange'}`}>
            {hasBaggage === null
              ? baggageFee !== null && baggageFee > 0
                ? '行李加购费 ' + money(baggageFee) + '，已计入总价，行李额以预订页为准'
                : '平台未返回行李额度，请在预订页确认'
              : hasBaggage === false
                ? baggageFee !== null && baggageFee > 0
                  ? '不含免费托运行李额度，需加购 ' + money(baggageFee) + '，已计入总价'
                  : '不含免费托运行李额度，行李额以预订页为准'
                : hasFreeBaggage
                ? baggageAllowance
                  ? '含免费托运行李 ' + baggageAllowance
                  : '含免费托运行李额度'
                : baggageFee === null
                  ? '行李额以预订页为准'
                  : '含托运行李额度，行李费用 ' + money(baggageFee) + '，以预订页为准'}
          </span>
        </div>

        <div className={`flex items-start rounded-2xl ${narrow ? 'gap-2 px-3 py-2' : 'gap-3 px-4 py-2'} ${hasRealtimeWinner ? 'border border-green-100/60 bg-green-50/60' : 'border border-brand-text/5 bg-brand-bg/40'}`}>
          <ShieldCheck className={`${narrow ? 'h-3.5 w-3.5' : 'mt-0.5 h-4 w-4'} shrink-0 text-green-600`} />
          <p className={`${narrow ? 'text-[10px] leading-[1.55]' : 'text-sm leading-6'} ${hasRealtimeWinner ? 'text-green-800' : 'text-brand-muted'}`}>
            {demo ? (
              '此处为虚拟示例价格，不参与实时最低价判断；进入对话查询后会替换为真实来源结果。'
            ) : hasRealtimeWinner ? (
              <>
                {feeBreakdownComplete ? (
                  <>
                    AI 监测：该价格含
                    {taxSource === 'regulatory_estimate' ? '按现行标准计算的机建燃油' : '机建燃油'}
                    与行李费用，是当前全网
                    <span className="font-bold underline decoration-green-300 decoration-2 underline-offset-2">最优解</span>，建议在{' '}
                    <span className="font-bold text-brand-orange">{platform}</span> 下单。
                  </>
                ) : (
                  <>
                    当前为 <span className="font-bold text-brand-orange">{platform}</span> 平台展示价，
                    {taxSource === 'regulatory_estimate'
                      ? '机建燃油已按现行标准计算，行李额度待平台补充。'
                      : '机建燃油与行李额度待平台补充。'}
                  </>
                )}
              </>
            ) : usesPlatformQuoteAsTicket ? (
              '平台未单独拆分基础票价，票价栏暂按平台展示价显示；税费与行李规则以预订页为准。'
            ) : (
              '价格、税费与行李规则以预订页为准。'
            )}
          </p>
        </div>
      </div>

      <div className={`${sectionGap} rounded-2xl border border-brand-text/5 bg-brand-bg/40 ${narrow ? 'p-2.5' : compact ? 'p-3 sm:p-3.5' : 'p-4 sm:p-[18px]'}`}>
        <div className={`${narrow ? 'mb-2' : 'mb-2.5'} flex items-center justify-between`}>
          <div className="flex items-center gap-2">
            <div className={`h-2 w-2 rounded-full bg-brand-orange ${hasRealtimeWinner ? 'animate-pulse' : ''}`} />
            <span className={`${narrow ? 'text-[10px]' : 'text-xs sm:text-sm'} font-bold text-brand-muted`}>
              {demo
                ? '平台价格示例'
                : hasRealtimeWinner
                  ? '全网多端实时同步'
                  : '多端价格参考'}
            </span>
          </div>
          {hasRealtimeWinner ? (
            <span className={`rounded-md border border-brand-orange/20 bg-white/60 font-bold text-brand-orange ${narrow ? 'px-1.5 py-0.5 text-[9px]' : 'px-2 py-1 text-[11px]'}`}>
              实时底价
            </span>
          ) : null}
        </div>
        <div className={`grid gap-2 ${narrow ? '' : 'sm:grid-cols-2'}`}>
          {prices.map((price) => {
            const lowest = hasSelectedWinner && price === selectedWinner
            const freshnessMessage =
              price.data_freshness === 'unknown'
                ? '更新时间未知'
                : price.data_freshness === 'stale'
                  ? '价格可能已更新'
                  : undefined
            const providerMessage =
              price.provider_status === 'success'
                ? freshnessMessage
                : statusText[price.provider_status] ?? freshnessMessage
            const rowPrice = formatCurrency(price.price, price.currency)
            const displayedValue =
              price.price !== null
                ? rowPrice
                : providerMessage ?? rowPrice

            return (
            <div key={price.id} className={`flex items-center justify-between ${demo || lowest ? 'opacity-100' : 'opacity-45'}`}>
              <span className={`${narrow ? 'text-[10px]' : 'text-sm'} font-medium text-brand-text`}>{price.name}</span>
              <div className="flex items-center gap-2">
                {lowest && <span className={`rounded bg-brand-orange px-1.5 py-0.5 font-bold text-white ${narrow ? 'text-[8px]' : 'text-[10px]'}`}>最低</span>}
                {price.price === null && price.provider_status === 'success' && price.data_freshness === 'fresh' && price.price_status === 'view_live_price' && isExpiryCurrent(price.expires_at, expiryNow) && isHttpsUrl(price.url) ? (
                  <a
                    href={price.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`${narrow ? 'text-[11px]' : 'text-sm sm:text-base'} font-black text-brand-orange`}
                  >
                    查看实时价
                  </a>
                ) : (
                  <span className={`${narrow ? 'text-[11px]' : 'text-sm sm:text-base'} font-black ${lowest ? 'text-brand-orange' : 'text-brand-text'}`}>
                    {displayedValue}
                  </span>
                )}
              </div>
            </div>
            )
          })}
        </div>
      </div>

      <div className={`mt-auto flex ${narrow ? 'flex-row gap-1.5' : 'flex-col gap-2 sm:flex-row'}`}>
        {onSearch ? (
          <button
            type="button"
            onClick={onSearch}
            className={`flex flex-1 items-center justify-center rounded-2xl bg-brand-orange font-bold text-white transition hover:bg-brand-text ${narrow ? 'gap-1.5 px-3 py-2 text-[11px]' : 'gap-2 px-4 py-2 text-sm'}`}
          >
            <Plane className={narrow ? 'h-3.5 w-3.5' : 'h-4 w-4'} />
            在对话中查询
          </button>
        ) : null}
        <button
          type="button"
          onClick={onMonitorPrice}
          className={`flex flex-1 items-center justify-center rounded-2xl border border-brand-text/10 bg-white font-bold text-brand-text transition hover:bg-brand-orange/5 ${narrow ? 'gap-1.5 px-3 py-2 text-[11px]' : 'gap-2 px-4 py-2 text-sm'}`}
        >
          <Bell className={narrow ? 'h-3.5 w-3.5' : 'h-4 w-4'} />
          监控价格
        </button>
        {safeBookingUrl ? (
          <a
            href={safeBookingUrl}
            onClick={trackPurchaseJump}
            target="_blank"
            rel="noopener noreferrer"
            className={`group flex flex-1 items-center justify-center rounded-2xl bg-brand-text font-bold text-white shadow-card transition hover:bg-brand-orange ${narrow ? 'gap-1.5 px-3 py-2 text-[11px]' : 'gap-2 px-4 py-2 text-sm'}`}
          >
            前往预订
            <ExternalLink className={`${narrow ? 'h-3.5 w-3.5' : 'h-4 w-4'} transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5`} />
          </a>
        ) : (
          <button
            type="button"
            disabled
            className={`group flex flex-1 cursor-not-allowed items-center justify-center rounded-2xl bg-brand-text font-bold text-white opacity-50 shadow-card ${narrow ? 'gap-1.5 px-3 py-2 text-[11px]' : 'gap-2 px-4 py-2 text-sm'}`}
          >
            前往预订
            <ExternalLink className={narrow ? 'h-3.5 w-3.5' : 'h-4 w-4'} />
          </button>
        )}
      </div>
    </div>
  )
}

function isHttpsUrl(value: string | null | undefined): value is string {
  if (!value) return false

  try {
    const parsed = new URL(value)
    return parsed.protocol === 'https:' && Boolean(parsed.hostname)
  } catch {
    return false
  }
}

function PriceBlock({
  label,
  value,
  compact,
  narrow,
  highlight,
}: {
  label: string
  value: string
  compact?: boolean
  narrow?: boolean
  highlight?: boolean
}) {
  return (
    <div className="flex min-w-0 flex-col items-center text-center">
      <span className={`${narrow ? 'mb-0.5 text-[9px] leading-4' : `mb-1 ${compact ? 'text-[11px]' : 'text-xs'}`} text-brand-muted`}>{label}</span>
      <span className={`font-bold ${highlight ? 'text-brand-orange' : 'text-brand-text'} ${narrow ? 'text-xs' : compact ? 'text-sm' : 'text-base'}`}>{value}</span>
    </div>
  )
}
