'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import {
  DEFAULT_USER_ID,
  deleteMemory as deleteMemoryRequest,
  getMemoryWorkspace,
  updateMemory,
} from '@/lib/api-client'
import { mockMemories } from '@/lib/mocks'
import type { MemoryWorkspaceData, PreferenceMemory } from '@/types'

const emptyWorkspace: MemoryWorkspaceData = {
  memories: mockMemories,
  queryHistory: [],
  clickHistory: [],
}

function readTextValue(record: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = record[key]
    if (typeof value === 'string' && value.trim()) {
      return value.trim()
    }
  }

  return ''
}

export default function MemoryPage() {
  const [memories, setMemories] = useState<PreferenceMemory[]>(mockMemories)
  const [workspace, setWorkspace] = useState<MemoryWorkspaceData>(emptyWorkspace)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let mounted = true

    getMemoryWorkspace(DEFAULT_USER_ID)
      .then((result) => {
        if (mounted) {
          setWorkspace(result)
          setMemories(result.memories)
        }
      })
      .catch((loadError) => {
        if (mounted) {
          setError(loadError instanceof Error ? loadError.message : '读取记忆失败')
        }
      })
      .finally(() => {
        if (mounted) {
          setLoading(false)
        }
      })

    return () => {
      mounted = false
    }
  }, [])

  const startEdit = (id: string, currentValue: string) => {
    setEditingId(id)
    setEditValue(currentValue)
  }

  const saveEdit = async () => {
    if (!editingId) return

    const targetMemory = memories.find((memory) => memory.id === editingId)
    if (!targetMemory) return

    setSaving(true)
    setError('')

    try {
      const result = await updateMemory({
        user_id: DEFAULT_USER_ID,
        field: targetMemory.field,
        value: editValue,
        source: 'manual',
      })
      setMemories(result)
      setWorkspace((current) => ({ ...current, memories: result }))
      setEditingId(null)
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteMemory = async (field: string) => {
    setSaving(true)
    setError('')

    try {
      const result = await deleteMemoryRequest(field, DEFAULT_USER_ID)
      setMemories(result)
      setWorkspace((current) => ({ ...current, memories: result }))
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : '删除失败')
    } finally {
      setSaving(false)
    }
  }

  const handleAddMemory = () => {
    const value = window.prompt('输入一条新的出行时间偏好，例如：周末 / 法定假日')
    if (!value?.trim()) return

    void updateMemory({
      user_id: DEFAULT_USER_ID,
      field: 'travel_window',
      value: value.trim(),
      source: 'manual',
    })
      .then((result) => {
        setMemories(result)
        setWorkspace((current) => ({ ...current, memories: result }))
        setError('')
      })
      .catch((addError) => {
        setError(addError instanceof Error ? addError.message : '新增失败')
      })
  }

  const latestQueries = workspace.queryHistory.slice(0, 3)
  const clickedRoutes = workspace.clickHistory.slice(0, 3).map((item) => {
    const origin = readTextValue(item.flightInfo, ['origin_city', 'origin', 'origin_code']) || '出发地待定'
    const destination = readTextValue(item.flightInfo, ['destination_city', 'destination', 'destination_code']) || '目的地待定'
    const departDate = readTextValue(item.flightInfo, ['depart_date', 'date_start'])

    return {
      route: `${origin} -> ${destination}`,
      date: departDate || '时间待定',
      createdAt: item.createdAt,
    }
  })
  const latestSearchRoutes = latestQueries.map((item) => {
    const origin = readTextValue(item.query, ['origin_city', 'origin', 'origin_code']) || '任意出发地'
    const destination = readTextValue(item.query, ['destination_city', 'destination', 'destination_code']) || '目的地待定'
    const departDate = readTextValue(item.query, ['date_start'])

    return {
      route: `${origin} -> ${destination}`,
      date: departDate || '时间待定',
      createdAt: item.createdAt,
    }
  })
  const recentRoutes = clickedRoutes.length > 0 ? clickedRoutes : latestSearchRoutes
  const placePool = [
    ...workspace.clickHistory.map((item) => readTextValue(item.flightInfo, ['destination_city', 'destination', 'destination_code'])),
    ...workspace.queryHistory.map((item) => readTextValue(item.query, ['destination_city', 'destination', 'destination_code'])),
  ].filter(Boolean)
  const recentPlaces = Array.from(new Set(placePool)).slice(0, 8)
  const datePool = [
    ...workspace.clickHistory.map((item) => readTextValue(item.flightInfo, ['depart_date', 'date_start'])),
    ...workspace.queryHistory.map((item) => readTextValue(item.query, ['date_start'])),
  ].filter(Boolean)
  const recentDates = Array.from(new Set(datePool)).slice(0, 6)
  const latestActivity = memories[0]?.updatedAt ?? '刚刚'
  const behaviorSummary = workspace.clickHistory.length > 0
    ? '这些路线是你最近真正点开过的目的地，说明系统已经开始分辨你会停下来看的票。'
    : '你还在探索阶段，目前先根据搜索记录形成轨迹，等点开更多票卡后会更懂你的真实兴趣。'

  return (
    <div className="min-h-screen bg-[#f7f8fb] font-sans">
      <nav className="sticky top-0 z-10 flex items-center justify-between border-b border-[#e8ebf2] bg-white/78 px-8 py-5 backdrop-blur-sm">
        <Link
          href="/chat"
          className="group flex items-center gap-2 text-sm text-gray-400 transition-colors hover:text-navy"
        >
          <svg className="h-4 w-4 transition-transform group-hover:-translate-x-0.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10 13L5 8l5-5" />
          </svg>
          返回对话
        </Link>
        <div className="flex items-center gap-2">
          <div className="h-4 w-4 rounded-full bg-navy" />
          <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-navy/40">FareSniper</span>
        </div>
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-navy text-xs font-semibold text-white">
          我
        </div>
      </nav>

      <div className="mx-auto grid max-w-[1360px] grid-cols-[minmax(0,560px)_minmax(360px,1fr)] gap-10 px-8 py-10">
        <section>
          <div className="mb-10">
            <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.18em] text-gray-300">
              MEMORY · {loading ? '加载中' : `${memories.length} 条记忆`}
            </p>
            <h1 className="font-heading text-[2.9rem] font-bold leading-tight text-navy">
              系统记住的你
            </h1>
            <p className="mt-2 text-sm text-gray-400">
              来自你的对话与手动设置 · 随时可编辑
            </p>
            {error && (
              <p className="mt-3 text-sm text-red-500">
                {error}
              </p>
            )}
          </div>

          <div className="space-y-3">
            {loading && (
              <div className="rounded-3xl bg-white px-6 py-10 text-sm text-gray-400 shadow-card">
                正在加载你的记忆...
              </div>
            )}

            {memories.map((memory, index) => (
              <div
                key={memory.id}
                className="group relative transition-all duration-300 hover:z-10"
                style={{
                  transform: `rotate(${memory.rotation})`,
                  zIndex: memories.length - index,
                }}
                onMouseEnter={(event) => {
                  ;(event.currentTarget as HTMLElement).style.transform = 'rotate(0deg) translateY(-2px)'
                }}
                onMouseLeave={(event) => {
                  ;(event.currentTarget as HTMLElement).style.transform = `rotate(${memory.rotation})`
                }}
              >
                <div className="overflow-hidden rounded-3xl bg-white shadow-card transition-shadow duration-300 hover:shadow-card-hover">
                  <div className="h-1 w-full" style={{ backgroundColor: memory.accentColor }} />

                  <div className="p-6">
                    <div className="mb-4 flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <div
                          className="flex h-7 w-7 items-center justify-center rounded-xl text-xs font-bold text-white"
                          style={{ backgroundColor: memory.accentColor }}
                        >
                          {memory.label.charAt(0)}
                        </div>
                        <span className="font-mono text-[11px] uppercase tracking-wider text-gray-400">
                          {memory.label}
                        </span>
                      </div>

                      <div className="flex items-center gap-1 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                        <button
                          disabled={saving}
                          onClick={() => startEdit(memory.id, memory.value)}
                          className="rounded-lg px-2.5 py-1.5 text-xs text-gray-300 transition-all hover:bg-gray-50 hover:text-navy"
                        >
                          编辑
                        </button>
                        <button
                          disabled={saving}
                          onClick={() => handleDeleteMemory(memory.field)}
                          className="rounded-lg px-2.5 py-1.5 text-xs text-gray-300 transition-all hover:bg-red-50 hover:text-red-400"
                        >
                          删除
                        </button>
                      </div>
                    </div>

                    {editingId === memory.id ? (
                      <div className="flex gap-2">
                        <input
                          autoFocus
                          value={editValue}
                          onChange={(event) => setEditValue(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter') saveEdit()
                            if (event.key === 'Escape') setEditingId(null)
                          }}
                          className="flex-1 rounded-xl border border-navy/20 bg-navy-50/50 px-3 py-2 text-sm text-navy outline-none focus:border-navy/40"
                        />
                        <button
                          onClick={saveEdit}
                          disabled={saving}
                          className="rounded-xl bg-navy px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-navy-light"
                        >
                          {saving ? '保存中...' : '保存'}
                        </button>
                      </div>
                    ) : (
                      <p className="font-heading text-[1.6rem] font-bold leading-tight text-navy">
                        {memory.value}
                      </p>
                    )}

                    <div className="mt-4 flex items-center justify-between border-t border-gray-50 pt-4">
                      <span
                        className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                          memory.source === 'auto'
                            ? 'bg-signal-muted text-signal-text'
                            : 'bg-navy-50 text-navy-muted'
                        }`}
                      >
                        {memory.source === 'auto' ? '系统归纳' : '手动设置'}
                      </span>
                      <span className="text-xs text-gray-300">{memory.updatedAt}更新</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <button
            onClick={handleAddMemory}
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-3xl border-2 border-dashed border-gray-200 py-5 text-sm text-gray-300 transition-all duration-200 hover:border-navy/20 hover:bg-white hover:text-navy/40"
          >
            <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M8 3v10M3 8h10" />
            </svg>
            添加偏好
          </button>
        </section>

        <aside className="space-y-5">
          <div className="rounded-[32px] bg-[linear-gradient(145deg,#1f2f69_0%,#2d4a93_100%)] p-7 text-white shadow-[0_24px_60px_rgba(27,43,94,0.18)]">
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-white/52">
              Behavior Snapshot
            </p>
            <h2 className="mt-3 font-heading text-[2.2rem] font-bold leading-tight">
              你的出行轨迹
            </h2>
            <p className="mt-3 max-w-[380px] text-sm leading-relaxed text-white/68">
              {behaviorSummary}
            </p>

            <div className="mt-6 grid grid-cols-3 gap-3">
              <div className="rounded-2xl bg-white/10 px-4 py-4">
                <p className="text-xs text-white/54">搜索记录</p>
                <p className="mt-2 text-2xl font-semibold">{workspace.queryHistory.length}</p>
              </div>
              <div className="rounded-2xl bg-white/10 px-4 py-4">
                <p className="text-xs text-white/54">点开票卡</p>
                <p className="mt-2 text-2xl font-semibold">{workspace.clickHistory.length}</p>
              </div>
              <div className="rounded-2xl bg-white/10 px-4 py-4">
                <p className="text-xs text-white/54">最近活跃</p>
                <p className="mt-2 text-lg font-semibold">{latestActivity}</p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-5">
            <div className="rounded-[28px] border border-[#ebeff5] bg-white p-6 shadow-[0_16px_40px_rgba(27,43,94,0.06)]">
              <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-navy/34">
                Places
              </p>
              <h3 className="mt-3 text-lg font-semibold text-navy">
                最近关注城市
              </h3>
              <div className="mt-4 flex flex-wrap gap-2">
                {recentPlaces.length > 0 ? recentPlaces.map((place) => (
                  <span
                    key={place}
                    className="rounded-full bg-[#eef3ff] px-3 py-2 text-sm font-medium text-navy"
                  >
                    {place}
                  </span>
                )) : (
                  <p className="text-sm leading-relaxed text-navy/42">
                    还没有形成明显目的地轨迹，等你多搜索几次这里会慢慢长出来。
                  </p>
                )}
              </div>
            </div>

            <div className="rounded-[28px] border border-[#ebeff5] bg-white p-6 shadow-[0_16px_40px_rgba(27,43,94,0.06)]">
              <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-navy/34">
                Timing
              </p>
              <h3 className="mt-3 text-lg font-semibold text-navy">
                最近在看的时间
              </h3>
              <div className="mt-4 flex flex-wrap gap-2">
                {recentDates.length > 0 ? recentDates.map((date) => (
                  <span
                    key={date}
                    className="rounded-full bg-[#f6f8fc] px-3 py-2 text-sm font-medium text-navy/78"
                  >
                    {date}
                  </span>
                )) : (
                  <p className="text-sm leading-relaxed text-navy/42">
                    暂时还没有稳定时间线，等你留下更多出发日期后这里会更有参考价值。
                  </p>
                )}
              </div>
            </div>
          </div>

          <div className="rounded-[28px] border border-[#ebeff5] bg-white p-6 shadow-[0_16px_40px_rgba(27,43,94,0.06)]">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-navy/34">
                  Recent Activity
                </p>
                <h3 className="mt-3 text-lg font-semibold text-navy">
                  最近形成的路线轨迹
                </h3>
              </div>
              <div className="rounded-full bg-[#eef3ff] px-3 py-1 text-xs font-medium text-navy/56">
                {recentRoutes.length} 条展示
              </div>
            </div>

            <div className="mt-5 space-y-3">
              {recentRoutes.length > 0 ? recentRoutes.map((item, index) => (
                <div
                  key={`${item.route}-${item.createdAt}-${index}`}
                  className="rounded-2xl bg-[#f8fafc] px-4 py-4"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-sm font-semibold text-navy">
                        {item.route}
                      </p>
                      <p className="mt-1 text-sm text-navy/44">
                        出发时间：{item.date}
                      </p>
                    </div>
                    <span className="text-xs text-navy/34">{item.createdAt}</span>
                  </div>
                </div>
              )) : (
                <div className="rounded-2xl bg-[#f8fafc] px-4 py-5 text-sm text-navy/42">
                  还没有足够的历史记录。等你多搜索几次，这里会开始展示越来越清晰的路线轨迹。
                </div>
              )}
            </div>
          </div>

          <div className="rounded-[28px] border border-[#ebeff5] bg-[linear-gradient(145deg,#f7f9fd_0%,#eef4ff_100%)] p-6 shadow-[0_16px_40px_rgba(27,43,94,0.05)]">
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-navy/34">
              Insight
            </p>
            <h3 className="mt-3 text-lg font-semibold text-navy">
              系统还在等你告诉它什么
            </h3>
            <div className="mt-4 space-y-3">
              <div className="rounded-2xl bg-white px-4 py-4 shadow-sm">
                <p className="text-sm font-medium text-navy">
                  {workspace.clickHistory.length > 0 ? '你已经开始筛选具体票卡了' : '还缺少点开票卡的行为'}
                </p>
                <p className="mt-1 text-sm leading-relaxed text-navy/46">
                  {workspace.clickHistory.length > 0
                    ? '继续点开感兴趣的票，系统会更清楚你是只看低价，还是更在意日期、时间段和航司。'
                    : '下一次看到感兴趣的路线时点开它，右侧这块就会从“搜索轨迹”升级成更真实的偏好判断。'}
                </p>
              </div>
              <div className="rounded-2xl bg-white px-4 py-4 shadow-sm">
                <p className="text-sm font-medium text-navy">
                  {recentPlaces.length > 2 ? '目的地线索已经开始稳定' : '目的地线索还不够多'}
                </p>
                <p className="mt-1 text-sm leading-relaxed text-navy/46">
                  {recentPlaces.length > 2
                    ? `目前最常出现的是 ${recentPlaces.slice(0, 3).join('、')}，后续推荐会优先围绕这些城市展开。`
                    : '再补几次搜索，系统就能把“偶尔看看”和“真的想去”分得更清楚。'}
                </p>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
