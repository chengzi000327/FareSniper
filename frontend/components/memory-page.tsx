'use client'

import React from 'react'
import { motion } from 'motion/react'
import {
  BellRing,
  BookOpen,
  Check,
  ChevronRight,
  Clock3,
  Heart,
  Lightbulb,
  PencilLine,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Trash2,
} from 'lucide-react'
import { api, memoryApi } from '@/lib/api'
import type { MemoryItemDto, QueryHistoryItemDto } from '@/lib/api'

type LoadState = 'loading' | 'ready' | 'error'
type MemoryView = 'journal' | 'ideas' | 'remembered'
type CompanionKind = 'cat' | 'corgi' | 'penguin' | 'plain'
type CompanionPose = 'idle' | 'idea' | 'deal' | 'departure' | 'reminder' | 'journal'

type CompanionProfile = {
  kind: CompanionKind
  name: string
  proactivity: 'quiet' | 'standard' | 'active'
}

type TravelIdea = {
  id: string
  text: string
  created_at: string
}

type JournalEntry = {
  id: string
  date: string
  title: string
  detail: string
  source: '想法' | '查询'
}

type MemoryPayload = {
  memories: MemoryItemDto[]
  query_history: QueryHistoryItemDto[]
}

const COMPANIONS: Record<CompanionKind, {
  label: string
  defaultName: string
  personality: string
  description: string
  asset?: string
}> = {
  cat: {
    label: '云朵猫',
    defaultName: '云朵',
    personality: '安静 · 柔和',
    description: '只在真正重要的时候出现，适合轻柔陪伴。',
    asset: '/companions/cloud-cat-actions.png',
  },
  corgi: {
    label: '登机柯基',
    defaultName: '登登',
    personality: '热情 · 行动派',
    description: '更愿意告诉你下一步可以做什么，但不会替你决定。',
    asset: '/companions/boarding-corgi-actions.png',
  },
  penguin: {
    label: '候鸟企鹅',
    defaultName: '小候',
    personality: '冷静 · 有条理',
    description: '擅长整理时间、清单和确定信息。',
    asset: '/companions/migratory-penguin-actions.png',
  },
  plain: {
    label: '纯净助手',
    defaultName: '旅伴',
    personality: '克制 · 不拟人',
    description: '不显示宠物，只保留必要的记忆和提醒。',
  },
}

const POSE_POSITION: Record<CompanionPose, [number, number]> = {
  idle: [0, 0],
  idea: [1, 0],
  deal: [2, 0],
  departure: [0, 1],
  reminder: [1, 1],
  journal: [2, 1],
}

const INTERNAL_MEMORY_FIELDS = new Set(['companion_profile', 'travel_ideas'])

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function memoryValue(memories: MemoryItemDto[], field: string): unknown {
  return memories.find((item) => item.field === field)?.value
}

function parseCompanion(value: unknown): CompanionProfile | null {
  const record = asRecord(value)
  const kind = record?.kind
  const name = record?.name
  const proactivity = record?.proactivity
  if (
    (kind === 'cat' || kind === 'corgi' || kind === 'penguin' || kind === 'plain') &&
    typeof name === 'string' && name.trim() &&
    (proactivity === 'quiet' || proactivity === 'standard' || proactivity === 'active')
  ) {
    return { kind, name: name.trim(), proactivity }
  }
  return null
}

function parseTravelIdeas(value: unknown): TravelIdea[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    const record = asRecord(item)
    if (
      typeof record?.id === 'string' &&
      typeof record.text === 'string' && record.text.trim() &&
      typeof record.created_at === 'string'
    ) {
      return [{ id: record.id, text: record.text.trim(), created_at: record.created_at }]
    }
    return []
  })
}

function queryText(item: QueryHistoryItemDto): string {
  const query = asRecord(item.query)
  return typeof query?.text === 'string' ? query.text.trim() : ''
}

function locationName(value: unknown): string | null {
  if (typeof value === 'string') return value.trim() || null
  const record = asRecord(value)
  if (!record) return null
  for (const key of ['city_name', 'cityName', 'city', 'name', 'label', 'code']) {
    const candidate = record[key]
    if (typeof candidate === 'string' && candidate.trim()) return candidate.trim()
  }
  return null
}

