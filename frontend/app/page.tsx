'use client'

import { useState } from 'react'
import Link from 'next/link'

// Inline mock for the missed deal preview card
const missedDeal = {
  origin: '北京', destination: '三亚',
  price: 398, originalPrice: 980,
  airline: '海南航空', departDate: '2026-05-01',
  departTime: '07:30', arriveTime: '13:45',
  signals: ['近90天低位', '五一低价'],
  systemId: 'SYS.042',
  discount: 59,
}

const avatarColors = ['#1B2B5E', '#22C55E', '#F59E0B', '#8B5CF6']

export default function LoginPage() {
  const [loading, setLoading] = useState(false)

  const handleLogin = () => {
    setLoading(true)
    setTimeout(() => { window.location.href = '/chat' }, 900)
  }

  return (
    <div className="min-h-screen flex bg-bg-gray overflow-hidden font-sans">

      {/* ── LEFT PANEL ─────────────────────────────────── */}
      <div className="flex-1 flex flex-col justify-center px-14 py-12 relative">

        {/* Brand mark */}
        <div className="absolute top-8 left-14 flex items-center gap-2">
          <div className="w-5 h-5 rounded-full bg-navy" />
          <span className="font-mono text-xs tracking-[0.18em] text-navy/40 uppercase">
            FareSniper
          </span>
        </div>

        <div className="max-w-[420px]">
          {/* Live badge */}
          <div className="inline-flex items-center gap-2 bg-signal-muted border border-signal/20 text-signal-text text-xs font-medium px-3 py-1.5 rounded-full mb-8">
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-signal opacity-75" />
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-signal" />
            </span>
            实时监测中 · 今日发现 12 个特价
          </div>

          {/* Headline */}
          <h1 className="font-heading text-[3.6rem] font-bold leading-[1.08] text-navy tracking-tight mb-5">
            好机票，<br />
            <span className="italic font-heading text-navy/60">不等人。</span>
          </h1>

          <p className="text-gray-400 text-[1.05rem] leading-relaxed mb-10">
            AI 实时监测 3 亿+ 价格数据，<br />
            只在真正值得买的时候告诉你。
          </p>

          {/* WeChat CTA */}
          <button
            onClick={handleLogin}
            disabled={loading}
            className="w-full bg-[#07C160] hover:bg-[#06AD56] active:bg-[#059447] text-white font-semibold text-[0.95rem] py-[14px] rounded-2xl flex items-center justify-center gap-2.5 transition-all duration-200 hover:shadow-lg hover:shadow-[#07C160]/30 disabled:opacity-70 disabled:cursor-not-allowed"
          >
            {loading ? (
              <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.539c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178A1.17 1.17 0 0 1 4.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178 1.17 1.17 0 0 1-1.162-1.178c0-.651.52-1.18 1.162-1.18zm9.266 6.658c-3.763 0-6.813 2.507-6.813 5.601 0 3.094 3.05 5.601 6.813 5.601a7.93 7.93 0 0 0 2.27-.325.688.688 0 0 1 .574.079l1.507.882a.26.26 0 0 0 .132.043c.126 0 .231-.105.231-.234 0-.056-.023-.112-.039-.168l-.31-1.175a.468.468 0 0 1 .169-.529C23.087 20.561 24 19.019 24 17.25c0-3.094-3.05-5.601-6.136-5.601zm-3.624 3.084a.932.932 0 0 1 0 1.864.932.932 0 0 1 0-1.864zm3.552 0a.932.932 0 0 1 0 1.864.932.932 0 0 1 0-1.864z"/>
              </svg>
            )}
            {loading ? '正在登录...' : '微信一键登录'}
          </button>

          {/* Divider */}
          <div className="flex items-center gap-3 my-4">
            <div className="flex-1 h-px bg-gray-200" />
            <span className="text-gray-300 text-xs">或者</span>
            <div className="flex-1 h-px bg-gray-200" />
          </div>

          {/* Phone login */}
          <Link
            href="/chat"
            className="w-full block text-center border border-navy/15 text-navy/60 text-sm py-3.5 rounded-2xl hover:border-navy/30 hover:text-navy hover:bg-navy/[0.03] transition-all duration-200"
          >
            手机号登录
          </Link>

          {/* Social proof */}
          <div className="flex items-center gap-3 mt-10 pt-8 border-t border-gray-100">
            <div className="flex -space-x-2">
              {avatarColors.map((color, i) => (
                <div
                  key={i}
                  className="w-7 h-7 rounded-full border-2 border-white flex items-center justify-center text-white text-[10px] font-bold"
                  style={{ backgroundColor: color }}
                >
                  {['赵','钱','孙','李'][i]}
                </div>
              ))}
            </div>
            <p className="text-gray-400 text-sm">
              已帮助 <strong className="text-navy font-semibold">12,847</strong> 人省下机票钱
            </p>
          </div>
        </div>
      </div>

      {/* ── RIGHT PANEL ────────────────────────────────── */}
      <div className="w-[46%] bg-navy/[0.04] grain-overlay flex flex-col items-center justify-center relative overflow-hidden">

        {/* Decorative blobs */}
        <div className="absolute top-1/3 right-[-80px] w-72 h-72 rounded-full bg-signal/8 blur-3xl pointer-events-none" />
        <div className="absolute bottom-1/4 left-[-60px] w-56 h-56 rounded-full bg-navy/6 blur-3xl pointer-events-none" />

        {/* Caption */}
        <p className="font-mono text-[11px] tracking-[0.2em] text-gray-300 uppercase mb-5">
          你上次搜索后可能错过的
        </p>

        {/* Deal Card */}
        <div className="relative w-[300px] group">
          {/* Shadow card behind */}
          <div className="absolute inset-0 bg-navy/8 rounded-3xl translate-x-3 translate-y-3 transition-transform duration-500 group-hover:translate-x-5 group-hover:translate-y-5" />

          {/* Main card */}
          <div className="relative bg-white rounded-3xl p-6 shadow-card-float rotate-[3deg] group-hover:rotate-0 transition-all duration-500 cursor-default no-select">

            {/* Card top row */}
            <div className="flex items-start justify-between mb-5">
              <div>
                <p className="font-mono text-[10px] text-gray-300 mb-1">{missedDeal.systemId}</p>
                <p className="font-heading text-[1.1rem] font-bold text-navy leading-tight">
                  {missedDeal.origin} → {missedDeal.destination}
                </p>
                <p className="text-gray-400 text-xs mt-0.5">
                  {missedDeal.airline} · {missedDeal.departDate}
                </p>
              </div>
              <div className="text-right">
                <p className="text-gray-300 text-xs line-through mb-0.5">¥{missedDeal.originalPrice}</p>
                <p className="font-heading text-[2.2rem] font-bold text-navy leading-none">
                  ¥{missedDeal.price}
                </p>
                <p className="text-signal text-xs font-medium mt-0.5">-{missedDeal.discount}%</p>
              </div>
            </div>

            {/* Flight timeline */}
            <div className="flex items-center gap-2 py-3.5 px-1 border-y border-gray-50 mb-4">
              <span className="text-navy text-sm font-semibold tabular-nums">{missedDeal.departTime}</span>
              <div className="flex-1 relative flex items-center">
                <div className="flex-1 h-px bg-gray-100" />
                <div className="mx-2 text-gray-300">
                  <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M9.293 1.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L11.586 7H3a1 1 0 110-2h8.586L9.293 2.707a1 1 0 010-1.414z"/>
                  </svg>
                </div>
                <div className="flex-1 h-px bg-gray-100" />
              </div>
              <span className="text-navy text-sm font-semibold tabular-nums">{missedDeal.arriveTime}</span>
            </div>

            {/* Signal tags */}
            <div className="flex flex-wrap gap-1.5 mb-4">
              {missedDeal.signals.map((s) => (
                <span
                  key={s}
                  className="bg-signal-muted text-signal-text text-[11px] font-medium px-2.5 py-1 rounded-full"
                >
                  {s}
                </span>
              ))}
            </div>

            {/* AI verdict bar */}
            <div className="bg-navy rounded-2xl px-4 py-3 flex items-center justify-between">
              <span className="text-white/50 text-xs font-mono">AI 判断</span>
              <div className="flex items-center gap-1.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-signal opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-signal" />
                </span>
                <span className="text-white text-sm font-semibold">建议现在买</span>
              </div>
            </div>
          </div>
        </div>

        <p className="mt-7 text-gray-300 text-xs text-center">
          登录后查看今日全部特价 →
        </p>
      </div>
    </div>
  )
}
