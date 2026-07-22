'use client'

import React from 'react'
import {
  Bell,
  BookHeart,
  ChevronRight,
  Compass,
  Heart,
  MapPin,
  MessageCircle,
  Plane,
  Search,
  Send,
  Sparkles,
  UserRound,
} from 'lucide-react'
import { ChatPage } from '@/components/chat-page'
import { MemoryPage } from '@/components/memory-page'
import { formatCurrency } from '@/lib/currency'
import { memoryApi, recApi } from '@/lib/api'
import type { MemoryItemDto, QueryHistoryItemDto, RecCardDto } from '@/lib/api'

type MobileTab = 'explore' | 'chat' | 'memory' | 'profile'

type MobileMemory = {
  memories: MemoryItemDto[]
  query_history: QueryHistoryItemDto[]
}

type CompanionKind = 'cat' | 'corgi' | 'penguin' | 'plain'

const COMPANION_ASSETS: Record<Exclude<CompanionKind, 'plain'>, string> = {
  cat: '/companions/cloud-cat-actions.png',
  corgi: '/companions/boarding-corgi-actions.png',
  penguin: '/companions/migratory-penguin-actions.png',
}

const COMPANION_DEFAULTS: Record<CompanionKind, string> = {
  cat: '云朵',
  corgi: '登登',
  penguin: '小候',
  plain: '旅伴',
}

const INTERNAL_MEMORY_FIELDS = new Set(['companion_profile', 'travel_ideas'])

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function companionFromMemory(memories: MemoryItemDto[]) {
  const raw = memories.find((memory) => memory.field === 'companion_profile')?.value
  const profile = asRecord(raw)
  const kind = profile?.kind
  const selectedKind: CompanionKind = kind === 'corgi' || kind === 'penguin' || kind === 'plain' ? kind : 'cat'
  const name = typeof profile?.name === 'string' && profile.name.trim()
    ? profile.name.trim()
    : COMPANION_DEFAULTS[selectedKind]
  return { kind: selectedKind, name }
}

function explicitIdeaCount(memories: MemoryItemDto[]) {
  const value = memories.find((memory) => memory.field === 'travel_ideas')?.value
  return Array.isArray(value) ? value.length : 0
}

function MobileCompanion({ kind }: { kind: CompanionKind }) {
  if (kind === 'plain') {
    return (
      <div className="grid aspect-square w-full place-items-center rounded-[32px] bg-brand-text text-white">
        <Sparkles className="h-8 w-8" />
      </div>
    )
  }
  return (
    <div className="relative aspect-square w-full overflow-hidden rounded-[32px] bg-[#fffaf1]">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={COMPANION_ASSETS[kind]} alt="查价旅伴" className="pointer-events-none absolute left-0 top-0 h-[200%] w-[300%] max-w-none select-none" />
    </div>
  )
}

function recommendationTitle(card: RecCardDto) {
  if (card.preview_deal) {
    return `${card.preview_deal.origin_city} → ${card.preview_deal.destination_city}`
  }
  return card.title?.trim() || '新的航线发现'
}

function recommendationPrice(card: RecCardDto) {
  const deal = card.preview_deal
  if (!deal) return '查询实时价格'
  return formatCurrency(deal.total_price ?? deal.price, deal.currency)
}

