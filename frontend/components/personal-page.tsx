'use client'

import React from 'react'
import {
  Bell,
  Clock3,
  Headphones,
  Mail,
  MessageSquareText,
  Phone,
  Settings2,
  Ticket,
  UserRound,
} from 'lucide-react'

type GraphNode = {
  id: string
  label: string
  kind: 'center' | 'monitor' | 'chat' | 'support'
  x: number
  y: number
  detail: string
}

const graphNodes: GraphNode[] = [
  { id: 'me', label: '我的发现台', kind: 'center', x: 50, y: 50, detail: '你当前关注的价格监控、对话历史和最近活跃的特价线索。' },
  { id: 'monitor-root', label: '价格监控', kind: 'monitor', x: 27, y: 32, detail: '集中整理你正在盯的航线和目标价。' },
  { id: 'chat-root', label: '对话历史', kind: 'chat', x: 73, y: 30, detail: '回看你最近说过的需求、预算和出发计划。' },
  { id: 'trip-1', label: '上海 → 三亚', kind: 'monitor', x: 19, y: 58, detail: '目标价 ¥520，当前已接近低位，可继续盯。' },
  { id: 'trip-2', label: '北京 → 东京', kind: 'monitor', x: 33, y: 73, detail: '暑假前后价格仍在波动，适合持续关注。' },
  { id: 'chat-1', label: '五一预算 600', kind: 'chat', x: 68, y: 70, detail: '你最近最明确的一次询价需求，方向是三亚。' },
  { id: 'chat-2', label: '周末快闪灵感', kind: 'chat', x: 82, y: 54, detail: '系统记得你最近想找短假快闪型目的地。' },
  { id: 'note', label: '最近提醒', kind: 'support', x: 47, y: 18, detail: '过去 7 天里有 2 条价格提醒被触发。' },
]

const graphEdges: Array<[string, string]> = [
  ['me', 'monitor-root'],
  ['me', 'chat-root'],
  ['me', 'note'],
  ['monitor-root', 'trip-1'],
  ['monitor-root', 'trip-2'],
  ['chat-root', 'chat-1'],
  ['chat-root', 'chat-2'],
  ['trip-1', 'chat-1'],
]

const notificationSettings = [
  { label: '降价提醒', description: '关注航线一旦低于心理价位，立刻提醒', enabled: true },
  { label: '节假日特价提醒', description: '围绕你的常看路线推送节假日窗口价', enabled: true },
  { label: '关注行程动态', description: '行李额、税费或平台差价变化时提醒', enabled: false },
]

