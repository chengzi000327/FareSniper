'use client'

import React from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Gift, MapPin, Plane, X } from 'lucide-react'
import { DiscoveryCardContent } from '@/components/discovery-card-content'
import { api } from '@/lib/api'
import { dealToCardProps } from '@/lib/mappers'
import type { DiscoveryCardContentProps } from '@/components/discovery-card-content'

type Deal = {
  id: string
  from: string
  to: string
  price: string
  date: string
  reason: string
  image: string
  cardData: DiscoveryCardContentProps
}

export function ExplorePage() {
  const [deals, setDeals] = React.useState<Deal[]>([])
  const [loading, setLoading] = React.useState(true)
  const [departure, setDeparture] = React.useState('')
  const [selectedDeal, setSelectedDeal] = React.useState<Deal | null>(null)
  const [isDrawing, setIsDrawing] = React.useState(false)

  React.useEffect(() => {
    api
      .getRecommendations()
      .then((resp) => {
        const mapped: Deal[] = resp.cards
          .filter((c) => !!c.preview_deal)
          .map((c) => {
            const deal = c.preview_deal!
            return {
              id: c.id,
              from: deal.origin_city,
              to: deal.destination_city,
              price: String(deal.price),
              date: deal.depart_date,
              reason: c.reason,
              image: `https://picsum.photos/seed/${deal.destination_code}/400/300`,
              cardData: dealToCardProps(deal),
            }
          })
        setDeals(mapped)
      })
      .catch(() => {
        // keep empty state on error
      })
      .finally(() => setLoading(false))
  }, [])

  const visibleDeals = deals.filter((deal) => !departure || deal.from.includes(departure))

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

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="mb-6 flex flex-col gap-4 px-5 pt-6 sm:px-8 lg:flex-row lg:items-center lg:justify-between lg:px-12 lg:pt-8">
        <h1 className="text-3xl font-bold text-brand-text sm:text-4xl">探索发现</h1>
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="relative">
            <MapPin className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-muted" />
            <input
              type="text"
              placeholder="输入出发地（可选）"
              value={departure}
              onChange={(event) => setDeparture(event.target.value)}
              className="w-full rounded-2xl border border-brand-text/10 bg-white py-3 pl-11 pr-4 text-sm transition focus:border-brand-orange sm:w-64"
            />
          </div>
          <button
            type="button"
            onClick={handleDrawBlindBox}
            disabled={isDrawing || deals.length === 0}
            className="flex items-center justify-center gap-2 rounded-2xl bg-brand-text px-5 py-3 text-sm font-bold text-white transition hover:bg-brand-orange disabled:opacity-60"
          >
            <motion.div animate={isDrawing ? { rotate: 360 } : { rotate: 0 }} transition={isDrawing ? { repeat: Infinity, duration: 1, ease: 'linear' } : undefined}>
              <Gift className="h-4 w-4" />
            </motion.div>
            {isDrawing ? '抽取中...' : '盲盒抽取目的地'}
          </button>
        </div>
      </div>

      <div className="thin-scrollbar flex-1 overflow-y-auto px-5 pb-8 sm:px-8 lg:px-12">
        {loading ? (
          <div className="columns-1 gap-5 space-y-5 md:columns-2 xl:columns-3 2xl:columns-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="mb-5 h-80 animate-pulse break-inside-avoid rounded-[28px] bg-white/60" />
            ))}
          </div>
        ) : visibleDeals.length === 0 ? (
          <div className="flex h-48 items-center justify-center rounded-[28px] border border-dashed border-brand-text/10 text-brand-muted">
            {deals.length === 0 ? '暂无推荐，请稍后重试' : '没有匹配的出发地'}
          </div>
        ) : (
          <div className="columns-1 gap-5 space-y-5 md:columns-2 xl:columns-3 2xl:columns-4">
            {visibleDeals.map((deal) => (
              <motion.div
                key={deal.id}
                whileHover={{ y: -5 }}
                className="mb-5 break-inside-avoid overflow-hidden rounded-[28px] border border-brand-text/5 bg-white shadow-sm"
              >
                <img src={deal.image} alt={deal.to} className="h-auto w-full object-cover" referrerPolicy="no-referrer" />
                <div className="p-5">
                  <div className="mb-3 flex items-center gap-2">
                    <Plane className="h-4 w-4 text-brand-orange" />
                    <span className="text-base font-bold">
                      {deal.from} → {deal.to}
                    </span>
                  </div>
                  <div className="mb-1 flex items-baseline gap-2">
                    <div className="text-3xl font-black text-brand-text">¥{deal.price}</div>
                    <div className="text-sm text-brand-muted">起</div>
                  </div>
                  <div className="mb-3 text-sm text-brand-muted">{deal.date} · 往返含税</div>
                  <p className="mb-4 text-sm leading-6 text-brand-muted">{deal.reason}</p>
                  <div className="mb-4 flex items-center justify-between">
                    <span className="rounded-md bg-brand-bg px-2 py-1 text-xs text-brand-muted">直飞</span>
                    {deal.cardData.hasBaggage && (
                      <span className="rounded-md bg-brand-bg px-2 py-1 text-xs text-brand-muted">含行李</span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => setSelectedDeal(deal)}
                    className="w-full rounded-2xl bg-brand-bg px-4 py-3 text-sm font-bold text-brand-text transition hover:bg-brand-text hover:text-white"
                  >
                    查看详情
                  </button>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>

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
              onClick={(event) => event.stopPropagation()}
            >
              <button
                type="button"
                onClick={() => setSelectedDeal(null)}
                className="absolute right-4 top-4 z-10 rounded-full bg-white/90 p-2 transition hover:bg-white"
              >
                <X className="h-5 w-5 text-brand-text" />
              </button>
              <DiscoveryCardContent {...selectedDeal.cardData} />
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  )
}
