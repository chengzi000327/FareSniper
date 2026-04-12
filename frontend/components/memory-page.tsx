'use client'

import React from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowRight, BookOpen, Compass, Heart, History, Lightbulb } from 'lucide-react'
import { api } from '@/lib/api'
import type { MemoryItemDto, QueryHistoryItemDto } from '@/lib/api'

type TimelineEntry = {
  time: string
  title: string
  detail: string
}

type MemoryChapter = {
  id: string
  shortLabel: string
  label: string
  icon: React.ReactNode
  coverNote: string
  leftTitle: string
  leftMeta: string
  timeline: TimelineEntry[]
  rightTitle: string
  priorities: string[]
  notes: string[]
}

// Static fallback chapters (used when no backend data or for non-mapped chapters)
const STATIC_CHAPTERS: MemoryChapter[] = [
  {
    id: 'preference',
    shortLabel: '偏好',
    label: '出行偏好',
    icon: <Heart className="h-4 w-4" />,
    coverNote: '系统记住你更容易心动的目的地与路线。',
    leftTitle: '你偏爱的旅行气味',
    leftMeta: '最近形成的目的地倾向',
    timeline: [
      { time: '01', title: '更容易被海岛与松弛感强的城市吸引', detail: '三亚、大理、青岛这类恢复感明显的路线被你反复查看。' },
      { time: '02', title: '你通常会优先点开直飞方案', detail: '少折腾、节奏轻、价格结构清楚的航班更容易进入你的候选。' },
      { time: '03', title: '你对"值得去"的判断更接近体验感而不是打卡感', detail: '系统会逐渐优先给你推送更松弛、更适合真正休息的目的地。' },
    ],
    rightTitle: '这一页的记忆重点',
    priorities: ['海岛/度假感路线优先级高', '直飞和总时长短更容易被接受', '更偏爱"轻松抵达"的目的地'],
    notes: ['你不是单纯在找低价，而是在找"值得出发"的感觉。', '系统会慢慢分辨，你更喜欢放松型旅行，而不是任务型旅行。'],
  },
  {
    id: 'habit',
    shortLabel: '习惯',
    label: '出行习惯',
    icon: <Compass className="h-4 w-4" />,
    coverNote: '你的搜索节奏和决策习惯正在被慢慢整理。',
    leftTitle: '你做决定的方式',
    leftMeta: '搜索与判断价格的习惯',
    timeline: [
      { time: '01', title: '通常会先看综合总价', detail: '你更关心最终实际要花多少钱，而不是单独看裸票价格。' },
      { time: '02', title: '节假日前一到两周会集中比较', detail: '五一、端午、暑假前，是你最容易进入比价状态的时间窗。' },
      { time: '03', title: '你会反复核对平台差异再决定', detail: '系统后续可以优先替你缩小平台选择范围。' },
    ],
    rightTitle: '这一页的记忆重点',
    priorities: ['更重视含税总价', '搜索高峰靠近节假日前', '会跨平台确认价格差异'],
    notes: ['提醒你的最佳时机，不是价格最低的那一刻，而是你最容易做决定的那一刻。', '这些习惯会让后续推荐更像"帮你判断"，而不是单纯塞给你信息。'],
  },
  {
    id: 'idea',
    shortLabel: '想法',
    label: '出行想法',
    icon: <Lightbulb className="h-4 w-4" />,
    coverNote: '有些还没决定的念头，也值得被记下来。',
    leftTitle: '最近浮现的旅行念头',
    leftMeta: '还没出发，但已经有了方向',
    timeline: [
      { time: '01', title: '你最近更想安排短假快闪旅行', detail: '周末出发、两到四天内完成的小旅行，被你频繁关注。' },
      { time: '02', title: '开始在意更轻松的出行方式', detail: '带娃、舒适、低负担这类关键词出现得更多。' },
      { time: '03', title: '你想找的是一种"说走就走但不累"的状态', detail: '系统会持续留意这类适合临时决定的路线。' },
    ],
    rightTitle: '这一页的记忆重点',
    priorities: ['短假旅行灵感在升温', '更关注轻松与陪伴感', '适合临时起意的小旅行值得持续关注'],
    notes: ['有些记忆不是历史，而是你还没说出口的愿望。', '这部分会帮助系统提前猜到，你下一次可能想去哪里。'],
  },
  {
    id: 'history',
    shortLabel: '历史',
    label: '出行历史',
    icon: <History className="h-4 w-4" />,
    coverNote: '被反复点开的路线，最终都会留下痕迹。',
    leftTitle: '最近反复被想起的路线',
    leftMeta: '近期浏览与比较留下的记忆',
    timeline: [
      { time: '01', title: '上海 → 三亚是近期最深的一条线索', detail: '你反复比较了平台、行李额和节假日波动。' },
      { time: '02', title: '北京 → 东京已经形成稳定预算印象', detail: '系统逐渐知道，什么价位会让你觉得真正值得下手。' },
      { time: '03', title: '你会记住那些"差一点就买了"的路线', detail: '这些历史会帮助后续提醒更准确地命中。' },
    ],
    rightTitle: '这一页的记忆重点',
    priorities: ['重点航线会形成心理价位', '历史比较行为能帮助后续提醒', '"差点下单"的路线最值得持续跟踪'],
    notes: ['不是所有历史都要被保留，真正重要的是那些你曾认真犹豫过的路线。', '系统会把这些印象慢慢整理成更懂你的价格记忆。'],
  },
]