export function PersonalPage() {
  const [selectedId, setSelectedId] = React.useState('me')
  const selectedNode = graphNodes.find((node) => node.id === selectedId) ?? graphNodes[0]

  return (
    <div className="thin-scrollbar h-full overflow-y-auto px-5 py-6 sm:px-8 lg:px-12 lg:py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-brand-text sm:text-4xl">个人中心</h1>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-brand-muted sm:text-base">
          这里不是普通设置页，而是你的特价机票发现台。左边是你最近的发现关系，右边是信息、提醒和帮助入口。
        </p>
      </div>

      <div className="xl:flex xl:min-h-[calc(100vh-15rem)] xl:items-center xl:justify-center">
        <div className="grid w-full max-w-[78rem] gap-6 xl:grid-cols-[minmax(0,1.12fr)_minmax(21rem,0.88fr)] xl:items-center">
        <section className="relative min-h-[38rem] overflow-hidden rounded-[34px] bg-[radial-gradient(circle_at_center,rgba(255,138,61,0.08),transparent_24%)]">
          <div className="relative min-h-[38rem]">
            <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              <defs>
                <radialGradient id="graphGlow" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="rgba(255,138,61,0.12)" />
                  <stop offset="100%" stopColor="rgba(255,138,61,0)" />
                </radialGradient>
              </defs>
              <circle cx="50" cy="50" r="8" fill="url(#graphGlow)" />
              {[16, 28, 40].map((radius) => (
                <circle key={radius} cx="50" cy="50" r={radius} fill="none" stroke="rgba(67,44,27,0.08)" strokeDasharray="1.8 3.4" />
              ))}
              {graphEdges.map(([fromId, toId]) => {
                const from = graphNodes.find((node) => node.id === fromId)
                const to = graphNodes.find((node) => node.id === toId)
                if (!from || !to) return null
                return (
                  <line
                    key={`${fromId}-${toId}`}
                    x1={from.x}
                    y1={from.y}
                    x2={to.x}
                    y2={to.y}
                    stroke="rgba(67,44,27,0.22)"
                    strokeWidth="0.45"
                  />
                )
              })}
            </svg>

            {graphNodes.map((node) => {
              const isSelected = node.id === selectedId
              const colorClass =
                node.kind === 'center'
                  ? 'bg-brand-text text-white border-brand-text shadow-card'
                  : node.kind === 'monitor'
                    ? 'bg-brand-orange/14 text-brand-text border-brand-orange/20'
                    : node.kind === 'chat'
                      ? 'bg-white text-brand-text border-brand-text/12'
                      : 'bg-brand-bg text-brand-text border-brand-text/10'

              return (
                <button
                  key={node.id}
                  type="button"
                  onClick={() => setSelectedId(node.id)}
                  className={`absolute -translate-x-1/2 -translate-y-1/2 rounded-full border px-3 py-2 text-xs font-bold tracking-[0.12em] transition ${
                    isSelected ? 'scale-105 ring-2 ring-brand-orange/25' : 'hover:scale-105'
                  } ${colorClass}`}
                  style={{ left: `${node.x}%`, top: `${node.y}%` }}
                >
                  {node.label}
                </button>
              )
            })}
          </div>
        </section>

        <div className="space-y-6">
          <section className="space-y-4 rounded-[32px] border border-brand-text/6 bg-white p-6 shadow-[0_20px_60px_-42px_rgba(67,44,27,0.22)] sm:p-7">
            <SimpleRow
              icon={<UserRound className="h-4 w-4" />}
              label="账号与基础信息"
              content="me@faresniper.ai · 手机号登录 · 上海 / 北京 · 今天活跃"
            />
            {notificationSettings.map((item) => (
              <SimpleToggleRow
                key={item.label}
                icon={<Bell className="h-4 w-4" />}
                label={item.label}
                description={item.description}
                enabled={item.enabled}
              />
            ))}
            <SimpleRow
              icon={<Headphones className="h-4 w-4" />}
              label="客服与帮助"
              content="在线客服 · 邮件反馈 · 联系我们"
            />
          </section>
        </div>
        </div>
      </div>
    </div>
  )
}

function SimpleRow({
  icon,
  label,
  content,
}: {
  icon: React.ReactNode
  label: string
  content: string
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-[22px] border border-brand-text/5 bg-brand-bg/35 px-4 py-4">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-brand-orange/10 text-brand-orange">
          {icon}
        </div>
        <div className="min-w-0">
          <div className="text-sm font-bold text-brand-text">{label}</div>
          <div className="mt-1 truncate text-sm text-brand-muted">{content}</div>
        </div>
      </div>
    </div>
  )
}

function SimpleToggleRow({
  icon,
  label,
  description,
  enabled,
}: {
  icon: React.ReactNode
  label: string
  description: string
  enabled: boolean
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-[22px] border border-brand-text/5 bg-brand-bg/35 px-4 py-4">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-brand-orange/10 text-brand-orange">
          {icon}
        </div>
        <div className="min-w-0">
          <div className="text-sm font-bold text-brand-text">{label}</div>
          <div className="mt-1 text-sm text-brand-muted">{description}</div>
        </div>
      </div>
      <div
        className={`flex h-7 w-12 shrink-0 rounded-full p-1 transition ${
          enabled ? 'justify-end bg-brand-text' : 'justify-start bg-brand-text/10'
        }`}
      >
        <div className="h-5 w-5 rounded-full bg-white shadow-sm" />
      </div>
    </div>
  )
}
