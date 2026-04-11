'use client'

import { useEffect, useState } from 'react'
import { DEFAULT_USER_ID, getRecommendationDeals } from '@/lib/api-client'
import { hotDeals, missedDeal as mockMissedDeal } from '@/lib/mocks'
import type { FlightDeal } from '@/types'

const avatarColors = ['#1B2B5E', '#22C55E', '#F59E0B', '#8B5CF6']
const cardOffsets = ['-rotate-[6deg] -translate-y-2', 'rotate-0', 'rotate-[6deg] translate-y-2']

export default function LoginPage() {
  const [loading, setLoading] = useState(false)
  const [heroDeals, setHeroDeals] = useState<FlightDeal[]>([mockMissedDeal, ...hotDeals.slice(1, 3)])

  useEffect(() => {
    let mounted = true

    getRecommendationDeals(DEFAULT_USER_ID)
      .then((deals) => {
        if (mounted && deals.length > 0) {
          setHeroDeals(deals.slice(0, 3))
        }
      })
      .catch(() => {
        if (mounted) {
          setHeroDeals([mockMissedDeal, ...hotDeals.slice(1, 3)])
        }
      })

    return () => {
      mounted = false
    }
  }, [])

  const handleLogin = () => {
    setLoading(true)
    setTimeout(() => { window.location.href = '/chat' }, 900)
  }

  return (
    <div className="min-h-screen overflow-hidden bg-[#fdfefe] font-sans text-navy">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-[-10%] top-[-8%] h-[340px] w-[340px] rounded-full bg-[#e7f1ec]/55 blur-3xl" />
        <div className="absolute bottom-[-10%] left-[18%] h-[280px] w-[280px] rounded-full bg-[#eef3f8]/75 blur-3xl" />
        <div className="absolute right-[-8%] top-[10%] h-[420px] w-[420px] rounded-full bg-[#e8eef7]/55 blur-3xl" />
        <div className="absolute right-[18%] top-[30%] h-[260px] w-[260px] rounded-full bg-[#edf5f0]/45 blur-3xl" />
      </div>

      <div className="relative flex min-h-screen overflow-hidden">

        {/* ── LEFT PANEL ─────────────────────────────────── */}
        <div className="relative flex flex-1 flex-col items-center justify-center px-14 py-12">

          {/* Brand mark */}
          <div className="absolute left-14 top-8 flex max-w-[560px] items-start gap-4">
            <div className="mt-1.5 h-5 w-5 flex-shrink-0 rounded-full bg-navy" />
            <div className="text-left">
              <p className="text-[0.95rem] font-semibold tracking-[0.02em] text-navy/88">
                特价机票发现平台：懂你的航线才叫真特价。
              </p>
              <p className="mt-1 font-mono text-[11px] tracking-[0.12em] text-navy/42">
                FareSniper: I remenber your dreams, so I track your deals
              </p>
            </div>
          </div>

          <div className="flex max-w-[520px] flex-col items-center text-center">
            {/* Live badge */}
            <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-[#9fd8af] bg-[#dff4e4]/85 px-3 py-1.5 text-xs font-medium text-signal-text shadow-[0_10px_30px_rgba(34,197,94,0.08)]">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-signal opacity-75" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-signal" />
              </span>
              实时监测中 · 今日发现 12 个特价
            </div>

            {/* Headline */}
            <h1 className="mb-5 font-heading text-[3.9rem] font-bold leading-[1.04] tracking-tight text-navy">
              好机票，<br />
              <span className="italic font-heading text-[#6d7698]">不等人。</span>
            </h1>

            <p className="mb-10 text-[1.05rem] leading-relaxed text-[#7d859d]">
              AI 实时监测 3 亿+ 价格数据，<br />
              只在真正值得买的时候告诉你。
            </p>

            <button
              onClick={handleLogin}
              disabled={loading}
              className="flex w-full max-w-[640px] items-center justify-center gap-2.5 rounded-2xl bg-navy py-[15px] text-[0.98rem] font-semibold text-white transition-all duration-200 hover:-translate-y-0.5 hover:bg-[#24366f] hover:shadow-[0_18px_40px_rgba(27,43,94,0.18)] disabled:cursor-not-allowed disabled:opacity-70"
            >
              {loading ? (
                <span className="h-5 w-5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
              ) : (
                <svg className="h-4 w-4" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2 7h10M8 3l4 4-4 4" />
                </svg>
              )}
              {loading ? '正在进入...' : '开始发现特价机票'}
            </button>

            <p className="mt-4 max-w-[520px] text-sm leading-relaxed text-[#7d859d]">
              无需登录，先看看今天有哪些真正值得买的路线。
            </p>

            {/* Social proof */}
            <div className="mt-10 flex items-center gap-3 border-t border-[#d8d6cf] pt-8">
              <div className="flex -space-x-2">
                {avatarColors.map((color, i) => (
                  <div
                    key={i}
                    className="flex h-7 w-7 items-center justify-center rounded-full border-2 border-[#f7f4ee] text-[10px] font-bold text-white"
                    style={{ backgroundColor: color }}
                  >
                    {['赵', '钱', '孙', '李'][i]}
                  </div>
                ))}
              </div>
              <p className="text-sm text-[#7d859d]">
                已帮助 <strong className="font-semibold text-navy">12,847</strong> 人省下机票钱
              </p>
            </div>
          </div>
        </div>

        {/* ── RIGHT PANEL ────────────────────────────────── */}
        <div className="relative flex w-[50%] flex-col items-center justify-center overflow-visible bg-transparent">

          {/* Decorative blobs */}
          <div className="pointer-events-none absolute right-[-20px] top-[16%] h-64 w-64 rounded-full bg-[#e2eaf5]/28 blur-3xl" />
          <div className="pointer-events-none absolute bottom-[20%] left-[-20px] h-52 w-52 rounded-full bg-[#e7f2eb]/24 blur-3xl" />

          <div className="relative z-10 flex w-full max-w-[880px] -translate-x-8 -translate-y-6 flex-col items-center justify-center px-4">
            {/* Caption */}
            <div className="mb-8 text-center">
              <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.2em] text-navy/28">
                你上次搜索后可能错过的
              </p>
              <p className="text-sm text-navy/45">
                这次，不止给你一张票，而是一组值得看的机会。
              </p>
            </div>

            {/* Deal Card Row */}
            <div className="flex items-center justify-center gap-3">
              {heroDeals.slice(0, 3).map((deal, index) => {
                const discount = deal.originalPrice > deal.price
                  ? Math.round((1 - deal.price / deal.originalPrice) * 100)
                  : 0

                return (
                  <div
                    key={deal.id}
                    className={`group w-[236px] cursor-default rounded-[28px] border border-white/75 bg-white/94 p-4 shadow-[0_22px_60px_rgba(62,73,102,0.13)] backdrop-blur-md transition-all duration-500 ${cardOffsets[index] ?? ''} hover:-translate-y-1 hover:rotate-0`}
                  >
                    <div className="mb-4 flex items-start justify-between gap-3">
                      <div>
                        <p className="mb-1 font-mono text-[10px] text-gray-300">{deal.systemId}</p>
                        <p className="font-heading text-[0.95rem] font-bold leading-tight text-navy">
                          {deal.origin} → {deal.destination}
                        </p>
                        <p className="mt-0.5 text-xs text-gray-400">
                          {deal.airline} · {deal.departDate}
                        </p>
                      </div>
                      <div className="text-right">
                        {deal.originalPrice > deal.price && (
                          <p className="mb-0.5 text-xs text-gray-300 line-through">¥{deal.originalPrice}</p>
                        )}
                        <p className="font-heading text-[1.7rem] font-bold leading-none text-navy">
                          ¥{deal.price}
                        </p>
                        {discount > 0 && (
                          <p className="mt-0.5 text-xs font-medium text-signal">-{discount}%</p>
                        )}
                      </div>
                    </div>

                    <div className="mb-3 flex items-center gap-2 border-y border-gray-50 px-1 py-2.5">
                      <span className="text-[0.95rem] font-semibold tabular-nums text-navy">{deal.departTime}</span>
                      <div className="relative flex flex-1 items-center">
                        <div className="h-px flex-1 bg-gray-100" />
                        <div className="mx-2 text-gray-300">
                          <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="currentColor">
                            <path d="M9.293 1.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L11.586 7H3a1 1 0 110-2h8.586L9.293 2.707a1 1 0 010-1.414z"/>
                          </svg>
                        </div>
                        <div className="h-px flex-1 bg-gray-100" />
                      </div>
                      <span className="text-[0.95rem] font-semibold tabular-nums text-navy">{deal.arriveTime}</span>
                    </div>

                    <div className="mb-3 flex flex-wrap gap-1.5">
                      {deal.signals.slice(0, 2).map((signal) => (
                        <span
                          key={signal}
                          className="rounded-full bg-signal-muted px-2.5 py-1 text-[11px] font-medium text-signal-text"
                        >
                          {signal}
                        </span>
                      ))}
                    </div>

                    <div className="flex items-center justify-between rounded-2xl bg-navy px-3.5 py-2.5">
                      <span className="text-xs font-mono text-white/50">AI 判断</span>
                      <div className="flex items-center gap-1.5">
                        <span className="relative flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-signal opacity-75" />
                          <span className="relative inline-flex h-2 w-2 rounded-full bg-signal" />
                        </span>
                        <span className="text-[0.95rem] font-semibold text-white">{deal.verdict}</span>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            <p className="mt-10 text-center text-xs text-navy/34">
              进入后可继续查看今日全部特价 →
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
