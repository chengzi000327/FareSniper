'use client'

import { useState } from 'react'
import Link from 'next/link'

const deals = [
  {
    id: 'fd001',
    origin: '北京', originCode: 'BJS',
    destination: '三亚', destinationCode: 'SYX',
    price: 398, originalPrice: 980,
    departDate: '2026-05-01', airline: '海南航空',
    signals: ['近90天低位', '五一低价'],
    confidence: 'high' as const,
    systemId: 'SYS.042',
    gradientFrom: '#0EA5E9', gradientTo: '#22D3EE',
    verdict: '建议现在买',
  },
  {
    id: 'fd002',
    origin: '上海', originCode: 'SHA',
    destination: '大理', destinationCode: 'DLU',
    price: 560, originalPrice: 1200,
    departDate: '2026-04-20', airline: '云南航空',
    signals: ['符合心理价位', '近期最低'],
    confidence: 'high' as const,
    systemId: 'SYS.117',
    gradientFrom: '#8B5CF6', gradientTo: '#C4B5FD',
    verdict: '建议现在买',
  },
  {
    id: 'fd003',
    origin: '广州', originCode: 'CAN',
    destination: '成都', destinationCode: 'CTU',
    price: 320, originalPrice: 720,
    departDate: '2026-04-25', airline: '四川航空',
    signals: ['历史新低'],
    confidence: 'medium' as const,
    systemId: 'SYS.208',
    gradientFrom: '#10B981', gradientTo: '#6EE7B7',
    verdict: '可以关注',
  },
  {
    id: 'fd004',
    origin: '北京', originCode: 'BJS',
    destination: '厦门', destinationCode: 'XMN',
    price: 480, originalPrice: 1100,
    departDate: '2026-05-03', airline: '厦门航空',
    signals: ['近90天低位', '假期前低价'],
    confidence: 'high' as const,
    systemId: 'SYS.334',
    gradientFrom: '#F59E0B', gradientTo: '#FCD34D',
    verdict: '建议现在买',
  },
  {
    id: 'fd005',
    origin: '深圳', originCode: 'SZX',
    destination: '西藏', destinationCode: 'LXA',
    price: 890, originalPrice: 1850,
    departDate: '2026-05-10', airline: '西藏航空',
    signals: ['季节性低点', '符合偏好'],
    confidence: 'medium' as const,
    systemId: 'SYS.456',
    gradientFrom: '#3B82F6', gradientTo: '#93C5FD',
    verdict: '可以关注',
  },
]

const confidenceConfig = {
  high:   { label: '高置信', dot: '#22C55E', bg: 'bg-signal-muted', text: 'text-signal-text' },
  medium: { label: '中置信', dot: '#F59E0B', bg: 'bg-amber-50',    text: 'text-amber-700'  },
  low:    { label: '低置信', dot: '#D1D5DB', bg: 'bg-gray-50',     text: 'text-gray-500'   },
}

const filters = ['全部', '高置信', '符合偏好', '今日新增']