export function MobileAppPage() {
  const [activeTab, setActiveTab] = React.useState<MobileTab>('explore')
  const [chatQuery, setChatQuery] = React.useState<string | null>(null)
  const [memory, setMemory] = React.useState<MobileMemory>({ memories: [], query_history: [] })
  const [recommendations, setRecommendations] = React.useState<RecCardDto[]>([])
  const [loading, setLoading] = React.useState(true)

  React.useEffect(() => {
    let active = true
    Promise.allSettled([
      memoryApi.get(),
      recApi.list({ limit: 4, offset: 0 }),
    ]).then(([memoryResult, recommendationResult]) => {
      if (!active) return
      if (memoryResult.status === 'fulfilled') {
        setMemory({
          memories: memoryResult.value.memories ?? [],
          query_history: memoryResult.value.query_history ?? [],
        })
      }
      if (recommendationResult.status === 'fulfilled') {
        setRecommendations(recommendationResult.value.cards ?? [])
      }
      setLoading(false)
    })
    return () => { active = false }
  }, [])

  const startChat = (query: string) => {
    const value = query.trim()
    if (!value) return
    setChatQuery(value)
    setActiveTab('chat')
  }

  return (
    <div className="min-h-[100dvh] bg-[#eadfd4] sm:grid sm:place-items-center sm:p-4">
      <main className="relative flex h-[100dvh] w-full flex-col overflow-hidden bg-brand-bg sm:h-[min(52rem,calc(100dvh-2rem))] sm:max-w-[430px] sm:rounded-[38px] sm:border-[7px] sm:border-brand-text sm:shadow-[0_30px_90px_rgba(67,44,27,0.28)]">
        <div className="min-h-0 flex-1 overflow-hidden">
          {activeTab === 'explore' ? (
            <MobileExploreHome
              loading={loading}
              memory={memory}
              recommendations={recommendations}
              onSearch={startChat}
              onOpenMemory={() => setActiveTab('memory')}
            />
          ) : activeTab === 'chat' ? (
            <ChatPage initialQuery={chatQuery} onInitialQueryConsumed={() => setChatQuery(null)} />
          ) : activeTab === 'memory' ? (
            <MemoryPage />
          ) : (
            <MobileProfile memory={memory} onOpenMemory={() => setActiveTab('memory')} onOpenChat={() => setActiveTab('chat')} />
          )}
        </div>

        <MobileBottomNav activeTab={activeTab} onChange={setActiveTab} />
      </main>
    </div>
  )
}

