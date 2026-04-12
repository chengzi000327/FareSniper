'use client'

import React from 'react'
import { Bell, BellOff, CheckCircle, Trash2 } from 'lucide-react'

type Alert = {
  id: string
  from: string
  to: string
  targetPrice: number
  isActive: boolean
}

const initialAlerts: Alert[] = [
  { id: '1', from: '上海', to: '三亚', targetPrice: 520, isActive: true },
  { id: '2', from: '北京', to: '东京', targetPrice: 899, isActive: false },
]

export function AlertList() {
  const [alerts, setAlerts] = React.useState<Alert[]>(initialAlerts)
  const [message, setMessage] = React.useState<{ type: 'success'; text: string } | null>(null)

  const showMessage = (text: string) => {
    setMessage({ type: 'success', text })
    window.setTimeout(() => setMessage(null), 3000)
  }

  const handleToggle = (id: string) => {
    setAlerts((current) =>
      current.map((alert) => (alert.id === id ? { ...alert, isActive: !alert.isActive } : alert)),
    )
    const alert = alerts.find((item) => item.id === id)
    showMessage(`监控已${alert?.isActive ? '禁用' : '启用'}`)
  }

  const handleDelete = (id: string) => {
    setAlerts((current) => current.filter((alert) => alert.id !== id))
    showMessage('监控已删除')
  }

  if (alerts.length === 0) {
    return (
      <div className="rounded-[24px] border border-brand-text/5 bg-brand-bg px-5 py-6 text-sm text-brand-muted">
        当前没有监控航线。后面接你自己的后端接口时，这里再改成真实数据。
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {message ? (
        <div className="flex items-center gap-2 rounded-2xl bg-green-100 p-4 text-sm text-green-800">
          <CheckCircle className="h-4 w-4" />
          {message.text}
        </div>
      ) : null}

      {alerts.map((alert) => (
        <div key={alert.id} className="flex items-center justify-between gap-4 rounded-[24px] border border-brand-text/5 bg-white p-5 shadow-sm">
          <div>
            <h3 className="text-lg font-bold text-brand-text">
              {alert.from} → {alert.to}
            </h3>
            <p className="mt-1 text-sm text-brand-muted">目标价格: ¥{alert.targetPrice}</p>
          </div>

          <div className="flex items-center gap-2">
            <button type="button" onClick={() => handleToggle(alert.id)} className="rounded-full p-2 transition hover:bg-brand-bg">
              {alert.isActive ? <Bell className="h-5 w-5" /> : <BellOff className="h-5 w-5" />}
            </button>
            <button type="button" onClick={() => handleDelete(alert.id)} className="rounded-full p-2 text-red-500 transition hover:bg-red-50">
              <Trash2 className="h-5 w-5" />
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
