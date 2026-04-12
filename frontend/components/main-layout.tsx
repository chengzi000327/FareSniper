'use client'

import React from 'react'
import { ArrowLeft, Compass, History, MessageSquare, User } from 'lucide-react'
import { ChatPage } from '@/components/chat-page'
import { ExplorePage } from '@/components/explore-page'
import { MemoryPage } from '@/components/memory-page'
import { PersonalPage } from '@/components/personal-page'
import { SidebarItem } from '@/components/shared-components'

type Tab = 'chat' | 'explore' | 'memory' | 'personal'

export function MainLayout({ onBack }: { onBack: () => void }) {
  const [activeTab, setActiveTab] = React.useState<Tab>('chat')

  return (
    <div className="flex min-h-screen flex-col bg-brand-bg lg:h-screen lg:flex-row lg:overflow-hidden">
      <aside className="flex items-center justify-between border-b border-brand-text/10 px-4 py-4 lg:sticky lg:top-0 lg:z-20 lg:h-screen lg:w-16 lg:shrink-0 lg:flex-col lg:border-b-0 lg:border-r lg:bg-brand-bg lg:px-0 lg:py-8">
        <button
          onClick={onBack}
          className="flex h-10 w-10 items-center justify-center rounded-2xl text-brand-muted transition hover:bg-brand-text/5 hover:text-brand-text"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>

        <div className="flex items-center gap-4 lg:flex-col lg:gap-8">
          <SidebarItem icon={<MessageSquare />} active={activeTab === 'chat'} onClick={() => setActiveTab('chat')} label="对话" />
          <SidebarItem icon={<Compass />} active={activeTab === 'explore'} onClick={() => setActiveTab('explore')} label="探索" />
          <SidebarItem icon={<History />} active={activeTab === 'memory'} onClick={() => setActiveTab('memory')} label="记忆" />
          <SidebarItem icon={<User />} active={activeTab === 'personal'} onClick={() => setActiveTab('personal')} label="个人" />
        </div>

        <div className="hidden lg:block lg:h-10 lg:w-10" />
      </aside>

      <main className="min-h-[calc(100vh-76px)] flex-1 lg:min-h-0 lg:overflow-hidden">
        {activeTab === 'chat' && <ChatPage />}
        {activeTab === 'explore' && <ExplorePage />}
        {activeTab === 'memory' && <MemoryPage />}
        {activeTab === 'personal' && <PersonalPage />}
      </main>
    </div>
  )
}
