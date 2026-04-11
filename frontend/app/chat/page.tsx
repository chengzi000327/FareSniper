'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'

// Four floating deal cards for the corners
const floatingCards = [
  {
    id: 'f1',
    origin: '北京', destination: '三亚',
    price: 398, signal: '近90天低位',
    gradient: 'linear-gradient(135deg, #0EA5E9, #22D3EE)',
    position: { top: '10%', left: '4%' },
    animation: 'drift-a',
    systemId: 'SYS.042',
  },
  {
    id: 'f2',
    origin: '上海', destination: '大理',
    price: 560, signal: '符合心理价位',
    gradient: 'linear-gradient(135deg, #8B5CF6, #C4B5FD)',
    position: { top: '8%', right: '4%' },
    animation: 'drift-b',
    systemId: 'SYS.117',
  },
  {
    id: 'f3',
    origin: '广州', destination: '成都',
    price: 320, signal: '历史新低',
    gradient: 'linear-gradient(135deg, #10B981, #6EE7B7)',
    position: { bottom: '14%', left: '4%' },
    animation: 'drift-c',
    systemId: 'SYS.208',
  },
  {
    id: 'f4',
    origin: '北京', destination: '厦门',
    price: 480, signal: '假期前低价',
    gradient: 'linear-gradient(135deg, #F59E0B, #FCD34D)',
    position: { bottom: '10%', right: '4%' },
    animation: 'drift-d',
    systemId: 'SYS.334',
  },
]

const suggestions = ['五一三亚，预算600', '北京上海随时', '下周末成都', '暑假带娃出行']

export default function ChatPage() {
  const [query, setQuery] = useState('')
  const router = useRouter()

  const handleSearch = () => {
    if (query.trim()) router.push('/explore')
  }

  return (
    <div className="min-h-screen bg-bg-gray relative overflow-hidden font-sans">

      {/* ── NAV ────────────────────────────────────────── */}
      <nav className="absolute top-0 left-0 right-0 z-20 flex items-center justify-between px-8 py-6">
        <Link href="/" className="flex items-center gap-2 group">
          <div className="w-4 h-4 rounded-full bg-navy group-hover:scale-110 transition-transform" />
          <span className="font-mono text-[11px] tracking-[0.18em] text-navy/35 uppercase group-hover:text-navy/60 transition-colors">
            FareSniper
          </span>
        </Link>
        <div className="flex items-center gap-6">
          <Link href="/memory" className="text-sm text-gray-400 hover:text-navy transition-colors">
            我的记忆
          </Link>
          <Link
            href="/explore"
            className="text-sm bg-navy text-white px-4 py-2 rounded-xl hover:bg-navy-light transition-colors"
          >
            探索特价
          </Link>
        </div>
      </nav>

      {/* ── FLOATING DEAL CARDS (background layer) ─────── */}
      {floatingCards.map((card) => (
        <div
          key={card.id}
          className={`absolute z-0 pointer-events-none animate-${card.animation}`}
          style={card.position as React.CSSProperties}
        >
          <div className="bg-white rounded-2xl shadow-card overflow-hidden w-[168px] opacity-80">
            {/* Gradient image */}
            <div
              className="h-[72px] relative"
              style={{ background: card.gradient }}
            >
              <span className="absolute top-2 right-2.5 font-mono text-[9px] text-white/50">
                {card.systemId}
              </span>
            </div>
            {/* Card body */}
            <div className="px-3.5 py-3">
              <p className="text-navy text-[11px] font-medium mb-1 truncate">
                {card.origin} → {card.destination}
              </p>
              <p className="font-heading text-[1.4rem] font-bold text-navy leading-none mb-2">
                ¥{card.price}
              </p>
              <span className="inline-block bg-signal-muted text-signal-text text-[10px] font-medium px-2 py-0.5 rounded-full">
                {card.signal}
              </span>
            </div>
          </div>
        </div>
      ))}

      {/* ── CENTER CONTENT ─────────────────────────────── */}
      <div className="relative z-10 min-h-screen flex flex-col items-center justify-center px-6">
        <div className="w-full max-w-[520px] text-center">

          {/* Live count badge */}
          <div className="inline-flex items-center gap-2 bg-white border border-gray-100 shadow-sm text-gray-400 text-xs px-3.5 py-1.5 rounded-full mb-8">
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-signal opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-signal" />
            </span>
            今日监测到 <strong className="text-navy mx-0.5">12</strong> 个异常低价
          </div>

          {/* Main question */}
          <h1 className="font-heading text-[4rem] font-bold text-navy leading-[1.1] mb-3 tracking-tight">
            想去哪？
          </h1>
          <p className="text-gray-400 text-base mb-8 leading-relaxed">
            用自然语言告诉我，我来判断值不值得买
          </p>

          {/* Search input */}
          <div className="relative bg-white rounded-2xl shadow-card border border-gray-100/80 flex items-center gap-2 pl-5 pr-1.5 py-1.5 focus-within:border-navy/25 focus-within:shadow-card-hover transition-all duration-300">
            <svg className="w-4 h-4 text-gray-300 flex-shrink-0" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="6.5" cy="6.5" r="4.5" />
              <path d="M10.5 10.5L14 14" strokeLinecap="round" />
            </svg>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="比如：五一去三亚，预算 600"
              className="flex-1 py-3 bg-transparent text-navy placeholder-gray-300 text-[0.95rem] font-sans outline-none"
              autoFocus
            />
            <button
              onClick={handleSearch}
              className="flex-shrink-0 bg-navy hover:bg-navy-light text-white text-sm font-medium px-5 py-3 rounded-xl flex items-center gap-2 transition-all duration-200 hover:shadow-md"
            >
              分析
              <svg className="w-3.5 h-3.5" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 7h10M8 3l4 4-4 4" />
              </svg>
            </button>
          </div>

          {/* Quick suggestion pills */}
          <div className="flex flex-wrap justify-center gap-2 mt-4">
            {suggestions.map((s) => (
              <button
                key={s}
                onClick={() => setQuery(s)}
                className="bg-white/80 border border-gray-100 shadow-sm text-gray-400 text-xs px-3.5 py-2 rounded-full hover:border-navy/20 hover:text-navy hover:bg-white hover:shadow-card transition-all duration-200"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
