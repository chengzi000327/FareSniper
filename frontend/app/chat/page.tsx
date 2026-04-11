'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { DEFAULT_USER_ID, searchFlights } from '@/lib/api-client'

const suggestions = ['五一去三亚，预算600', '北京上海随时', '下周末成都', '暑假带娃出行']

const menuItems = [
  { href: '/chat', label: 'chat', active: true },
  { href: '/explore', label: 'explore', active: false },
  { href: '/memory', label: 'memory', active: false },
]

export default function ChatPage() {
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  const handleSearch = async () => {
    const trimmedQuery = query.trim()
    if (!trimmedQuery || loading) return

    setLoading(true)
    setError('')

    try {
      const result = await searchFlights(trimmedQuery, DEFAULT_USER_ID)
      window.sessionStorage.setItem('faresniper:last-search', JSON.stringify(result))
      router.push(`/explore?q=${encodeURIComponent(trimmedQuery)}`)
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : '搜索失败，请确认后端已启动')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#fdfefe] font-sans text-navy">
      <div className="flex min-h-screen">
        <aside className="flex w-[220px] flex-col border-r border-[#e6e9ef] bg-white/75 px-5 py-6 backdrop-blur-sm">
          <Link href="/" className="flex items-center gap-3">
            <div className="h-4 w-4 rounded-full bg-navy" />
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-navy/38">
                FareSniper
              </p>
              <p className="text-xs text-navy/54">
                flight deals desk
              </p>
            </div>
          </Link>

          <nav className="mt-10 flex flex-col gap-2">
            {menuItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-2xl px-4 py-3 text-sm font-medium capitalize transition-all duration-200 ${
                  item.active
                    ? 'bg-navy text-white shadow-[0_12px_24px_rgba(27,43,94,0.14)]'
                    : 'text-navy/52 hover:bg-navy/[0.04] hover:text-navy'
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="mt-auto rounded-3xl border border-[#eceef3] bg-[#fafbfc] px-4 py-4">
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-navy/28">
              workspace
            </p>
            <p className="mt-2 text-sm leading-relaxed text-navy/56">
              从这里开始搜索、探索特价，或者直接管理你的偏好记忆。
            </p>
          </div>
        </aside>

        <main className="relative flex flex-1 flex-col overflow-hidden">
          <div className="pointer-events-none absolute inset-0">
            <div className="absolute left-[14%] top-[14%] h-[240px] w-[240px] rounded-full bg-[#e8eef7]/58 blur-3xl" />
            <div className="absolute right-[10%] top-[18%] h-[220px] w-[220px] rounded-full bg-[#e7f1ec]/42 blur-3xl" />
            <div className="absolute bottom-[16%] left-[32%] h-[260px] w-[260px] rounded-full bg-[#f1f3f8]/80 blur-3xl" />
          </div>

          <div className="relative z-10 flex items-center justify-between px-8 py-6">
            <div className="rounded-full border border-[#e8ebf2] bg-white/85 px-3 py-1.5 text-xs text-navy/48 shadow-sm">
              Chat Workspace
            </div>
            <div className="rounded-full border border-[#e8ebf2] bg-white/85 px-3 py-1.5 text-xs text-navy/48 shadow-sm">
              Default view: chat
            </div>
          </div>

          <div className="relative z-10 flex flex-1 items-center justify-center px-8 pb-12">
            <div className="w-full max-w-[760px]">
              <div className="text-center">
                <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-[#9fd8af] bg-[#dff4e4]/85 px-3.5 py-1.5 text-xs font-medium text-signal-text shadow-[0_10px_30px_rgba(34,197,94,0.08)]">
                  <span className="relative flex h-1.5 w-1.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-signal opacity-75" />
                    <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-signal" />
                  </span>
                  今日监测到 <strong className="mx-0.5 text-navy">12</strong> 个异常低价
                </div>

                <h1 className="font-heading text-[4.4rem] font-bold leading-[1.02] tracking-tight text-navy">
                  想去哪？
                </h1>
                <p className="mx-auto mt-4 max-w-[560px] text-lg leading-relaxed text-navy/46">
                  用自然语言告诉我你的目的地、时间和预算，我来帮你判断值不值得买。
                </p>
              </div>

              <div className="mt-10 rounded-[28px] border border-[#e9edf3] bg-white/92 p-5 shadow-[0_24px_60px_rgba(27,43,94,0.08)] backdrop-blur-sm">
                <textarea
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault()
                      void handleSearch()
                    }
                  }}
                  placeholder="比如：五一去三亚，预算 600；或者北京出发，下周末找便宜一点的海边航线"
                  className="min-h-[140px] w-full resize-none bg-transparent px-2 py-1 text-[1.05rem] leading-relaxed text-navy placeholder:text-[#b2b8c8] outline-none"
                />

                <div className="mt-4 flex items-center justify-between gap-4 border-t border-[#eef1f6] pt-4">
                  <div className="rounded-full border border-[#edf0f5] bg-[#fafbfd] px-3 py-1.5 text-xs text-navy/44">
                    Search over: FareSniper deals
                  </div>
                  <button
                    onClick={() => void handleSearch()}
                    disabled={loading}
                    className="flex items-center gap-2 rounded-2xl bg-navy px-5 py-3 text-sm font-semibold text-white transition-all duration-200 hover:bg-[#24366f] hover:shadow-[0_14px_30px_rgba(27,43,94,0.16)] disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {loading ? '分析中...' : '分析'}
                    {!loading && (
                      <svg className="h-3.5 w-3.5" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M2 7h10M8 3l4 4-4 4" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              {error && (
                <p className="mt-4 text-center text-sm text-red-500">
                  {error}
                </p>
              )}

              <div className="mt-5 flex flex-wrap justify-center gap-3">
                {suggestions.map((item) => (
                  <button
                    key={item}
                    onClick={() => setQuery(item)}
                    className="rounded-full border border-[#e8ebf2] bg-white/88 px-4 py-2 text-sm text-navy/54 shadow-sm transition-all duration-200 hover:border-navy/16 hover:text-navy hover:shadow-md"
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