function queryRoute(item: QueryHistoryItemDto): string | null {
  const query = asRecord(item.query)
  const intent = asRecord(query?.intent)
  if (!intent) return null
  const origin = locationName(intent.origin ?? intent.origin_city ?? intent.departure ?? intent.from)
  const destination = locationName(intent.destination ?? intent.destination_city ?? intent.arrival ?? intent.to)
  if (origin && destination) return `${origin} → ${destination}`
  return destination || origin
}

function dateKey(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.slice(0, 10)
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(date)
}

function monthKey(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '未标记月份'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: 'long',
  }).format(date)
}

function buildJournalEntries(ideas: TravelIdea[], history: QueryHistoryItemDto[]): JournalEntry[] {
  const ideaEntries: JournalEntry[] = ideas.map((idea) => ({
    id: `idea-${idea.id}`,
    date: idea.created_at,
    title: idea.text,
    detail: '这是你亲自记下的一个出行念头，还不代表已经确定行程。',
    source: '想法',
  }))
  const queryEntries: JournalEntry[] = history.flatMap((item) => {
    const text = queryText(item)
    if (!text) return []
    const route = queryRoute(item)
    return [{
      id: `query-${item.id}`,
      date: item.created_at,
      title: route || text,
      detail: route ? `你查询了“${text}”。` : `你发起了一次真实查询：“${text}”。`,
      source: '查询' as const,
    }]
  })
  return [...ideaEntries, ...queryEntries].sort(
    (left, right) => new Date(right.date).getTime() - new Date(left.date).getTime(),
  )
}

