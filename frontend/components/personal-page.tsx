'use client'

import React from 'react'
import { Bell, Clock3, MessageSquareText, RefreshCw, Search, UserRound } from 'lucide-react'
import { alertsApi, memoryApi } from '@/lib/api'
import type { AlertItemDto, MemoryItemDto, QueryHistoryItemDto } from '@/lib/api'

type GraphNode = {
  id: string
  label: string
  kind: 'center' | 'monitor' | 'chat'
  x: number
  y: number
  detail: string
}

type PersonalData = {
  alerts: AlertItemDto[]
  memories: MemoryItemDto[]
  queries: QueryHistoryItemDto[]
}

function queryText(item: QueryHistoryItemDto) {
  if (typeof item.query !== 'object' || item.query === null || Array.isArray(item.query)) return '一次机票查询'
  const text = (item.query as Record<string, unknown>).text
  return typeof text === 'string' && text.trim() ? text.trim() : '一次机票查询'
}

function accountSummary() {
  if (typeof window === 'undefined') return '正在读取账号'
  const phone = window.localStorage.getItem('fs_phone')
  const userId = window.localStorage.getItem('fs_user_id')
  if (phone) {
    const digits = phone.replace(/\D/g, '')
    return `${digits.slice(-11, -7)}****${digits.slice(-4)} · 正式账号`
  }
  return userId ? `本机游客账号 · ${userId.slice(-8).toUpperCase()}` : '账号正在初始化'
}