function MobileExploreHome({
  loading,
  memory,
  recommendations,
  onSearch,
  onOpenMemory,
}: {
  loading: boolean
  memory: MobileMemory
  recommendations: RecCardDto[]
  onSearch: (query: string) => void
  onOpenMemory: () => void
}) {
  const [query, setQuery] = React.useState('')
  const companion = companionFromMemory(memory.memories)
  const preferenceCount = memory.memories.filter((item) => !INTERNAL_MEMORY_FIELDS.has(item.field)).length
  const ideaCount = explicitIdeaCount(memory.memories)

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    onSearch(query)
  }

  return (
    <div className="thin-scrollbar h-full overflow-y-auto px-5 pb-8 pt-[max(1.25rem,env(safe-area-inset-top))]">
      <header className="flex items-center justify-between">
        <div>
          <div className="text-[11px] font-black tracking-[0.2em] text-brand-orange">特价机票发现</div>
          <h1 className="mt-1 font-serif text-3xl font-black text-brand-text">今天想去哪儿？</h1>
        </div>
        <button type="button" aria-label="查看提醒" className="grid h-11 w-11 place-items-center rounded-2xl border border-brand-text/8 bg-white text-brand-text shadow-sm">
          <Bell className="h-5 w-5" />
        </button>
      </header>

      <section className="relative mt-5 overflow-hidden rounded-[30px] bg-brand-text p-5 text-white shadow-card">
        <div className="absolute -right-8 -top-10 h-36 w-36 rounded-full bg-brand-orange/35 blur-2xl" />
        <div className="relative grid grid-cols-[minmax(0,1fr)_5.5rem] items-center gap-4">
          <div>
            <div className="text-xs font-bold text-white/65">你的查价旅伴</div>
            <h2 className="mt-1 text-2xl font-black">{companion.name} 在陪你找低价</h2>
            <p className="mt-2 text-xs leading-6 text-white/70">记住真实偏好，但不会把一次搜索当成长期意愿。</p>
          </div>
          <MobileCompanion kind={companion.kind} />
        </div>
        <div className="relative mt-4 flex gap-2 text-[11px] font-bold text-white/75">
          <span className="rounded-full bg-white/10 px-3 py-1.5">{preferenceCount} 项偏好</span>
          <span className="rounded-full bg-white/10 px-3 py-1.5">{ideaCount} 个明确关注</span>
          <span className="rounded-full bg-white/10 px-3 py-1.5">{memory.query_history.length} 次查询</span>
        </div>
      </section>

      <form onSubmit={submit} className="mt-5 rounded-[28px] border border-brand-orange/15 bg-white p-4 shadow-[0_18px_50px_-32px_rgba(67,44,27,0.35)]">
        <label htmlFor="mobile-flight-query" className="flex items-center gap-2 text-xs font-black text-brand-orange">
          <Search className="h-4 w-4" />
          用一句话告诉我出发计划
        </label>
        <div className="mt-3 flex items-center gap-2">
          <input
            id="mobile-flight-query"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="例如：下周五上海去三亚，预算 800"
            className="min-w-0 flex-1 bg-transparent py-2 text-sm font-semibold text-brand-text placeholder:font-normal placeholder:text-brand-muted/65"
          />
          <button type="submit" aria-label="开始查询" disabled={!query.trim()} className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-brand-orange text-white disabled:opacity-35">
            <Send className="h-5 w-5" />
          </button>
        </div>
      </form>

      <section className="mt-7">
        <div className="flex items-end justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold text-brand-orange"><Compass className="h-4 w-4" />真实推荐</div>
            <h2 className="mt-1 text-xl font-black text-brand-text">值得查一查</h2>
          </div>
          <span className="text-xs font-semibold text-brand-muted">价格以预订页为准</span>
        </div>

        <div className="mt-4 space-y-3">
          {loading ? (
            [0, 1].map((item) => <div key={item} className="h-28 animate-pulse rounded-[24px] bg-white/70" />)
          ) : recommendations.length ? (
            recommendations.slice(0, 3).map((card, index) => (
              <button
                key={card.id ?? `${recommendationTitle(card)}-${index}`}
                type="button"
                onClick={() => onSearch(card.query_hint || `查询${recommendationTitle(card)}的机票`)}
                className="flex w-full items-center gap-4 rounded-[24px] border border-brand-text/7 bg-white p-4 text-left shadow-sm transition active:scale-[0.99]"
              >
                <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-brand-orange-light text-brand-orange"><Plane className="h-5 w-5" /></div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-base font-black text-brand-text">{recommendationTitle(card)}</div>
                  <div className="mt-1 truncate text-xs text-brand-muted">{card.reason || '进入对话获取最新可售结果'}</div>
                </div>
                <div className="text-right">
                  <div className="whitespace-nowrap text-sm font-black text-brand-orange">{recommendationPrice(card)}</div>
                  <ChevronRight className="ml-auto mt-2 h-4 w-4 text-brand-muted" />
                </div>
              </button>
            ))
          ) : (
            <button type="button" onClick={() => onSearch('帮我看看最近有什么值得关注的特价机票')} className="flex w-full items-center gap-3 rounded-[24px] border border-dashed border-brand-text/12 bg-white/60 p-5 text-left">
              <MapPin className="h-5 w-5 text-brand-orange" />
              <span className="text-sm font-semibold leading-6 text-brand-muted">还没有可展示的真实推荐，发起一次查询看看。</span>
              <ChevronRight className="ml-auto h-4 w-4 text-brand-muted" />
            </button>
          )}
        </div>
      </section>

      <button type="button" onClick={onOpenMemory} className="mt-7 flex w-full items-center gap-4 rounded-[26px] bg-[#fff0dc] p-5 text-left">
        <div className="grid h-12 w-12 place-items-center rounded-2xl bg-white text-brand-orange"><BookHeart className="h-5 w-5" /></div>
        <div className="min-w-0 flex-1">
          <div className="text-base font-black text-brand-text">看看它记住了什么</div>
          <div className="mt-1 text-xs leading-5 text-brand-muted">偏好可以修改；明确关注、最近查询和旅行手帐彼此分开。</div>
        </div>
        <ChevronRight className="h-5 w-5 text-brand-muted" />
      </button>
    </div>
  )
}

