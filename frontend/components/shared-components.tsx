'use client'

import React from 'react'
import { motion } from 'motion/react'
import { ChevronRight, Plane } from 'lucide-react'

export function SidebarItem({
  icon,
  active,
  onClick,
  label,
}: {
  icon: React.ReactNode
  active: boolean
  onClick: () => void
  label: string
}) {
  return (
    <div className="group flex flex-col items-center gap-1">
      <motion.button
        type="button"
        onClick={onClick}
        whileHover={{ scale: 1.08 }}
        className={`flex h-10 w-10 items-center justify-center rounded-2xl transition ${
          active ? 'bg-brand-text text-white shadow-card' : 'text-brand-muted hover:bg-brand-text/5 hover:text-brand-text'
        }`}
      >
        {React.cloneElement(icon as React.ReactElement, { className: 'h-5 w-5' })}
      </motion.button>
      <span className={`text-[11px] font-bold tracking-tight ${active ? 'text-brand-text' : 'text-brand-muted'}`}>
        {label}
      </span>
    </div>
  )
}

export function RecommendationCard({ from, to, price, date }: { from: string; to: string; price: string; date: string }) {
  return (
    <motion.div whileHover={{ y: -5 }} className="group cursor-pointer rounded-3xl border border-brand-text/5 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Plane className="h-4 w-4 text-brand-orange" />
          <span className="text-sm font-bold sm:text-base">
            {from} → {to}
          </span>
        </div>
        <ChevronRight className="h-4 w-4 text-brand-muted transition group-hover:translate-x-1" />
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-black text-brand-text sm:text-3xl">¥{price}</span>
        <span className="text-xs text-brand-muted sm:text-sm">{date} · 往返含税</span>
      </div>
    </motion.div>
  )
}