function memoriesToPreferenceChapter(memories: MemoryItemDto[]): Partial<MemoryChapter> {
  if (!memories.length) return {}
  const timeline: TimelineEntry[] = memories.slice(0, 3).map((m, i) => ({
    time: String(i + 1).padStart(2, '0'),
    title: m.label,
    detail: `当前记录：${m.value_display}（来源：${m.source === 'manual' ? '手动设置' : '自动学习'}）`,
  }))
  const priorities = memories.map((m) => `${m.label}：${m.value_display}`)
  return {
    timeline: timeline.length ? timeline : undefined,
    priorities: priorities.length ? priorities : undefined,
    coverNote: `系统已记录你的 ${memories.length} 条出行偏好。`,
  }
}

function queryHistoryToHistoryChapter(queryHistory: QueryHistoryItemDto[]): Partial<MemoryChapter> {
  if (!queryHistory.length) return {}
  const timeline: TimelineEntry[] = queryHistory.slice(0, 3).map((q, i) => {
    const text = (q.query as { text?: string }).text ?? JSON.stringify(q.query)
    const date = q.created_at.slice(0, 10)
    return {
      time: String(i + 1).padStart(2, '0'),
      title: text,
      detail: `搜索于 ${date}`,
    }
  })
  const priorities = queryHistory.slice(0, 3).map((q) => {
    return (q.query as { text?: string }).text ?? '查询记录'
  })
  return {
    timeline: timeline.length ? timeline : undefined,
    priorities: priorities.length ? priorities : undefined,
    coverNote: `最近 ${queryHistory.length} 次搜索记录已保存。`,
    leftMeta: '最近的搜索记录',
  }
}

