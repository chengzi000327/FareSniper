'use client'

import React from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowRight, BookOpen, Compass, Heart, History, Lightbulb } from 'lucide-react'
import { api } from '@/lib/api'
import type { MemoryItemDto, QueryHistoryItemDto } from '@/lib/api'

type LoadState = 'loading' | 'ready' | 'error'

type TimelineEntry = {
  id: string
  time: string
  title: string
  detail: string
}

type MemoryChapter = {
  id: 'preference' | 'habit' | 'idea' | 'history'
  shortLabel: string
  label: string
  icon: React.ReactNode
  coverNote: string
  leftMeta: string
  timeline: TimelineEntry[]
  priorities: string[]
  note: string
  emptyTitle: string
}

type MemoryPayload = {
  memories: MemoryItemDto[]
  query_history: QueryHistoryItemDto[]
}

const PREFERENCE_FIELDS = new Set([
  'budget',
  'budget_ceiling',
  'frequent_cities',
  'preferred_airlines',
])

const HABIT_FIELDS = new Set([
  'constraints',
  'travel_scenes',
  'preferred_departure_time',
  'preferred_cabin',
  'preferred_cabins',
  'preferred_platforms',
  'direct_only',
  'max_stops',
])

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function displayValue(memory: MemoryItemDto): string {
  return typeof memory.value_display === 'string' ? memory.value_display.trim() : ''
}

function displayLabel(memory: MemoryItemDto): string {
  const label = typeof memory.label === 'string' ? memory.label.trim() : ''
  return label || memory.field
}

