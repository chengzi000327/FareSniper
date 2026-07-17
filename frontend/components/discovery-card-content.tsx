import React from 'react'
import { ArrowRight, Bell, Briefcase, Equal, ExternalLink, Plane, Plus, ShieldCheck } from 'lucide-react'
import type { ProviderDisplayStatus } from '@/lib/api'

export type PriceItem = {
  name: string
  price: number | null
  lowest?: boolean
  status?: ProviderDisplayStatus
  url?: string | null
  data_provider?: string | null
}

export type DiscoveryCardContentProps = {
  from: string
  to: string
  date?: string
  basePrice: number | null
  totalPrice?: number | null
  tax: number | null
  baggageFee: number | null
  hasBaggage: boolean | null
  originalPrice?: number
  platform: string
  recommendScore?: string
  prices: PriceItem[]
  compact?: boolean
  onMonitorPrice?: () => void
  bookingUrl?: string | null
  placeholder?: boolean
}

export function DiscoveryCardContent({
  from,
  to,
  date,
  basePrice,
  totalPrice,
  tax,
  baggageFee,
  hasBaggage,
  platform,
  recommendScore,
  prices,
  compact,
  onMonitorPrice,
  bookingUrl,
  placeholder = false,
}: DiscoveryCardContentProps) {
  const computedTotal =
    totalPrice ??
    (basePrice !== null && tax !== null && baggageFee !== null
      ? basePrice + tax + baggageFee
      : null)
  const money = (value: number | null) => (value === null ? '待确认' : '¥' + value)
  const statusText: Partial<Record<ProviderDisplayStatus, string>> = {
    loading: '正在获取数据',
    queued: '等待下次刷新',
    stale: '价格可能已更新',
    timeout: '暂时超时',
    disabled: '尚未配置',
    error: '暂时不可用',
    empty: '暂无结果',
  }
  const hasFreeBaggage = hasBaggage === true && baggageFee === 0
  const isRealtimeLowest = (price: PriceItem) =>
    price.lowest === true && price.status === 'success' && price.price !== null && computedTotal !== null
  const hasVerifiedLowestPrice = prices.some(isRealtimeLowest)
  const safeBookingUrl = isHttpsUrl(bookingUrl) ? bookingUrl : null
  const cardPadding = compact ? 'p-3.5 sm:p-4' : 'p-5 sm:p-6'
  const sectionGap = compact ? 'mb-3.5' : 'mb-5'

  return (
    <div className={`flex h-full flex-col ${cardPadding}`}>
      <div className={`flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between ${compact ? 'mb-2.5' : 'mb-5'}`}>
        <div className="flex items-center gap-3">
          <div
            className={`flex items-center justify-center rounded-2xl bg-brand-orange/10 ${compact ? 'h-10 w-10' : 'h-12 w-12'}`}
          >
            <Plane className={`text-brand-orange ${compact ? 'h-5 w-5' : 'h-6 w-6'}`} />
          </div>
          <div>
            <div className="mb-1 flex items-center gap-2">
              <h3 className={`font-black leading-none ${compact ? 'text-lg' : 'text-xl sm:text-2xl'}`}>{from}</h3>
              <ArrowRight className="h-4 w-4 text-brand-muted/60" />
              <h3 className={`font-black leading-none ${compact ? 'text-lg' : 'text-xl sm:text-2xl'}`}>{to}</h3>
            </div>
            <p className={`font-medium text-brand-muted ${compact ? 'text-xs' : 'text-sm'}`}>
              {placeholder ? '待查询 · 正在获取数据' : `直飞特惠 · ${date || '实时价格'}`}
            </p>
          </div>
        </div>
        <div className="flex flex-col items-start sm:items-end">
          <div className="mb-2 rounded-md bg-green-500 px-2 py-1 text-[10px] font-bold uppercase tracking-[0.25em] text-white shadow-sm shadow-green-500/20">
            发现指数
          </div>
          <span className={`font-black leading-none tracking-tight text-green-500 ${compact ? 'text-2xl' : 'text-3xl'}`}>
            {recommendScore || '9.5'}
          </span>
        </div>
      </div>

      <div
        className={`relative ${sectionGap} grid grid-cols-2 items-center gap-3 overflow-hidden rounded-2xl border border-brand-text/5 bg-brand-bg/70 sm:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr] sm:gap-2 ${
          compact ? 'p-3 sm:p-3.5' : 'p-4 sm:p-[18px]'
        }`}
      >
        <div className="absolute left-0 top-0 h-1 w-full bg-gradient-to-r from-transparent via-brand-orange/20 to-transparent" />
        <PriceBlock label="票价" value={money(basePrice)} compact={compact} />
        <Plus className="hidden h-4 w-4 text-brand-muted/40 sm:block" />
        <PriceBlock label="机建燃油" value={money(tax)} compact={compact} />
        <Plus className="hidden h-4 w-4 text-brand-muted/40 sm:block" />
        <PriceBlock
          label="行李额"
          value={
            baggageFee !== null && baggageFee > 0
              ? '+¥' + baggageFee
              : hasFreeBaggage
                ? '免费'
                : hasBaggage === false
                  ? '不含'
                  : '待确认'
          }
          compact={compact}
          highlight={baggageFee !== null && baggageFee > 0}
        />
        <Equal className="hidden h-4 w-4 text-brand-muted/40 sm:block" />
        <div className="col-span-2 flex flex-col items-start border-t border-brand-text/5 pt-3 sm:col-span-1 sm:items-end sm:border-t-0 sm:pt-0">
          <span className="mb-1 text-[11px] font-bold text-brand-orange sm:text-xs">综合总价</span>
          <span className={`font-black leading-none text-brand-orange ${compact ? 'text-2xl' : 'text-3xl'}`}>{money(computedTotal)}</span>
        </div>
      </div>

      <div className={`${sectionGap} space-y-2.5`}>
        <div className="flex items-center gap-3 rounded-2xl border border-brand-text/5 bg-white px-4 py-2 shadow-sm">
          <div className={`flex h-9 w-9 items-center justify-center rounded-full ${hasBaggage === true ? 'bg-green-50' : 'bg-brand-orange/5'}`}>
            <Briefcase className={`h-4 w-4 ${hasBaggage === true ? 'text-green-500' : 'text-brand-orange'}`} />
          </div>
          <span className={`text-sm leading-6 font-medium ${hasFreeBaggage ? 'text-green-600' : 'text-brand-orange'}`}>
            {hasBaggage === null
              ? baggageFee !== null && baggageFee > 0
                ? '行李加购费 ¥' + baggageFee + '，已计入总价，行李额以预订页为准'
                : '行李额以预订页为准'
              : hasBaggage === false
                ? baggageFee !== null && baggageFee > 0
                  ? '不含免费托运行李额度，需加购 ¥' + baggageFee + '，已计入总价'
                  : '不含免费托运行李额度，行李额以预订页为准'
                : hasFreeBaggage
                ? '含免费托运行李额度'
                : baggageFee === null
                  ? '行李额以预订页为准'
                  : '含托运行李额度，行李费用 ¥' + baggageFee + '，以预订页为准'}
          </span>
        </div>

        <div className={`flex items-start gap-3 rounded-2xl px-4 py-2 ${hasVerifiedLowestPrice ? 'border border-green-100/60 bg-green-50/60' : 'border border-brand-text/5 bg-brand-bg/40'}`}>
          <ShieldCheck className="mt-0.5 h-4 w-4 text-green-600" />
          <p className={`text-sm leading-6 ${hasVerifiedLowestPrice ? 'text-green-800' : 'text-brand-muted'}`}>
            {hasVerifiedLowestPrice ? (
              <>
                AI 监测：该价格为综合行李后的全网<span className="font-bold underline decoration-green-300 decoration-2 underline-offset-2">最优解</span>，建议在{' '}
                <span className="font-bold text-brand-orange">{platform}</span> 下单。
              </>
            ) : (
              '价格、税费与行李规则以预订页为准。'
            )}
          </p>
        </div>
      </div>

      <div className={`${sectionGap} rounded-2xl border border-brand-text/5 bg-brand-bg/40 ${compact ? 'p-3 sm:p-3.5' : 'p-4 sm:p-[18px]'}`}>
        <div className="mb-2.5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={`h-2 w-2 rounded-full bg-brand-orange ${hasVerifiedLowestPrice ? 'animate-pulse' : ''}`} />
            <span className="text-xs font-bold text-brand-muted sm:text-sm">
              {hasVerifiedLowestPrice ? '全网多端实时同步' : '多端价格参考'}
            </span>
          </div>
          {hasVerifiedLowestPrice ? (
            <span className="rounded-md border border-brand-orange/20 bg-white/60 px-2 py-1 text-[11px] font-bold text-brand-orange">
              实时底价
            </span>
          ) : null}
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {prices.map((price) => {
            const lowest = isRealtimeLowest(price)

            return (
            <div key={price.name} className={`flex items-center justify-between ${lowest ? 'opacity-100' : 'opacity-45'}`}>
              <span className="text-sm font-medium text-brand-text">{price.name}</span>
              <div className="flex items-center gap-2">
                {lowest && <span className="rounded bg-brand-orange px-1.5 py-0.5 text-[10px] font-bold text-white">最低</span>}
                {price.status === 'view_live_price' && isHttpsUrl(price.url) ? (
                  <a
                    href={price.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-black text-brand-orange sm:text-base"
                  >
                    查看实时价
                  </a>
                ) : (
                  <span className={`text-sm font-black sm:text-base ${lowest ? 'text-brand-orange' : 'text-brand-text'}`}>
                    {price.status ? statusText[price.status] ?? money(price.price) : money(price.price)}
                  </span>
                )}
              </div>
            </div>
            )
          })}
        </div>
      </div>

      <div className="mt-auto flex flex-col gap-2 sm:flex-row">
        <button
          type="button"
          onClick={onMonitorPrice}
          className="flex flex-1 items-center justify-center gap-2 rounded-2xl border border-brand-text/10 bg-white px-4 py-2 text-sm font-bold text-brand-text transition hover:bg-brand-orange/5"
        >
          <Bell className="h-4 w-4" />
          监控价格
        </button>
        {safeBookingUrl ? (
          <a
            href={safeBookingUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex flex-1 items-center justify-center gap-2 rounded-2xl bg-brand-text px-4 py-2 text-sm font-bold text-white shadow-card transition hover:bg-brand-orange"
          >
            前往预订
            <ExternalLink className="h-4 w-4 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
          </a>
        ) : (
          <button
            type="button"
            disabled
            className="group flex flex-1 cursor-not-allowed items-center justify-center gap-2 rounded-2xl bg-brand-text px-4 py-2 text-sm font-bold text-white opacity-50 shadow-card"
          >
            前往预订
            <ExternalLink className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  )
}

function isHttpsUrl(value: string | null | undefined): value is string {
  if (!value) return false

  try {
    return new URL(value).protocol === 'https:'
  } catch {
    return false
  }
}

function PriceBlock({
  label,
  value,
  compact,
  highlight,
}: {
  label: string
  value: string
  compact?: boolean
  highlight?: boolean
}) {
  return (
    <div className="flex flex-col items-center">
      <span className={`mb-1 text-brand-muted ${compact ? 'text-[11px]' : 'text-xs'}`}>{label}</span>
      <span className={`font-bold ${highlight ? 'text-brand-orange' : 'text-brand-text'} ${compact ? 'text-sm' : 'text-base'}`}>{value}</span>
    </div>
  )
}
