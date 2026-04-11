'use client'

import { useState } from 'react'
import Link from 'next/link'

const initialMemories = [
  {
    id: 'm001', field: 'price_anchor', label: '心理价位',
    value: '¥600 以内', source: 'auto' as const,
    updatedAt: '3天前', accentColor: '#22C55E', rotation: '-1deg',
  },
  {
    id: 'm002', field: 'preferred_origins', label: '常用出发地',
    value: '北京、上海', source: 'manual' as const,
    updatedAt: '6天前', accentColor: '#1B2B5E', rotation: '2deg',
  },
  {
    id: 'm003', field: 'preferred_destinations', label: '想去的地方',
    value: '三亚、大理、成都', source: 'auto' as const,
    updatedAt: '1天前', accentColor: '#F59E0B', rotation: '-2deg',
  },
  {
    id: 'm004', field: 'travel_window', label: '出行时间偏好',
    value: '周末 / 法定假日', source: 'manual' as const,
    updatedAt: '10天前', accentColor: '#8B5CF6', rotation: '1.5deg',
  },
  {
    id: 'm005', field: 'cabin_preference', label: '舱位偏好',
    value: '经济舱', source: 'auto' as const,
    updatedAt: '15天前', accentColor: '#0EA5E9', rotation: '-1.5deg',
  },
]

export default function MemoryPage() {
  const [memories, setMemories] = useState(initialMemories)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')

  const startEdit = (id: string, currentValue: string) => {
    setEditingId(id)
    setEditValue(currentValue)
  }

  const saveEdit = () => {
    if (!editingId) return
    setMemories((prev) =>
      prev.map((m) => (m.id === editingId ? { ...m, value: editValue, updatedAt: '刚刚' } : m))
    )
    setEditingId(null)
  }

  const deleteMemory = (id: string) => {
    setMemories((prev) => prev.filter((m) => m.id !== id))
  }

  return (
    <div className="min-h-screen bg-bg-gray font-sans">

      {/* ── NAV ────────────────────────────────────────── */}
      <nav className="flex items-center justify-between px-8 py-5 border-b border-gray-100 bg-bg-gray/80 backdrop-blur-sm sticky top-0 z-10">
        <Link
          href="/chat"
          className="flex items-center gap-2 text-gray-400 hover:text-navy text-sm transition-colors group"
        >
          <svg className="w-4 h-4 transition-transform group-hover:-translate-x-0.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10 13L5 8l5-5" />
          </svg>
          返回对话
        </Link>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-navy" />
          <span className="font-mono text-[11px] tracking-[0.18em] text-navy/40 uppercase">FareSniper</span>
        </div>
        <div className="w-8 h-8 rounded-full bg-navy flex items-center justify-center text-white text-xs font-semibold">
          我
        </div>
      </nav>

      {/* ── CONTENT ────────────────────────────────────── */}
      <div className="max-w-[480px] mx-auto px-6 py-12">

        {/* Header */}
        <div className="mb-10">
          <p className="font-mono text-[11px] tracking-[0.18em] text-gray-300 uppercase mb-3">
            MEMORY · {memories.length} 条记忆
          </p>
          <h1 className="font-heading text-[2.6rem] font-bold text-navy leading-tight">
            系统记住的你
          </h1>
          <p className="text-gray-400 text-sm mt-2">
            来自你的对话与手动设置 · 随时可编辑
          </p>
        </div>

        {/* Memory card stack */}
        <div className="space-y-3">
          {memories.map((memory, i) => (
            <div
              key={memory.id}
              className="group transition-all duration-300 hover:z-10 relative"
              style={{
                transform: `rotate(${memory.rotation})`,
                zIndex: memories.length - i,
              }}
              onMouseEnter={(e) => {
                ;(e.currentTarget as HTMLElement).style.transform = 'rotate(0deg) translateY(-2px)'
              }}
              onMouseLeave={(e) => {
                ;(e.currentTarget as HTMLElement).style.transform = `rotate(${memory.rotation})`
              }}
            >
              <div className="bg-white rounded-3xl overflow-hidden shadow-card hover:shadow-card-hover transition-shadow duration-300">
                {/* Accent strip */}
                <div
                  className="h-1 w-full"
                  style={{ backgroundColor: memory.accentColor }}
                />

                <div className="p-6">
                  {/* Header row */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2.5">
                      <div
                        className="w-7 h-7 rounded-xl flex items-center justify-center text-white text-xs font-bold"
                        style={{ backgroundColor: memory.accentColor }}
                      >
                        {memory.label.charAt(0)}
                      </div>
                      <span className="font-mono text-[11px] text-gray-400 uppercase tracking-wider">
                        {memory.label}
                      </span>
                    </div>

                    {/* Edit / Delete — visible on hover */}
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                      <button
                        onClick={() => startEdit(memory.id, memory.value)}
                        className="text-gray-300 hover:text-navy text-xs px-2.5 py-1.5 rounded-lg hover:bg-gray-50 transition-all"
                      >
                        编辑
                      </button>
                      <button
                        onClick={() => deleteMemory(memory.id)}
                        className="text-gray-300 hover:text-red-400 text-xs px-2.5 py-1.5 rounded-lg hover:bg-red-50 transition-all"
                      >
                        删除
                      </button>
                    </div>
                  </div>

                  {/* Value */}
                  {editingId === memory.id ? (
                    <div className="flex gap-2">
                      <input
                        autoFocus
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') saveEdit()
                          if (e.key === 'Escape') setEditingId(null)
                        }}
                        className="flex-1 border border-navy/20 rounded-xl px-3 py-2 text-navy text-sm outline-none focus:border-navy/40 bg-navy-50/50"
                      />
                      <button
                        onClick={saveEdit}
                        className="bg-navy text-white text-xs font-medium px-3 py-2 rounded-xl hover:bg-navy-light transition-colors"
                      >
                        保存
                      </button>
                    </div>
                  ) : (
                    <p className="font-heading text-[1.6rem] font-bold text-navy leading-tight">
                      {memory.value}
                    </p>
                  )}

                  {/* Footer */}
                  <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-50">
                    <span
                      className={`text-xs font-medium px-2.5 py-1 rounded-full ${
                        memory.source === 'auto'
                          ? 'bg-signal-muted text-signal-text'
                          : 'bg-navy-50 text-navy-muted'
                      }`}
                    >
                      {memory.source === 'auto' ? '系统归纳' : '手动设置'}
                    </span>
                    <span className="text-gray-300 text-xs">{memory.updatedAt}更新</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Add button */}
        <button className="w-full mt-4 border-2 border-dashed border-gray-200 rounded-3xl py-5 text-gray-300 text-sm hover:border-navy/20 hover:text-navy/40 hover:bg-white transition-all duration-200 flex items-center justify-center gap-2">
          <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M8 3v10M3 8h10" />
          </svg>
          添加偏好
        </button>
      </div>
    </div>
  )
}