export function PersonalPage() {
  const [data, setData] = React.useState<PersonalData>({ alerts: [], memories: [], queries: [] })
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState('')
  const [selectedId, setSelectedId] = React.useState('me')

  const loadData = React.useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [alertsResult, memoryResult] = await Promise.all([alertsApi.list(), memoryApi.get()])
      setData({
        alerts: alertsResult.alerts ?? [],
        memories: memoryResult.memories ?? [],
        queries: memoryResult.query_history ?? [],
      })
    } catch {
      setError('账号数据暂时没有加载成功，请稍后重试。')
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => { void loadData() }, [loadData])

  const graphNodes = React.useMemo<GraphNode[]>(() => {
    const alertPositions = [{ x: 18, y: 62 }, { x: 34, y: 76 }]
    const queryPositions = [{ x: 68, y: 74 }, { x: 84, y: 58 }]
    return [
      { id: 'me', label: '我的发现台', kind: 'center', x: 50, y: 49, detail: 'Mobile 与网页端通过同一账号读取这里的数据。' },
      { id: 'monitor-root', label: `价格提醒 ${data.alerts.length}`, kind: 'monitor', x: 27, y: 30, detail: `${data.alerts.length} 条后端价格提醒。` },
      { id: 'chat-root', label: `最近查询 ${data.queries.length}`, kind: 'chat', x: 73, y: 30, detail: `${data.queries.length} 条真实查询记录。` },
      ...data.alerts.slice(0, 2).map((alert, index) => ({
        id: `alert-${alert.id}`,
        label: `${alert.origin} → ${alert.destination}`,
        kind: 'monitor' as const,
        ...alertPositions[index],
        detail: `${alert.depart_date} · 目标价不高于 ¥${alert.target_price} · ${alert.status === 'triggered' ? '已触发' : '监控中'}`,
      })),
      ...data.queries.slice(0, 2).map((query, index) => ({
        id: `query-${query.id}`,
        label: queryText(query).slice(0, 12),
        kind: 'chat' as const,
        ...queryPositions[index],
        detail: `真实查询 · ${queryText(query)}`,
      })),
    ]
  }, [data.alerts, data.queries])

  const graphEdges = React.useMemo<Array<[string, string]>>(() => [
    ['me', 'monitor-root'],
    ['me', 'chat-root'],
    ...data.alerts.slice(0, 2).map((alert) => ['monitor-root', `alert-${alert.id}`] as [string, string]),
    ...data.queries.slice(0, 2).map((query) => ['chat-root', `query-${query.id}`] as [string, string]),
  ], [data.alerts, data.queries])
  const selectedNode = graphNodes.find((node) => node.id === selectedId) ?? graphNodes[0]
  const activeAlerts = data.alerts.filter((alert) => alert.status === 'active')

  return (
    <div className="thin-scrollbar h-full overflow-y-auto px-5 py-6 sm:px-8 lg:px-12 lg:py-8">
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <div className="text-xs font-black tracking-[0.16em] text-brand-orange">真实账号数据</div>
          <h1 className="mt-1 text-3xl font-bold text-brand-text sm:text-4xl">个人中心</h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-brand-muted sm:text-base">提醒、查询和记忆均来自生产后端，不再展示写死的示例内容。</p>
        </div>
        <button type="button" onClick={() => void loadData()} aria-label="刷新个人中心" className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border border-brand-text/8 bg-white text-brand-text shadow-sm">
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error ? <div className="mb-5 rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-700">{error}</div> : null}

      <div className="xl:flex xl:min-h-[calc(100vh-15rem)] xl:items-center xl:justify-center">
        <div className="grid w-full max-w-[78rem] gap-6 xl:grid-cols-[minmax(0,1.12fr)_minmax(21rem,0.88fr)] xl:items-center">
          <section className="relative min-h-[38rem] overflow-hidden rounded-[34px] bg-[radial-gradient(circle_at_center,rgba(255,138,61,0.08),transparent_24%)]">
            <div className="relative min-h-[38rem]">
              <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                {[16, 28, 40].map((radius) => <circle key={radius} cx="50" cy="50" r={radius} fill="none" stroke="rgba(67,44,27,0.08)" strokeDasharray="1.8 3.4" />)}
                {graphEdges.map(([fromId, toId]) => {
                  const from = graphNodes.find((node) => node.id === fromId)
                  const to = graphNodes.find((node) => node.id === toId)
                  return from && to ? <line key={`${fromId}-${toId}`} x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="rgba(67,44,27,0.22)" strokeWidth="0.45" /> : null
                })}
              </svg>

              {graphNodes.map((node) => (
                <button
                  key={node.id}
                  type="button"
                  onClick={() => setSelectedId(node.id)}
                  className={`absolute -translate-x-1/2 -translate-y-1/2 rounded-full border px-3 py-2 text-xs font-bold tracking-[0.08em] transition ${selectedId === node.id ? 'scale-105 ring-2 ring-brand-orange/25' : 'hover:scale-105'} ${node.kind === 'center' ? 'border-brand-text bg-brand-text text-white shadow-card' : node.kind === 'monitor' ? 'border-brand-orange/20 bg-brand-orange/14 text-brand-text' : 'border-brand-text/12 bg-white text-brand-text'}`}
                  style={{ left: `${node.x}%`, top: `${node.y}%` }}
                >
                  {node.label}
                </button>
              ))}

              <div className="absolute bottom-7 left-1/2 w-[min(90%,32rem)] -translate-x-1/2 rounded-[22px] border border-brand-text/6 bg-white/90 px-5 py-4 text-center shadow-sm backdrop-blur">
                <div className="text-sm font-black text-brand-text">{selectedNode.label}</div>
                <p className="mt-1 text-xs leading-5 text-brand-muted">{selectedNode.detail}</p>
              </div>
            </div>
          </section>

          <div className="space-y-5">
            <section className="space-y-3 rounded-[32px] border border-brand-text/6 bg-white p-6 shadow-[0_20px_60px_-42px_rgba(67,44,27,0.22)] sm:p-7">
              <SimpleRow icon={<UserRound className="h-4 w-4" />} label="当前账号" content={accountSummary()} />
              <SimpleRow icon={<Bell className="h-4 w-4" />} label="价格提醒" content={`${activeAlerts.length} 条监控中 · ${data.alerts.length} 条已保存`} />
              <SimpleRow icon={<MessageSquareText className="h-4 w-4" />} label="查询与记忆" content={`${data.queries.length} 次查询 · ${data.memories.length} 项记忆`} />
              <SimpleRow icon={<Clock3 className="h-4 w-4" />} label="数据连接" content="Mobile 与网页端共用生产 API 和账号令牌" />
            </section>

            <section className="rounded-[28px] border border-brand-text/6 bg-white p-5">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-black text-brand-text">后端价格提醒</h2>
                <span className="text-[10px] font-bold text-brand-orange">实时读取</span>
              </div>
              <div className="mt-3 space-y-2">
                {data.alerts.length ? data.alerts.slice(0, 4).map((alert) => (
                  <div key={alert.id} className="flex items-center justify-between gap-3 rounded-2xl bg-brand-bg px-4 py-3">
                    <div className="min-w-0">
                      <div className="text-sm font-black text-brand-text">{alert.origin} → {alert.destination}</div>
                      <div className="mt-1 text-[11px] text-brand-muted">{alert.depart_date} · {alert.status === 'triggered' ? '已触发' : '监控中'}</div>
                    </div>
                    <div className="shrink-0 text-sm font-black text-brand-orange">≤ ¥{alert.target_price}</div>
                  </div>
                )) : (
                  <div className="rounded-2xl border border-dashed border-brand-text/10 px-4 py-6 text-center">
                    <Search className="mx-auto h-5 w-5 text-brand-muted" />
                    <p className="mt-2 text-xs leading-5 text-brand-muted">从航班卡创建提醒后，网页和 Mobile 都会显示在这里。</p>
                  </div>
                )}
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  )
}

function SimpleRow({ icon, label, content }: { icon: React.ReactNode; label: string; content: string }) {
  return (
    <div className="flex items-center gap-3 rounded-[22px] border border-brand-text/5 bg-brand-bg/35 px-4 py-4">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-brand-orange/10 text-brand-orange">{icon}</div>
      <div className="min-w-0">
        <div className="text-sm font-bold text-brand-text">{label}</div>
        <div className="mt-1 truncate text-sm text-brand-muted">{content}</div>
      </div>
    </div>
  )
}