export default function ExplorePage() {
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [activeFilter, setActiveFilter] = useState('全部')

  return (
    <div className="min-h-screen bg-bg-gray font-sans">

      {/* ── NAV ────────────────────────────────────────── */}
      <nav className="flex items-center justify-between px-8 py-5">
        <Link href="/chat" className="flex items-center gap-2 group">
          <div className="w-4 h-4 rounded-full bg-navy group-hover:scale-110 transition-transform" />
          <span className="font-mono text-[11px] tracking-[0.18em] text-navy/35 uppercase group-hover:text-navy/60 transition-colors">
            FareSniper
          </span>
        </Link>
        <div className="flex items-center gap-5">
          <Link href="/chat" className="text-sm text-gray-400 hover:text-navy transition-colors">
            对话
          </Link>
          <Link
            href="/memory"
            className="text-sm text-gray-400 hover:text-navy transition-colors flex items-center gap-1.5"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-signal" />
            我的记忆
          </Link>
          <div className="w-8 h-8 rounded-full bg-navy flex items-center justify-center text-white text-xs font-semibold">
            我
          </div>
        </div>
      </nav>

      {/* ── HEADER ─────────────────────────────────────── */}
      <div className="px-8 pt-2 pb-6">
        <p className="font-mono text-[11px] tracking-[0.18em] text-gray-300 uppercase mb-2">
          DISCOVER · 今日精选
        </p>
        <h1 className="font-heading text-[2.6rem] font-bold text-navy leading-tight">
          为你发现
        </h1>
        <p className="text-gray-400 text-sm mt-2">
          AI 从今日{' '}
          <span className="text-navy font-semibold">847</span>{' '}
          个价格异动中筛选 · 共{' '}
          <span className="text-navy font-semibold">5</span>{' '}
          个值得关注
        </p>
      </div>

      {/* ── FILTER BAR ─────────────────────────────────── */}
      <div className="px-8 flex items-center gap-2 mb-6">
        {filters.map((f) => (
          <button
            key={f}
            onClick={() => setActiveFilter(f)}
            className={`text-xs font-medium px-3.5 py-1.5 rounded-full border transition-all duration-200 ${
              activeFilter === f
                ? 'bg-navy text-white border-navy shadow-sm'
                : 'bg-white text-gray-400 border-gray-100 hover:border-navy/20 hover:text-navy'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {/* ── DEAL CARDS HORIZONTAL SCROLL ───────────────── */}
      <div className="scroll-x pb-8">
        <div className="flex gap-4 px-8" style={{ width: 'max-content' }}>
          {deals.map((deal) => {
            const conf = confidenceConfig[deal.confidence]
            const isHovered = hoveredId === deal.id
            const discount = Math.round((1 - deal.price / deal.originalPrice) * 100)

            return (
              <Link
                key={deal.id}
                href="/chat"
                onMouseEnter={() => setHoveredId(deal.id)}
                onMouseLeave={() => setHoveredId(null)}
                className={`flex-shrink-0 w-[272px] bg-white rounded-3xl overflow-hidden shadow-card transition-all duration-300 ${
                  isHovered ? 'shadow-card-float -translate-y-2' : ''
                }`}
              >
                {/* ── DESTINATION IMAGE (gradient) */}
                <div
                  className="h-44 relative overflow-hidden"
                  style={{
                    background: `linear-gradient(140deg, ${deal.gradientFrom} 0%, ${deal.gradientTo} 100%)`,
                  }}
                >
                  {/* Shimmer overlay on hover */}
                  <div
                    className={`absolute inset-0 bg-white/10 transition-opacity duration-300 ${isHovered ? 'opacity-100' : 'opacity-0'}`}
                  />

                  {/* System ID — top right */}
                  <span className="absolute top-3 right-3.5 font-mono text-[10px] text-white/40">
                    {deal.systemId}
                  </span>

                  {/* Confidence badge — top left */}
                  <div className={`absolute top-3 left-3.5 flex items-center gap-1.5 ${conf.bg} px-2.5 py-1 rounded-full`}>
                    <span
                      className="w-1.5 h-1.5 rounded-full"
                      style={{ backgroundColor: conf.dot }}
                    />
                    <span className={`text-[10px] font-semibold ${conf.text}`}>{conf.label}</span>
                  </div>

                  {/* Route overlay — bottom */}
                  <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/30 to-transparent">
                    <p className="font-mono text-[10px] text-white/60 mb-0.5">
                      {deal.originCode} → {deal.destinationCode}
                    </p>
                    <p className="text-white font-semibold text-[1.05rem] leading-tight">
                      {deal.origin} → {deal.destination}
                    </p>
                  </div>
                </div>

                {/* ── CARD BODY */}
                <div className="p-5">
                  {/* Price row */}
                  <div className="flex items-baseline gap-2 mb-3">
                    <span className="font-heading text-[2.2rem] font-bold text-navy leading-none">
                      ¥{deal.price}
                    </span>
                    <span className="text-gray-300 text-sm line-through">¥{deal.originalPrice}</span>
                    <span className="ml-auto text-xs font-semibold text-signal">
                      -{discount}%
                    </span>
                  </div>

                  {/* Meta */}
                  <p className="text-gray-400 text-xs mb-3">
                    {deal.airline} · {deal.departDate}
                  </p>

                  {/* Signal tags */}
                  <div className="flex flex-wrap gap-1.5 mb-4">
                    {deal.signals.map((signal) => (
                      <span
                        key={signal}
                        className="bg-signal-muted text-signal-text text-[10px] font-medium px-2.5 py-0.5 rounded-full"
                      >
                        {signal}
                      </span>
                    ))}
                  </div>

                  {/* AI verdict bar */}
                  <div className="bg-navy/[0.05] rounded-xl px-3.5 py-2.5 flex items-center justify-between">
                    <span className="text-gray-400 text-[11px] font-mono">AI 判断</span>
                    <span
                      className={`text-xs font-semibold flex items-center gap-1.5 ${
                        deal.confidence === 'high' ? 'text-navy' : 'text-gray-400'
                      }`}
                    >
                      {deal.verdict}
                      <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                        <path d="M2 6h8M7 3l3 3-3 3" />
                      </svg>
                    </span>
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      </div>

      {/* ── BOTTOM CTA ─────────────────────────────────── */}
      <div className="px-8 pb-12">
        <div className="bg-navy rounded-2xl px-6 py-5 flex items-center justify-between max-w-[600px]">
          <div>
            <p className="text-white font-semibold text-sm mb-0.5">没看到合适的？</p>
            <p className="text-white/50 text-xs">告诉我你的想法，我再帮你找</p>
          </div>
          <Link
            href="/chat"
            className="bg-white text-navy text-sm font-semibold px-4 py-2.5 rounded-xl hover:bg-white/90 transition-colors flex items-center gap-1.5"
          >
            开始对话
            <svg className="w-3.5 h-3.5" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M2 7h10M8 3l4 4-4 4" />
            </svg>
          </Link>
        </div>
      </div>
    </div>
  )
}