export function MemoryPage() {
  const [opened, setOpened] = React.useState(false)
  const [selectedId, setSelectedId] = React.useState(STATIC_CHAPTERS[0].id)
  const [chapters, setChapters] = React.useState<MemoryChapter[]>(STATIC_CHAPTERS)

  React.useEffect(() => {
    api.getMemory().then((resp) => {
      setChapters((prev) =>
        prev.map((chapter) => {
          if (chapter.id === 'preference') {
            const overrides = memoriesToPreferenceChapter(resp.memories)
            return { ...chapter, ...overrides }
          }
          if (chapter.id === 'history') {
            const overrides = queryHistoryToHistoryChapter(resp.query_history)
            return { ...chapter, ...overrides }
          }
          return chapter
        }),
      )
    }).catch(() => {
      // keep static data on error
    })
  }, [])

  const selected = chapters.find((chapter) => chapter.id === selectedId) ?? chapters[0]

  return (
    <div className="thin-scrollbar h-full overflow-y-auto px-5 py-6 sm:px-8 lg:px-12 lg:py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-brand-text sm:text-4xl">记忆空间</h1>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-brand-muted sm:text-base">
          这是一本慢慢写满的特价机票发现日记。翻开它，你会看到系统究竟记住了你什么。
        </p>
      </div>

      <div className="xl:flex xl:min-h-[calc(100vh-15rem)] xl:items-center">
        <div className="grid gap-8 xl:w-full xl:grid-cols-[minmax(19rem,24rem)_minmax(0,1fr)] xl:items-stretch">
          <motion.div
            initial={{ opacity: 0, x: -16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.35, ease: 'easeOut' }}
            className="py-2 xl:flex xl:h-[37rem] xl:items-stretch"
          >
          <motion.button
            type="button"
            onClick={() => setOpened((value) => !value)}
            whileHover={{ y: -6, scale: 1.01 }}
            className="group relative flex min-h-[36rem] w-full max-w-[24rem] flex-col overflow-hidden rounded-[34px] border border-brand-text/8 bg-[linear-gradient(180deg,#fff5eb_0%,#ffecd8_34%,#ffe3c5_100%)] px-8 py-9 text-left shadow-[0_34px_90px_-44px_rgba(67,44,27,0.34)] sm:min-h-[37rem] sm:px-9 sm:py-10 xl:h-[37rem] xl:min-h-0 xl:sticky xl:top-8"
          >
            <div className="absolute inset-y-0 left-0 w-10 bg-[linear-gradient(90deg,rgba(67,44,27,0.14),rgba(67,44,27,0.04),transparent)]" />
            <div className="absolute right-7 top-7 h-16 w-16 rounded-full border border-brand-orange/20 bg-white/70" />
            <div className="mb-10 inline-flex items-center gap-2 rounded-full bg-white/70 px-4 py-2 text-xs font-bold uppercase tracking-[0.22em] text-brand-orange">
              <BookOpen className="h-4 w-4" />
              Memory Archive
            </div>
            <div className="font-serif text-[clamp(2.7rem,4.4vw,4.2rem)] leading-[1.08] tracking-[0.02em] text-brand-text">
              {opened ? '合上记忆' : '打开记忆'}
              <span className="block italic text-brand-orange">这本日记</span>
            </div>
            <p className="mt-12 max-w-md text-sm leading-8 text-brand-muted sm:text-base">
              这是一本慢慢写满的特价机票发现日记。里面记录你偏爱的路线、做决定的方式，还有那些差一点就出发的念头。
            </p>
            <div className="mt-auto flex items-end justify-between pt-16">
              <div>
                <div className="text-xs uppercase tracking-[0.28em] text-brand-text/48">FareSniper Journal</div>
                <div className="mt-5 font-serif text-3xl italic text-brand-text">Vol. 01</div>
              </div>
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-brand-text text-white transition group-hover:bg-brand-orange">
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
              className="relative min-h-[36rem] max-w-[70rem] rounded-[32px] border border-brand-text/6 bg-[linear-gradient(180deg,rgba(255,255,255,0.97),rgba(255,250,245,0.86))] shadow-[0_26px_70px_-42px_rgba(67,44,27,0.3)] sm:min-h-[37rem] xl:h-[37rem] xl:min-h-0"
            >
              <div className="absolute left-1/2 top-0 hidden h-full w-10 -translate-x-1/2 bg-[radial-gradient(circle_at_center,rgba(67,44,27,0.08),transparent_62%)] lg:block" />
              <div className="absolute left-1/2 top-10 hidden h-[calc(100%-5rem)] w-px -translate-x-1/2 bg-brand-text/8 lg:block" />

              <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <div className="border-b border-brand-text/6 p-6 sm:p-7 lg:border-b-0 lg:border-r lg:border-brand-text/6 lg:p-7 xl:p-8">
                  <div className="mb-6 flex items-center justify-between gap-4 text-[11px] uppercase tracking-[0.26em] text-brand-orange/80">
                    <span>日记</span>
                    <button
                      type="button"
                      onClick={() => setOpened(false)}
                      className="rounded-full border border-brand-text/10 bg-white/70 px-4 py-2 text-[11px] font-bold tracking-[0.18em] text-brand-text transition hover:border-brand-orange hover:text-brand-orange"
                    >
                      合上日记
                    </button>
                  </div>

                  <div className="font-serif text-[clamp(2.7rem,4.2vw,4.3rem)] leading-[0.92] text-brand-text">{selected.label}</div>
                  <div className="mt-3 text-sm uppercase tracking-[0.18em] text-brand-muted">{selected.leftMeta}</div>

                  <div className="mt-7 space-y-6">
                    {selected.timeline.map((item) => (
                      <div key={item.title} className="grid grid-cols-[2.5rem_minmax(0,1fr)] gap-4 border-t border-brand-text/8 pt-4">
                        <div className="pt-0.5 text-lg font-semibold text-brand-orange/72">{item.time}</div>
                        <div>
                          <div className="text-[1.15rem] font-bold text-brand-text">{item.title}</div>
                          <p className="mt-2 text-sm leading-7 text-brand-muted">{item.detail}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="relative p-6 sm:p-7 lg:p-7 xl:p-8">
                  <div className="mb-6 pr-10">
                    <div className="text-[11px] uppercase tracking-[0.24em] text-brand-orange/70">Journal Page</div>
                    <div className="mt-2 font-serif text-[2.1rem] leading-[0.96] text-brand-text">记下了什么</div>
                    <div className="mt-2 max-w-lg text-[15px] leading-7 text-brand-text/86">{selected.coverNote}</div>
                  </div>

                  <div className="space-y-6 pr-10">
                    <section>
                      <h3 className="text-[1.58rem] font-bold leading-tight text-brand-text">{selected.rightTitle}</h3>
                      <div className="mt-4 space-y-3">
                        {selected.priorities.map((priority) => (
                          <div
                            key={priority}
                            className="w-full rounded-[20px] border border-brand-text/6 bg-white/72 px-4 py-3 text-[15px] leading-7 text-brand-text shadow-[0_14px_38px_-30px_rgba(67,44,27,0.2)]"
                          >
                            {priority}
                          </div>
                        ))}
                      </div>
                    </section>

                    <section>
                      <h3 className="text-[1.38rem] font-bold text-brand-text">日记摘要</h3>
                      <div className="mt-3 space-y-2 border-t border-dashed border-brand-text/12 pt-3">
                        <p className="border-b border-dashed border-brand-text/10 pb-2.5 font-serif text-[1.02rem] italic leading-[1.7] text-brand-text/82 xl:text-[1.08rem]">
                          {selected.notes[0]}
                        </p>
                      </div>
                    </section>
                  </div>

                  <div className="absolute -right-12 top-1/2 hidden -translate-y-1/2 flex-col items-center justify-center gap-4 lg:flex">
                    {chapters.map((chapter) => {
                      const active = chapter.id === selectedId
                      return (
                        <button
                          key={chapter.id}
                          type="button"
                          onClick={() => setSelectedId(chapter.id)}
                          className={`w-12 rounded-l-2xl rounded-r-xl border border-brand-text/8 px-0 py-4 text-center text-sm tracking-[0.2em] transition ${
                            active
                              ? 'bg-brand-orange/12 text-brand-orange shadow-[0_10px_24px_-18px_rgba(67,44,27,0.35)]'
                              : 'bg-white text-brand-muted hover:bg-brand-bg hover:text-brand-text'
                          }`}
                        >
                          <span className="block -rotate-90 whitespace-nowrap">{chapter.shortLabel}</span>
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
              className="hidden min-h-[36rem] items-center justify-center rounded-[30px] border border-dashed border-brand-text/10 bg-white/35 px-10 text-center sm:min-h-[37rem] xl:flex xl:h-[37rem] xl:min-h-0"
            >
              <div>
                <div className="font-serif text-4xl text-brand-text/70">日记页会在右边展开</div>
                <p className="mt-4 max-w-lg text-sm leading-8 text-brand-muted">
                  点击左侧这本记忆书，像翻开旅行日记一样查看系统记住的内容。
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