function CompanionSprite({
  kind,
  pose,
  className = '',
}: {
  kind: CompanionKind
  pose: CompanionPose
  className?: string
}) {
  const companion = COMPANIONS[kind]
  const [column, row] = POSE_POSITION[pose]
  if (!companion.asset) {
    return (
      <div className={`grid place-items-center rounded-full bg-brand-text text-white ${className}`}>
        <Sparkles className="h-8 w-8" />
      </div>
    )
  }
  return (
    <div className={`relative overflow-hidden rounded-[28px] bg-[#fffaf1] ${className}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={companion.asset}
        alt={`${companion.label}·${pose}`}
        className="pointer-events-none absolute left-0 top-0 h-[200%] w-[300%] max-w-none select-none"
        style={{ transform: `translate(${-column * 33.333333}%, ${-row * 50}%)` }}
      />
    </div>
  )
}

export function MemoryPage() {
  const [loadState, setLoadState] = React.useState<LoadState>('loading')
  const [payload, setPayload] = React.useState<MemoryPayload>({ memories: [], query_history: [] })
  const [activeView, setActiveView] = React.useState<MemoryView>('journal')
  const [editingCompanion, setEditingCompanion] = React.useState(false)
  const [draftKind, setDraftKind] = React.useState<CompanionKind>('cat')
  const [draftName, setDraftName] = React.useState(COMPANIONS.cat.defaultName)
  const [savingCompanion, setSavingCompanion] = React.useState(false)
  const [ideaText, setIdeaText] = React.useState('')
  const [savingIdea, setSavingIdea] = React.useState(false)
  const [saveError, setSaveError] = React.useState('')
  const mountedRef = React.useRef(true)

  React.useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  const loadMemory = React.useCallback(async () => {
    setLoadState('loading')
    try {
      const response = await api.getMemory()
      if (!mountedRef.current) return
      setPayload({ memories: response.memories ?? [], query_history: response.query_history ?? [] })
      setLoadState('ready')
    } catch {
      if (mountedRef.current) setLoadState('error')
    }
  }, [])

  React.useEffect(() => { void loadMemory() }, [loadMemory])

  const profile = React.useMemo(
    () => parseCompanion(memoryValue(payload.memories, 'companion_profile')),
    [payload.memories],
  )
  const ideas = React.useMemo(
    () => parseTravelIdeas(memoryValue(payload.memories, 'travel_ideas')),
    [payload.memories],
  )
  const visibleMemories = React.useMemo(
    () => payload.memories.filter((item) => !INTERNAL_MEMORY_FIELDS.has(item.field)),
    [payload.memories],
  )
  const journalEntries = React.useMemo(
    () => buildJournalEntries(ideas, payload.query_history),
    [ideas, payload.query_history],
  )
  const journalMonths = React.useMemo(() => {
    const groups = new Map<string, JournalEntry[]>()
    journalEntries.forEach((entry) => {
      const month = monthKey(entry.date)
      groups.set(month, [...(groups.get(month) ?? []), entry])
    })
    return [...groups.entries()]
  }, [journalEntries])

  React.useEffect(() => {
    if (!profile) return
    setDraftKind(profile.kind)
    setDraftName(profile.name)
  }, [profile])

  const replaceMemory = React.useCallback((field: string, value: unknown, label: string) => {
    setPayload((current) => ({
      ...current,
      memories: [
        ...current.memories.filter((item) => item.field !== field),
        { field, value, label, value_display: '', source: 'manual' },
      ],
    }))
  }, [])

  const saveCompanion = async () => {
    const name = draftName.trim() || COMPANIONS[draftKind].defaultName
    const nextProfile: CompanionProfile = {
      kind: draftKind,
      name,
      proactivity: profile?.proactivity ?? 'standard',
    }
    setSavingCompanion(true)
    setSaveError('')
    try {
      await memoryApi.patch({ field: 'companion_profile', value: nextProfile })
      replaceMemory('companion_profile', nextProfile, '旅伴档案')
      setEditingCompanion(false)
    } catch {
      setSaveError('旅伴暂时没有保存成功，请稍后再试。')
    } finally {
      setSavingCompanion(false)
    }
  }

  const addIdea = async () => {
    const text = ideaText.trim()
    if (!text) return
    const nextIdeas: TravelIdea[] = [{
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      text,
      created_at: new Date().toISOString(),
    }, ...ideas]
    setSavingIdea(true)
    setSaveError('')
    try {
      await memoryApi.patch({ field: 'travel_ideas', value: nextIdeas })
      replaceMemory('travel_ideas', nextIdeas, '出行想法')
      setIdeaText('')
      setActiveView('ideas')
    } catch {
      setSaveError('这个想法暂时没有记下来，请稍后再试。')
    } finally {
      setSavingIdea(false)
    }
  }

  const removeIdea = async (id: string) => {
    const nextIdeas = ideas.filter((idea) => idea.id !== id)
    setSaveError('')
    try {
      await memoryApi.patch({ field: 'travel_ideas', value: nextIdeas })
      replaceMemory('travel_ideas', nextIdeas, '出行想法')
    } catch {
      setSaveError('暂时无法忘掉这个想法，请稍后再试。')
    }
  }

  const selectedKind = profile?.kind ?? draftKind
  const selectedName = profile?.name ?? COMPANIONS[draftKind].defaultName
  const showCompanionPicker = !profile || editingCompanion

  return (
    <div className="thin-scrollbar h-full overflow-y-auto bg-[radial-gradient(circle_at_82%_8%,rgba(255,138,61,0.12),transparent_25%)] px-5 py-6 sm:px-8 lg:px-12 lg:py-8">
      <header className="mx-auto flex max-w-7xl flex-col gap-5 border-b border-brand-text/10 pb-7 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.24em] text-brand-orange">旅芽 · by FareSniper</div>
          <h1 className="mt-2 font-serif text-4xl font-black text-brand-text sm:text-5xl">记得为什么出发</h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-brand-muted sm:text-base">
            旅伴会把真实的想法、查询和选择整理成手帐；只有你确认过的内容，才会成为长期记忆。
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadMemory()}
          disabled={loadState === 'loading'}
          className="inline-flex h-10 items-center justify-center gap-2 self-start rounded-full border border-brand-text/12 bg-white px-4 text-sm font-semibold text-brand-text transition hover:border-brand-orange hover:text-brand-orange disabled:cursor-wait disabled:opacity-55 sm:self-auto"
        >
          <RefreshCw className={`h-4 w-4 ${loadState === 'loading' ? 'animate-spin' : ''}`} />
          刷新记忆
        </button>
      </header>

      <div className="mx-auto max-w-7xl py-7">
        <section className="overflow-hidden rounded-[32px] border border-brand-orange/15 bg-[linear-gradient(135deg,rgba(255,255,255,0.92),rgba(255,240,220,0.76))] shadow-card">
          {showCompanionPicker ? (
            <div className="grid gap-8 p-5 sm:p-7 lg:grid-cols-[minmax(0,0.78fr)_minmax(0,1.22fr)] lg:p-9">
              <div className="flex flex-col justify-center">
                <div className="inline-flex w-fit items-center gap-2 rounded-full bg-brand-orange-light px-3 py-1.5 text-xs font-bold text-brand-orange">
                  <Heart className="h-3.5 w-3.5" />
                  第一步 · 选择旅伴
                </div>
                <h2 className="mt-5 font-serif text-3xl font-black leading-tight text-brand-text sm:text-4xl">
                  你希望谁陪你<br />慢慢写下旅程？
                </h2>
                <p className="mt-4 max-w-xl text-sm leading-7 text-brand-muted">
                  更换旅伴只会改变表达方式，不会改变已经保存的记忆、价格和推荐结论。
                </p>
                <label className="mt-6 block max-w-sm text-sm font-bold text-brand-text">
                  给旅伴起个名字
                  <input
                    value={draftName}
                    onChange={(event) => setDraftName(event.target.value)}
                    className="mt-2 h-11 w-full rounded-2xl border border-brand-text/12 bg-white px-4 font-normal outline-none transition focus:border-brand-orange"
                    placeholder={COMPANIONS[draftKind].defaultName}
                  />
                </label>
                <div className="mt-5 flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={() => void saveCompanion()}
                    disabled={savingCompanion}
                    className="inline-flex h-11 items-center gap-2 rounded-2xl bg-brand-text px-5 text-sm font-bold text-white transition hover:bg-brand-orange disabled:opacity-55"
                  >
                    <Check className="h-4 w-4" />
                    {savingCompanion ? '正在保存' : profile ? '保存更换' : '就选这位旅伴'}
                  </button>
                  {profile ? (
                    <button type="button" onClick={() => setEditingCompanion(false)} className="h-11 rounded-2xl border border-brand-text/12 bg-white px-5 text-sm font-bold text-brand-text">
                      暂不更换
                    </button>
                  ) : null}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-2 xl:grid-cols-4">
                {(Object.keys(COMPANIONS) as CompanionKind[]).map((kind) => {
                  const companion = COMPANIONS[kind]
                  const active = draftKind === kind
                  return (
                    <button
                      key={kind}
                      type="button"
                      aria-label={`选择${companion.label}`}
                      aria-pressed={active}
                      onClick={() => {
                        setDraftKind(kind)
                        setDraftName(companion.defaultName)
                      }}
                      className={`flex min-w-0 flex-col rounded-[24px] border p-3 text-left transition ${active ? 'border-brand-orange bg-white shadow-card' : 'border-brand-text/8 bg-white/55 hover:border-brand-orange/45'}`}
                    >
                      <CompanionSprite kind={kind} pose="idle" className="aspect-square w-full" />
                      <div className="mt-3 text-sm font-black text-brand-text">{companion.label}</div>
                      <div className="mt-1 text-[11px] font-bold text-brand-orange">{companion.personality}</div>
                      <p className="mt-2 text-[11px] leading-5 text-brand-muted">{companion.description}</p>
                    </button>
                  )
                })}
              </div>
            </div>
          ) : (
            <div className="grid items-center gap-6 p-5 sm:grid-cols-[13rem_minmax(0,1fr)] sm:p-7 lg:grid-cols-[17rem_minmax(0,1fr)_auto] lg:p-8">
              <CompanionSprite kind={selectedKind} pose={journalEntries.length ? 'journal' : 'idle'} className="aspect-square w-full max-w-[17rem] justify-self-center" />
              <div>
                <div className="text-xs font-bold text-brand-orange">你的出行旅伴 · {COMPANIONS[selectedKind].label}</div>
                <h2 className="mt-2 font-serif text-3xl font-black text-brand-text sm:text-4xl">{selectedName}</h2>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-brand-muted">
                  {journalEntries.length
                    ? `已经和你一起留下 ${journalEntries.length} 页真实记录。它不会替你编写没有发生过的故事。`
                    : '还没有写下第一篇记录。可以从一个很小的“想去哪里”开始。'}
                </p>
                <div className="mt-4 flex flex-wrap gap-2 text-xs font-bold text-brand-muted">
                  <span className="rounded-full bg-white px-3 py-1.5">轻陪伴</span>
                  <span className="rounded-full bg-white px-3 py-1.5">记忆可修改</span>
                  <span className="rounded-full bg-white px-3 py-1.5">不虚构经历</span>
                </div>
              </div>
              <button type="button" onClick={() => setEditingCompanion(true)} className="inline-flex h-10 items-center gap-2 rounded-full border border-brand-text/12 bg-white px-4 text-sm font-bold text-brand-text transition hover:border-brand-orange hover:text-brand-orange sm:col-start-2 lg:col-start-auto">
                <PencilLine className="h-4 w-4" />
                更换旅伴
              </button>
            </div>
          )}
        </section>

        {saveError ? <div className="mt-4 rounded-2xl border border-brand-orange/20 bg-brand-orange-light px-4 py-3 text-sm font-semibold text-brand-text">{saveError}</div> : null}

        <section className="mt-6 grid gap-4 rounded-[28px] border border-brand-text/8 bg-white/72 p-5 sm:p-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold text-brand-orange">
              <Lightbulb className="h-4 w-4" />
              记下一个还没成行的念头
            </div>
            <label htmlFor="travel-idea" className="sr-only">想去哪里，或者为什么想出发</label>
            <input
              id="travel-idea"
              value={ideaText}
              onChange={(event) => setIdeaText(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void addIdea()
              }}
              className="mt-3 h-12 w-full border-b border-brand-text/12 bg-transparent text-base font-semibold text-brand-text outline-none placeholder:font-normal placeholder:text-brand-muted/70 focus:border-brand-orange"
              placeholder="例如：秋天想去青岛吹吹海风"
            />
          </div>
          <button
            type="button"
            onClick={() => void addIdea()}
            disabled={!ideaText.trim() || savingIdea}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-2xl bg-brand-orange px-5 text-sm font-bold text-white transition hover:bg-brand-text disabled:cursor-not-allowed disabled:opacity-40"
          >
            <BookOpen className="h-4 w-4" />
            {savingIdea ? '正在记下' : '放进想去的地方'}
          </button>
        </section>

        <nav aria-label="记忆内容" className="mt-7 flex flex-wrap gap-2 border-b border-brand-text/10 pb-4">
          <MemoryTab active={activeView === 'journal'} onClick={() => setActiveView('journal')} icon={<BookOpen />} label="旅行手帐" count={journalEntries.length} />
          <MemoryTab active={activeView === 'ideas'} onClick={() => setActiveView('ideas')} icon={<Lightbulb />} label="想去清单" count={ideas.length} />
          <MemoryTab active={activeView === 'remembered'} onClick={() => setActiveView('remembered')} icon={<Heart />} label="它记住的" count={visibleMemories.length} />
        </nav>

        <motion.div key={activeView} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }} className="py-7">
          {loadState === 'error' ? (
            <EmptyState icon={<RefreshCw />} title="暂时无法读取记忆" detail="这次没有成功连接记忆服务，可以稍后重新读取。" action="重新读取" onAction={() => void loadMemory()} />
          ) : activeView === 'journal' ? (
            journalMonths.length ? (
              <div className="space-y-10">
                {journalMonths.map(([month, entries]) => (
                  <section key={month}>
                    <div className="flex items-center gap-4">
                      <h2 className="font-serif text-3xl font-black text-brand-text">{month}</h2>
                      <div className="h-px flex-1 bg-brand-text/10" />
                    </div>
                    <div className="mt-5 grid gap-4 lg:grid-cols-2">
                      {entries.map((entry) => (
                        <article key={entry.id} className="group rounded-[26px] border border-brand-text/8 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-card sm:p-6">
                          <div className="flex items-center justify-between gap-4 text-xs font-bold">
                            <span className="text-brand-orange">{dateKey(entry.date)}</span>
                            <span className="rounded-full bg-brand-orange-light px-3 py-1 text-brand-orange">{entry.source}</span>
                          </div>
                          <h3 className="mt-4 text-xl font-black leading-8 text-brand-text">{entry.title}</h3>
                          <p className="mt-3 text-sm leading-7 text-brand-muted">{entry.detail}</p>
                          <div className="mt-5 flex items-center gap-2 border-t border-dashed border-brand-text/10 pt-4 text-xs font-semibold text-brand-muted">
                            <ShieldCheck className="h-4 w-4 text-emerald-600" />
                            来自真实{entry.source === '查询' ? '查询记录' : '用户记录'}，可以修改或忘记
                          </div>
                        </article>
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            ) : (
              <EmptyState icon={<BookOpen />} title="手帐还没有写下第一页" detail="记录一个想去的地方，或者完成一次真实查询后，这里才会出现内容。" />
            )
          ) : activeView === 'ideas' ? (
            ideas.length ? (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {ideas.map((idea) => (
                  <article key={idea.id} className="rounded-[24px] border border-brand-orange/14 bg-brand-orange-light p-5">
                    <div className="flex items-center justify-between gap-3 text-xs font-bold text-brand-orange">
                      <span>{dateKey(idea.created_at)}</span>
                      <button type="button" aria-label={`忘掉想法：${idea.text}`} onClick={() => void removeIdea(idea.id)} className="grid h-8 w-8 place-items-center rounded-full bg-white/70 text-brand-muted transition hover:text-brand-orange">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                    <h3 className="mt-4 text-lg font-black leading-7 text-brand-text">{idea.text}</h3>
                    <p className="mt-3 text-sm leading-7 text-brand-muted">还只是一个念头，旅伴不会把它当成已经确定的行程。</p>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState icon={<Lightbulb />} title="还没有想去的地方" detail="先写下一句话。只有你主动保存的念头才会进入这里。" />
            )
          ) : visibleMemories.length ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {visibleMemories.map((memory) => (
                <article key={memory.field} className="rounded-[24px] border border-brand-text/8 bg-white p-5 shadow-sm">
                  <div className="flex items-center gap-2 text-xs font-bold text-brand-orange">
                    {memory.source === 'manual' ? <PencilLine className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
                    {memory.source === 'manual' ? '你亲自记录' : '根据真实行为学习'}
                  </div>
                  <h3 className="mt-4 text-lg font-black text-brand-text">{memory.label || memory.field}</h3>
                  <p className="mt-2 text-sm leading-7 text-brand-muted">{memory.value_display || '已记录'}</p>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState icon={<Heart />} title="旅伴还没有形成长期记忆" detail="它不会根据一次点击就猜测你。重复行为或你亲自确认后，偏好才会出现在这里。" />
          )}
        </motion.div>

        <footer className="grid gap-3 border-t border-brand-text/10 pt-5 text-xs font-semibold text-brand-muted sm:grid-cols-3">
          <div className="flex items-center gap-2"><Clock3 className="h-4 w-4 text-brand-orange" />主动提醒遵守安静时间</div>
          <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-brand-orange" />推断记忆必须展示来源</div>
          <div className="flex items-center gap-2"><BellRing className="h-4 w-4 text-brand-orange" />旅途中默认保持安静</div>
        </footer>
      </div>
    </div>
  )
}

function MemoryTab({
  active,
  onClick,
  icon,
  label,
  count,
}: {
  active: boolean
  onClick: () => void
  icon: React.ReactElement
  label: string
  count: number
}) {
  return (
    <button type="button" aria-pressed={active} onClick={onClick} className={`inline-flex h-10 items-center gap-2 rounded-full px-4 text-sm font-bold transition [&>svg]:h-4 [&>svg]:w-4 ${active ? 'bg-brand-text text-white' : 'bg-white text-brand-muted hover:text-brand-text'}`}>
      {icon}
      {label}
      <span className={active ? 'text-white/60' : 'text-brand-orange'}>{count}</span>
    </button>
  )
}

function EmptyState({
  icon,
  title,
  detail,
  action,
  onAction,
}: {
  icon: React.ReactElement
  title: string
  detail: string
  action?: string
  onAction?: () => void
}) {
  return (
    <div className="flex min-h-64 items-center justify-center rounded-[28px] border border-dashed border-brand-text/12 bg-white/45 p-8 text-center">
      <div>
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-brand-orange-light text-brand-orange [&>svg]:h-5 [&>svg]:w-5">{icon}</div>
        <h2 className="mt-4 text-xl font-black text-brand-text">{title}</h2>
        <p className="mx-auto mt-2 max-w-xl text-sm leading-7 text-brand-muted">{detail}</p>
        {action && onAction ? (
          <button type="button" onClick={onAction} className="mt-5 inline-flex h-10 items-center gap-2 rounded-2xl bg-brand-text px-4 text-sm font-bold text-white">
            {action}
            <ChevronRight className="h-4 w-4" />
          </button>
        ) : null}
      </div>
    </div>
  )
}