function MobileProfile({
  memory,
  onOpenMemory,
  onOpenChat,
}: {
  memory: MobileMemory
  onOpenMemory: () => void
  onOpenChat: () => void
}) {
  const companion = companionFromMemory(memory.memories)
  return (
    <div className="thin-scrollbar h-full overflow-y-auto px-5 pb-8 pt-[max(1.25rem,env(safe-area-inset-top))]">
      <div className="text-[11px] font-black tracking-[0.2em] text-brand-orange">我的发现台</div>
      <h1 className="mt-1 font-serif text-3xl font-black text-brand-text">我的</h1>

      <section className="mt-6 flex items-center gap-4 rounded-[28px] bg-white p-5 shadow-sm">
        <div className="w-20 shrink-0"><MobileCompanion kind={companion.kind} /></div>
        <div>
          <div className="text-xs font-bold text-brand-orange">当前旅伴</div>
          <div className="mt-1 text-xl font-black text-brand-text">{companion.name}</div>
          <div className="mt-1 text-xs leading-5 text-brand-muted">负责呈现记忆与提醒，不替你做购买决定。</div>
        </div>
      </section>

      <div className="mt-5 space-y-3">
        <ProfileRow icon={<Heart />} title="管理机票偏好" detail="添加、修改或忘记预算和出行习惯" onClick={onOpenMemory} />
        <ProfileRow icon={<BookHeart />} title="查看旅行手帐" detail="确认成行后才会写入真实旅行" onClick={onOpenMemory} />
        <ProfileRow icon={<MessageCircle />} title="继续查票对话" detail="接着当前上下文补充时间和条件" onClick={onOpenChat} />
        <ProfileRow icon={<Bell />} title="价格提醒" detail="只在真实目标价命中时提醒" />
      </div>
    </div>
  )
}

function ProfileRow({ icon, title, detail, onClick }: { icon: React.ReactElement; title: string; detail: string; onClick?: () => void }) {
  return (
    <button type="button" onClick={onClick} className="flex w-full items-center gap-4 rounded-[22px] border border-brand-text/7 bg-white p-4 text-left">
      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-brand-orange-light text-brand-orange [&>svg]:h-4 [&>svg]:w-4">{icon}</div>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-black text-brand-text">{title}</div>
        <div className="mt-1 text-xs leading-5 text-brand-muted">{detail}</div>
      </div>
      <ChevronRight className="h-4 w-4 text-brand-muted" />
    </button>
  )
}

function MobileBottomNav({ activeTab, onChange }: { activeTab: MobileTab; onChange: (tab: MobileTab) => void }) {
  const items: Array<{ id: MobileTab; label: string; icon: React.ReactElement }> = [
    { id: 'explore', label: '探索', icon: <Compass /> },
    { id: 'chat', label: '对话', icon: <MessageCircle /> },
    { id: 'memory', label: '记忆', icon: <BookHeart /> },
    { id: 'profile', label: '我的', icon: <UserRound /> },
  ]
  return (
    <nav aria-label="手机端主导航" className="z-30 grid shrink-0 grid-cols-4 border-t border-brand-text/8 bg-white/95 px-3 pb-[max(0.65rem,env(safe-area-inset-bottom))] pt-2 backdrop-blur-xl">
      {items.map((item) => {
        const active = item.id === activeTab
        return (
          <button key={item.id} type="button" aria-label={item.label} aria-pressed={active} onClick={() => onChange(item.id)} className={`flex min-h-12 flex-col items-center justify-center gap-1 rounded-2xl text-[11px] font-bold transition [&>svg]:h-5 [&>svg]:w-5 ${active ? 'bg-brand-orange-light text-brand-orange' : 'text-brand-muted'}`}>
            {item.icon}
            {item.label}
          </button>
        )
      })}
    </nav>
  )
}