function sourceLabel(source: string): string {
  if (source === 'manual') return '手动记录'
  if (source === 'auto') return '系统自动学习'
  return '已记录'
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

function queryText(item: QueryHistoryItemDto): string {
  const query = asRecord(item.query)
  const text = query?.text
  return typeof text === 'string' ? text.trim() : ''
}

function queryRoute(item: QueryHistoryItemDto): string | null {
  const query = asRecord(item.query)
  const intent = asRecord(query?.intent)
  if (!intent) return null

  const origin = locationName(
    intent.origin ?? intent.origin_city ?? intent.departure ?? intent.from,
  )
  const destination = locationName(
    intent.destination ?? intent.destination_city ?? intent.arrival ?? intent.to,
  )

  if (origin && destination) return `${origin} → ${destination}`
  return destination || origin
}

function formatQueryTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value

  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

function statusText(
  state: LoadState,
  emptyText: string,
): { emptyTitle: string; coverNote: string; note: string } {
  if (state === 'loading') {
    return {
      emptyTitle: '正在读取记忆数据',
      coverNote: '正在同步已保存的真实记录。',
      note: '数据读取完成后会在这里显示。',
    }
  }
  if (state === 'error') {
    return {
      emptyTitle: '暂时无法读取记忆数据',
      coverNote: '这次没有成功读取已保存的记录。',
      note: '稍后重新打开记忆页即可再次读取。',
    }
  }
  return {
    emptyTitle: emptyText,
    coverNote: '这一章暂时没有可展示的真实记录。',
    note: '产生对应的真实记录后，这一章会自动更新。',
  }
}

function buildPreferenceChapter(
  memories: MemoryItemDto[],
  state: LoadState,
): MemoryChapter {
  const items = memories
    .filter((item) => PREFERENCE_FIELDS.has(item.field) && displayValue(item))
    .slice(0, 3)
  const status = statusText(state, '还没有记录出行偏好')

  return {
    id: 'preference',
    shortLabel: '偏好',
    label: '出行偏好',
    icon: <Heart className="h-4 w-4" />,
    coverNote: items.length ? `已记录 ${items.length} 条真实出行偏好。` : status.coverNote,
    leftMeta: '预算、常去城市与偏好航司',
    timeline: items.map((item, index) => ({
      id: `preference-${item.field}`,
      time: String(index + 1).padStart(2, '0'),
      title: displayLabel(item),
      detail: `${displayValue(item)} · ${sourceLabel(item.source)}`,
    })),
    priorities: items.map((item) => `${displayLabel(item)}：${displayValue(item)}`),
    note: items.length ? '以上偏好只来自你保存或实际行为形成的记录。' : status.note,
    emptyTitle: status.emptyTitle,
  }
}

function buildHabitChapter(
  memories: MemoryItemDto[],
  state: LoadState,
): MemoryChapter {
  const explicitHabits = memories.filter(
    (item) => HABIT_FIELDS.has(item.field) && displayValue(item),
  )
  const learnedPreferences = memories.filter(
    (item) =>
      item.source === 'auto' &&
      PREFERENCE_FIELDS.has(item.field) &&
      displayValue(item),
  )
  const items = [...explicitHabits, ...learnedPreferences].slice(0, 3)
  const status = statusText(state, '还没有形成可展示的出行习惯')

  return {
    id: 'habit',
    shortLabel: '习惯',
    label: '出行习惯',
    icon: <Compass className="h-4 w-4" />,
    coverNote: items.length ? `已整理 ${items.length} 条出行习惯与自动学习记录。` : status.coverNote,
    leftMeta: '约束条件与行为学习结果',
    timeline: items.map((item, index) => ({
      id: `habit-${item.field}`,
      time: String(index + 1).padStart(2, '0'),
      title: displayLabel(item),
      detail: `${displayValue(item)} · ${sourceLabel(item.source)}`,
    })),
    priorities: items.map((item) =>
      item.source === 'auto' && PREFERENCE_FIELDS.has(item.field)
        ? `系统自动学习：${displayLabel(item)} ${displayValue(item)}`
        : `${displayLabel(item)}：${displayValue(item)}`,
    ),
    note: items.length ? '自动学习条目来自已记录的搜索或点击行为，不会补写未发生的习惯。' : status.note,
    emptyTitle: status.emptyTitle,
  }
}

function buildIdeaChapter(
  queryHistory: QueryHistoryItemDto[],
  state: LoadState,
): MemoryChapter {
  const items = queryHistory
    .map((item) => ({ item, route: queryRoute(item), text: queryText(item) }))
    .filter((entry): entry is { item: QueryHistoryItemDto; route: string; text: string } =>
      Boolean(entry.route && entry.text),
    )
    .slice(0, 3)
  const status = statusText(state, '最近查询里还没有可整理的路线')

  return {
    id: 'idea',
    shortLabel: '想法',
    label: '出行想法',
    icon: <Lightbulb className="h-4 w-4" />,
    coverNote: items.length ? `从最近查询中整理出 ${items.length} 条路线线索。` : status.coverNote,
    leftMeta: '最近查询中的目的地与路线',
    timeline: items.map(({ item, route, text }, index) => ({
      id: `idea-${item.id}`,
      time: String(index + 1).padStart(2, '0'),
      title: route,
      detail: text,
    })),
    priorities: items.map(({ route }) => `最近关注：${route}`),
    note: items.length ? '这些路线只根据最近查询整理，不代表已经形成长期偏好。' : status.note,
    emptyTitle: status.emptyTitle,
  }
}

function buildHistoryChapter(
  queryHistory: QueryHistoryItemDto[],
  state: LoadState,
): MemoryChapter {
  const items = queryHistory
    .filter((item) => queryText(item))
    .slice(0, 3)
  const status = statusText(state, '还没有搜索记录')

  return {
    id: 'history',
    shortLabel: '历史',
    label: '查询历史',
    icon: <History className="h-4 w-4" />,
    coverNote: items.length ? `这里显示最近 ${items.length} 次真实查询。` : status.coverNote,
    leftMeta: '最近查询时间与原始文本',
    timeline: items.map((item, index) => ({
      id: `history-${item.id}`,
      time: String(index + 1).padStart(2, '0'),
      title: queryText(item),
      detail: `查询时间：${formatQueryTime(item.created_at)}`,
    })),
    priorities: [],
    note: items.length ? '历史章保留原始查询文本与记录时间。' : status.note,
    emptyTitle: status.emptyTitle,
  }
}

function buildChapters(payload: MemoryPayload, state: LoadState): MemoryChapter[] {
  return [
    buildPreferenceChapter(payload.memories, state),
    buildHabitChapter(payload.memories, state),
    buildIdeaChapter(payload.query_history, state),
    buildHistoryChapter(payload.query_history, state),
  ]
}

export function MemoryPage() {
  const [opened, setOpened] = React.useState(false)
  const [selectedId, setSelectedId] = React.useState<MemoryChapter['id']>('preference')
  const [loadState, setLoadState] = React.useState<LoadState>('loading')
  const [payload, setPayload] = React.useState<MemoryPayload>({
    memories: [],
    query_history: [],
  })

  React.useEffect(() => {
    let active = true

    api.getMemory()
      .then((response) => {
        if (!active) return
        setPayload({
          memories: response.memories ?? [],
          query_history: response.query_history ?? [],
        })
        setLoadState('ready')
      })
      .catch(() => {
        if (active) setLoadState('error')
      })

    return () => {
      active = false
    }
  }, [])

  const chapters = React.useMemo(
    () => buildChapters(payload, loadState),
    [payload, loadState],
  )
  const selected = chapters.find((chapter) => chapter.id === selectedId) ?? chapters[0]

  return (
    <div className="thin-scrollbar h-full overflow-y-auto overflow-x-hidden px-5 py-6 sm:px-8 lg:px-12 lg:py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-brand-text sm:text-4xl">记忆空间</h1>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-brand-muted sm:text-base">
          这本日记只整理你真实留下的偏好、习惯与查询记录。
        </p>
      </div>

      <div className="xl:flex xl:min-h-[calc(100vh-15rem)] xl:items-center">
        <div className="grid min-w-0 gap-8 xl:w-full xl:grid-cols-[minmax(19rem,24rem)_minmax(0,1fr)] xl:items-stretch">
          <motion.div
            initial={{ opacity: 0, x: -16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.35, ease: 'easeOut' }}
            className="min-w-0 py-2 xl:flex xl:h-[37rem] xl:items-stretch"
          >
            <motion.button
              type="button"
              onClick={() => setOpened((value) => !value)}
              whileHover={{ y: -6, scale: 1.01 }}
              className="group relative flex min-h-[36rem] w-full max-w-[24rem] min-w-0 flex-col overflow-hidden rounded-[34px] border border-brand-text/8 bg-[linear-gradient(180deg,#fff5eb_0%,#ffecd8_34%,#ffe3c5_100%)] px-8 py-9 text-left shadow-[0_34px_90px_-44px_rgba(67,44,27,0.34)] sm:min-h-[37rem] sm:px-9 sm:py-10 xl:sticky xl:top-8 xl:h-[37rem] xl:min-h-0"
            >
              <div className="absolute inset-y-0 left-0 w-10 bg-[linear-gradient(90deg,rgba(67,44,27,0.14),rgba(67,44,27,0.04),transparent)]" />
              <div className="absolute right-7 top-7 h-16 w-16 rounded-full border border-brand-orange/20 bg-white/70" />
              <div className="mb-10 inline-flex w-fit items-center gap-2 rounded-full bg-white/70 px-4 py-2 text-xs font-bold uppercase tracking-[0.22em] text-brand-orange">
                <BookOpen className="h-4 w-4" />
                Memory Archive
              </div>
              <div className="break-words font-serif text-[clamp(2.7rem,4.4vw,4.2rem)] leading-[1.08] tracking-[0.02em] text-brand-text">
                {opened ? '合上记忆' : '打开记忆'}
                <span className="block italic text-brand-orange">这本日记</span>
              </div>
              <p className="mt-12 max-w-md break-words text-sm leading-8 text-brand-muted sm:text-base">
                搜索、保存和行为学习形成的记录，会按章节整理在这里。
              </p>
              <div className="mt-auto flex items-end justify-between gap-4 pt-16">
                <div className="min-w-0">
                  <div className="break-words text-xs uppercase tracking-[0.28em] text-brand-text/48">FareSniper Journal</div>
                  <div className="mt-5 font-serif text-3xl italic text-brand-text">Vol. 01</div>
                </div>
                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-brand-text text-white transition group-hover:bg-brand-orange">
                  {opened ? <BookOpen className="h-5 w-5" /> : <ArrowRight className="h-5 w-5" />}
                </div>
              </div>
            </motion.button>
          </motion.div>

          <AnimatePresence mode="wait">
            {opened ? (
              <motion.div
                key="memory-journal"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -16 }}
                transition={{ duration: 0.35, ease: 'easeOut' }}
                className="relative min-h-[36rem] min-w-0 max-w-[70rem] rounded-[32px] border border-brand-text/6 bg-[linear-gradient(180deg,rgba(255,255,255,0.97),rgba(255,250,245,0.86))] shadow-[0_26px_70px_-42px_rgba(67,44,27,0.3)] sm:min-h-[37rem] xl:h-[37rem] xl:min-h-0"
              >
                <div className="absolute left-1/2 top-0 hidden h-full w-10 -translate-x-1/2 bg-[radial-gradient(circle_at_center,rgba(67,44,27,0.08),transparent_62%)] lg:block" />
                <div className="absolute left-1/2 top-10 hidden h-[calc(100%-5rem)] w-px -translate-x-1/2 bg-brand-text/8 lg:block" />

                <div className="grid min-w-0 gap-0 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                  <div className="min-w-0 border-b border-brand-text/6 p-6 sm:p-7 lg:border-b-0 lg:border-r lg:border-brand-text/6 lg:p-7 xl:p-8">
                    <div className="mb-6 flex items-center justify-between gap-4 text-[11px] uppercase tracking-[0.26em] text-brand-orange/80">
                      <span>日记</span>
                      <button
                        type="button"
                        onClick={() => setOpened(false)}
                        className="shrink-0 rounded-full border border-brand-text/10 bg-white/70 px-4 py-2 text-[11px] font-bold tracking-[0.18em] text-brand-text transition hover:border-brand-orange hover:text-brand-orange"
                      >
                        合上日记
                      </button>
                    </div>

                    <div className="break-words font-serif text-[clamp(2.7rem,4.2vw,4.3rem)] leading-[0.92] text-brand-text">{selected.label}</div>
                    <div className="mt-3 break-words text-sm uppercase tracking-[0.18em] text-brand-muted">{selected.leftMeta}</div>

                    {selected.timeline.length ? (
                      <div className="mt-7 space-y-5">
                        {selected.timeline.map((item) => (
                          <div key={item.id} className="grid min-w-0 grid-cols-[2.5rem_minmax(0,1fr)] gap-4 border-t border-brand-text/8 pt-4">
                            <div className="pt-0.5 text-lg font-semibold text-brand-orange/72">{item.time}</div>
                            <div className="min-w-0">
                              <div className="break-words text-[1.15rem] font-bold text-brand-text [overflow-wrap:anywhere]">{item.title}</div>
                              <p className="mt-2 break-words text-sm leading-7 text-brand-muted [overflow-wrap:anywhere]">{item.detail}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="mt-8 rounded-[20px] border border-dashed border-brand-text/12 bg-white/55 px-5 py-6">
                        <div className="break-words text-base font-semibold text-brand-text">{selected.emptyTitle}</div>
                        <p className="mt-2 text-sm leading-7 text-brand-muted">{selected.note}</p>
                      </div>
                    )}
                  </div>

                  <div className="relative min-w-0 p-6 sm:p-7 lg:p-7 xl:p-8">
                    <div className="mb-6 lg:pr-10">
                      <div className="text-[11px] uppercase tracking-[0.24em] text-brand-orange/70">Journal Page</div>
                      <div className="mt-2 font-serif text-[2.1rem] leading-[0.96] text-brand-text">记下了什么</div>
                      <div className="mt-2 max-w-lg break-words text-[15px] leading-7 text-brand-text/86 [overflow-wrap:anywhere]">{selected.coverNote}</div>
                    </div>

                    <div className="space-y-6 lg:pr-10">
                      {selected.priorities.length ? (
                        <section>
                          <h3 className="text-[1.58rem] font-bold leading-tight text-brand-text">真实记录</h3>
                          <div className="mt-4 space-y-3">
                            {selected.priorities.map((priority) => (
                              <div
                                key={priority}
                                className="w-full break-words rounded-[20px] border border-brand-text/6 bg-white/72 px-4 py-3 text-[15px] leading-7 text-brand-text shadow-[0_14px_38px_-30px_rgba(67,44,27,0.2)] [overflow-wrap:anywhere]"
                              >
                                {priority}
                              </div>
                            ))}
                          </div>
                        </section>
                      ) : null}

                      <section>
                        <h3 className="text-[1.38rem] font-bold text-brand-text">日记摘要</h3>
                        <div className="mt-3 border-t border-dashed border-brand-text/12 pt-3">
                          <p className="break-words border-b border-dashed border-brand-text/10 pb-2.5 font-serif text-[1.02rem] italic leading-[1.7] text-brand-text/82 [overflow-wrap:anywhere] xl:text-[1.08rem]">
                            {selected.note}
                          </p>
                        </div>
                      </section>
                    </div>

                    <div className="mt-7 grid grid-cols-4 gap-2 border-t border-brand-text/8 pt-5 lg:absolute lg:-right-12 lg:top-1/2 lg:mt-0 lg:flex lg:w-12 lg:-translate-y-1/2 lg:flex-col lg:items-center lg:justify-center lg:gap-4 lg:border-0 lg:pt-0">
                      {chapters.map((chapter) => {
                        const active = chapter.id === selectedId
                        return (
                          <button
                            key={chapter.id}
                            type="button"
                            aria-label={chapter.shortLabel}
                            onClick={() => setSelectedId(chapter.id)}
                            className={`flex min-w-0 items-center justify-center gap-1 rounded-xl border border-brand-text/8 px-2 py-3 text-center text-xs transition lg:w-12 lg:rounded-l-2xl lg:rounded-r-xl lg:px-0 lg:py-4 lg:text-sm ${
                              active
                                ? 'bg-brand-orange/12 text-brand-orange shadow-[0_10px_24px_-18px_rgba(67,44,27,0.35)]'
                                : 'bg-white text-brand-muted hover:bg-brand-bg hover:text-brand-text'
                            }`}
                          >
                            <span className="hidden sm:block lg:hidden">{chapter.icon}</span>
                            <span className="whitespace-nowrap lg:block lg:-rotate-90">{chapter.shortLabel}</span>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="memory-placeholder"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -16 }}
                transition={{ duration: 0.25, ease: 'easeOut' }}
                className="hidden min-h-[36rem] min-w-0 items-center justify-center rounded-[30px] border border-dashed border-brand-text/10 bg-white/35 px-10 text-center sm:min-h-[37rem] xl:flex xl:h-[37rem] xl:min-h-0"
              >
                <div>
                  <div className="font-serif text-4xl text-brand-text/70">日记页会在右边展开</div>
                  <p className="mt-4 max-w-lg text-sm leading-8 text-brand-muted">
                    打开记忆日记，查看系统保存的真实内容。
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
