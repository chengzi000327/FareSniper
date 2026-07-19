'use client'

import React from 'react'
import { motion } from 'motion/react'
import { AlertCircle, Compass, Heart, History, Lightbulb, RefreshCw } from 'lucide-react'
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
    .slice(0, 8)
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
  const items = [...explicitHabits, ...learnedPreferences].slice(0, 8)
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
    .slice(0, 8)
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
    .slice(0, 10)
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
  const [selectedId, setSelectedId] = React.useState<MemoryChapter['id']>('preference')
  const [loadState, setLoadState] = React.useState<LoadState>('loading')
  const [payload, setPayload] = React.useState<MemoryPayload>({
    memories: [],
    query_history: [],
  })
  const mountedRef = React.useRef(true)

  React.useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  const loadMemory = React.useCallback(async () => {
    setLoadState('loading')
    try {
      const response = await api.getMemory()
      if (!mountedRef.current) return
      setPayload({
        memories: response.memories ?? [],
        query_history: response.query_history ?? [],
      })
      setLoadState('ready')
    } catch {
      if (mountedRef.current) setLoadState('error')
    }
  }, [])

  React.useEffect(() => {
    void loadMemory()
  }, [loadMemory])

  const chapters = React.useMemo(
    () => buildChapters(payload, loadState),
    [payload, loadState],
  )
  const selected = chapters.find((chapter) => chapter.id === selectedId) ?? chapters[0]

  return (
    <div className="thin-scrollbar h-full overflow-y-auto px-5 py-6 sm:px-8 lg:px-12 lg:py-8">
      <header className="flex flex-col gap-5 border-b border-brand-text/10 pb-7 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-brand-text sm:text-4xl">记忆空间</h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-brand-muted sm:text-base">
            偏好、习惯和查询历史会在完成搜索后自动更新。
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadMemory()}
          disabled={loadState === 'loading'}
          className="inline-flex h-10 items-center justify-center gap-2 self-start border border-brand-text/12 bg-white px-4 text-sm font-semibold text-brand-text transition hover:border-brand-orange hover:text-brand-orange disabled:cursor-wait disabled:opacity-55 sm:self-auto"
        >
          <RefreshCw className={`h-4 w-4 ${loadState === 'loading' ? 'animate-spin' : ''}`} />
          刷新记忆
        </button>
      </header>

      <div className="grid gap-0 border-b border-brand-text/10 sm:grid-cols-3">
        <MemoryMetric label="已记录偏好" value={payload.memories.length} />
        <MemoryMetric label="最近查询" value={payload.query_history.length} />
        <MemoryMetric label="同步状态" value={loadState === 'loading' ? '同步中' : loadState === 'error' ? '需重试' : '已同步'} />
      </div>

      <div className="grid min-w-0 gap-8 py-8 lg:grid-cols-[14rem_minmax(0,1fr)] lg:gap-12">
        <nav aria-label="记忆分类" className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:flex lg:flex-col">
          {chapters.map((chapter) => {
            const active = chapter.id === selectedId
            return (
              <button
                key={chapter.id}
                type="button"
                aria-label={chapter.shortLabel}
                aria-pressed={active}
                onClick={() => setSelectedId(chapter.id)}
                className={`flex min-h-12 items-center gap-3 border-l-2 px-4 py-3 text-left text-sm font-semibold transition ${
                  active
                    ? 'border-brand-orange bg-brand-orange/8 text-brand-orange'
                    : 'border-transparent text-brand-muted hover:bg-white hover:text-brand-text'
                }`}
              >
                {chapter.icon}
                <span>{chapter.label}</span>
              </button>
            )
          })}
        </nav>

        <motion.section
          key={selected.id}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          aria-live="polite"
          className="min-w-0"
        >
          <div className="border-b border-brand-text/10 pb-6">
            <p className="text-xs font-semibold text-brand-orange">{selected.leftMeta}</p>
            <h2 className="mt-2 text-2xl font-bold text-brand-text sm:text-3xl">{selected.label}</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-brand-muted">{selected.coverNote}</p>
          </div>

          {selected.timeline.length ? (
            <div className="divide-y divide-brand-text/8">
              {selected.timeline.map((item) => (
                <article key={item.id} className="grid min-w-0 gap-2 py-5 sm:grid-cols-[2.5rem_minmax(0,1fr)] sm:gap-5">
                  <div className="text-sm font-bold text-brand-orange/75">{item.time}</div>
                  <div className="min-w-0">
                    <h3 className="break-words text-base font-bold text-brand-text [overflow-wrap:anywhere]">{item.title}</h3>
                    <p className="mt-1.5 break-words text-sm leading-7 text-brand-muted [overflow-wrap:anywhere]">{item.detail}</p>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="flex min-h-48 items-center border-b border-brand-text/8 py-8">
              <div>
                {loadState === 'error' ? <AlertCircle className="mb-4 h-6 w-6 text-brand-orange" /> : null}
                <h3 className="text-lg font-bold text-brand-text">{selected.emptyTitle}</h3>
                <p className="mt-2 text-sm leading-7 text-brand-muted">{selected.note}</p>
                {loadState === 'error' ? (
                  <button
                    type="button"
                    onClick={() => void loadMemory()}
                    className="mt-5 inline-flex h-10 items-center gap-2 bg-brand-text px-4 text-sm font-semibold text-white transition hover:bg-brand-orange"
                  >
                    <RefreshCw className="h-4 w-4" />
                    重新读取
                  </button>
                ) : null}
              </div>
            </div>
          )}

          {selected.priorities.length ? (
            <div className="grid gap-3 border-b border-brand-text/10 py-6 sm:grid-cols-2">
              {selected.priorities.map((priority) => (
                <div key={priority} className="flex min-w-0 gap-3 bg-white px-4 py-3 text-sm leading-7 text-brand-text shadow-sm">
                  <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-brand-orange" />
                  <span className="break-words [overflow-wrap:anywhere]">{priority}</span>
                </div>
              ))}
            </div>
          ) : null}

          <p className="py-5 text-sm leading-7 text-brand-muted">{selected.note}</p>
        </motion.section>
      </div>
    </div>
  )
}

function MemoryMetric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="border-brand-text/8 px-0 py-5 sm:border-r sm:px-5 sm:first:pl-0 sm:last:border-r-0">
      <div className="text-xs text-brand-muted">{label}</div>
      <div className="mt-1 text-xl font-bold text-brand-text">{value}</div>
    </div>
  )
}
