'use client'

import React from 'react'
import {
  ArrowLeft,
  Bell,
  BookHeart,
  Check,
  ChevronRight,
  Clock3,
  Compass,
  Gift,
  Heart,
  LockKeyhole,
  MapPin,
  MessageCircle,
  PencilLine,
  Plane,
  Plus,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserCheck,
  UserRound,
  X,
} from 'lucide-react'
import { ChatPage } from '@/components/chat-page'
import { formatCurrency } from '@/lib/currency'
import { alertsApi, authApi, memoryApi, recApi } from '@/lib/api'
import type { AlertItemDto, MemoryItemDto, QueryHistoryItemDto, RecCardDto } from '@/lib/api'

type MobileTab = 'explore' | 'chat' | 'memory' | 'profile'

type MobileMemory = {
  memories: MemoryItemDto[]
  query_history: QueryHistoryItemDto[]
}

type TravelIdea = {
  id: string
  text: string
  created_at: string
}

type CompanionKind = 'cat' | 'corgi' | 'penguin' | 'plain'
type CompanionPose = 'idle' | 'journal'
type MobileMemorySection = 'preferences' | 'ideas' | 'queries' | 'journal'
type MobileAccount = {
  userId: string | null
  phone: string | null
  loggedIn: boolean
}

const COMPANION_ASSETS: Record<Exclude<CompanionKind, 'plain'>, string> = {
  cat: '/companions/cloud-cat-actions.png',
  corgi: '/companions/boarding-corgi-actions.png',
  penguin: '/companions/migratory-penguin-actions.png',
}

const COMPANION_DEFAULTS: Record<CompanionKind, string> = {
  cat: '云朵',
  corgi: '登登',
  penguin: '小候',
  plain: '旅伴',
}

const COMPANION_CHOICES: Array<{ kind: Exclude<CompanionKind, 'plain'>; title: string; detail: string }> = [
  { kind: 'cat', title: '云朵猫', detail: '安静记下每个想法' },
  { kind: 'corgi', title: '登登柯基', detail: '发现低价就来找你' },
  { kind: 'penguin', title: '小候企鹅', detail: '陪你等待出发时机' },
]

const INTERNAL_MEMORY_FIELDS = new Set(['companion_profile', 'travel_ideas'])
const ARRAY_MEMORY_FIELDS = new Set(['frequent_cities', 'preferred_airlines', 'constraints', 'travel_scenes'])
const PREFERENCE_OPTIONS = [
  { field: 'budget', label: '心理价位' },
  { field: 'frequent_cities', label: '常去城市' },
  { field: 'preferred_airlines', label: '偏好航司' },
  { field: 'constraints', label: '出行习惯' },
  { field: 'travel_scenes', label: '出行场景' },
] as const
const MEMORY_VALUE_CODES: Record<string, string> = {
  只看直飞: 'direct_only',
  避开红眼航班: 'avoid_redeye',
  偏好上午出发: 'prefer_morning',
  偏好靠窗座位: 'prefer_window',
  不要中转: 'avoid_stopover',
  需要托运行李: 'checked_baggage',
  只带随身行李: 'carry_on_only',
  商务出行: 'business',
  休闲旅行: 'leisure',
  探亲回家: 'family_visit',
  回家: 'return_home',
  家庭出行: 'with_family',
  亲子出行: 'with_children',
  独自出行: 'solo',
}
const MEMORY_CODE_LABELS = Object.fromEntries(
  Object.entries(MEMORY_VALUE_CODES).map(([label, code]) => [code, label]),
)
const POSE_POSITION: Record<CompanionPose, [number, number]> = {
  idle: [0, 0],
  journal: [2, 1],
}
const MOBILE_DESTINATION_IMAGES: Record<string, string> = {
  SHA: '/images/destinations/SHA.jpg',
  SYX: '/images/destinations/SYX.jpg',
  CTU: '/images/destinations/CTU.jpg',
  CAN: '/images/destinations/CAN.jpg',
  XMN: '/images/destinations/XMN.jpg',
}
const MOBILE_DESTINATION_CODES: Record<string, string> = {
  上海: 'SHA',
  三亚: 'SYX',
  成都: 'CTU',
  广州: 'CAN',
  厦门: 'XMN',
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function readMobileAccount(): MobileAccount {
  if (typeof window === 'undefined') return { userId: null, phone: null, loggedIn: false }
  const userId = window.localStorage.getItem('fs_user_id')
  const phone = window.localStorage.getItem('fs_phone')
  return {
    userId,
    phone,
    loggedIn: !!userId && !userId.startsWith('anon_'),
  }
}

function maskPhone(phone: string | null) {
  if (!phone) return '已绑定手机号'
  const digits = phone.replace(/\D/g, '')
  return digits.length >= 11 ? `${digits.slice(-11, -7)}****${digits.slice(-4)}` : phone
}

function shortAccountId(userId: string | null) {
  if (!userId) return ''
  const compact = userId.replace(/[^a-zA-Z0-9]/g, '')
  return compact.slice(-8).toUpperCase()
}

function normalizePhone(phone: string) {
  const value = phone.trim().replace(/[\s-]/g, '')
  if (value.startsWith('+')) return value
  return /^1\d{10}$/.test(value) ? `+86${value}` : value
}

function companionFromMemory(memories: MemoryItemDto[]) {
  const raw = memories.find((memory) => memory.field === 'companion_profile')?.value
  const profile = asRecord(raw)
  const kind = profile?.kind
  const selectedKind: CompanionKind = kind === 'corgi' || kind === 'penguin' || kind === 'plain' ? kind : 'cat'
  const name = typeof profile?.name === 'string' && profile.name.trim()
    ? profile.name.trim()
    : COMPANION_DEFAULTS[selectedKind]
  return { kind: selectedKind, name }
}

function explicitIdeaCount(memories: MemoryItemDto[]) {
  const value = memories.find((memory) => memory.field === 'travel_ideas')?.value
  return Array.isArray(value) ? value.length : 0
}

function travelIdeas(memories: MemoryItemDto[]): TravelIdea[] {
  const value = memories.find((memory) => memory.field === 'travel_ideas')?.value
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    const record = asRecord(item)
    return typeof record?.id === 'string' && typeof record.text === 'string' && typeof record.created_at === 'string'
      ? [{ id: record.id, text: record.text, created_at: record.created_at }]
      : []
  })
}

function shortDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.slice(0, 10)
  return new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', timeZone: 'Asia/Shanghai' }).format(date)
}

function queryText(item: QueryHistoryItemDto) {
  const query = asRecord(item.query)
  return typeof query?.text === 'string' && query.text.trim() ? query.text.trim() : '一次机票查询'
}

function preferenceDraft(memory: MemoryItemDto) {
  if (typeof memory.value === 'number') return String(memory.value)
  if (Array.isArray(memory.value)) {
    return memory.value.map((item) => {
      const text = String(item)
      return MEMORY_CODE_LABELS[text] ?? (/^[a-z][a-z0-9_]*$/.test(text) ? '其他偏好' : text)
    }).join('、')
  }
  return typeof memory.value === 'string' ? memory.value : memory.value_display
}

function parsePreferenceDraft(field: string, draft: string): number | string[] | string {
  const value = draft.trim()
  if (field === 'budget') {
    const budget = Number(value.replace(/[^\d.]/g, ''))
    if (!Number.isFinite(budget) || budget <= 0) throw new Error('请输入正确的心理价位')
    return Math.round(budget)
  }
  if (ARRAY_MEMORY_FIELDS.has(field)) {
    const values = value.split(/[、,，\n]/).map((item) => item.trim()).filter(Boolean)
    if (!values.length) throw new Error('请至少保留一项偏好')
    return [...new Set(values.map((item) => MEMORY_VALUE_CODES[item] ?? item))]
  }
  if (!value) throw new Error('偏好内容不能为空')
  return value
}

function MobileCompanion({ kind, pose = 'idle' }: { kind: CompanionKind; pose?: CompanionPose }) {
  if (kind === 'plain') {
    return (
      <div className="grid aspect-square w-full place-items-center rounded-[32px] bg-brand-text text-white">
        <Sparkles className="h-8 w-8" />
      </div>
    )
  }
  const [column, row] = POSE_POSITION[pose]
  return (
    <div className="relative aspect-square w-full overflow-hidden rounded-[32px] bg-[#fffaf1]">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={COMPANION_ASSETS[kind]}
        alt={pose === 'journal' ? '旅伴正在写手帐' : '查价旅伴'}
        className="pointer-events-none absolute left-0 top-0 h-[200%] w-[300%] max-w-none select-none"
        style={{ transform: `translate(${-column * 33.333333}%, ${-row * 50}%)` }}
      />
    </div>
  )
}

function recommendationTitle(card: RecCardDto) {
  if (card.preview_deal) {
    return `${card.preview_deal.origin_city} → ${card.preview_deal.destination_city}`
  }
  return card.title?.trim() || '新的航线发现'
}

function recommendationPrice(card: RecCardDto) {
  const deal = card.preview_deal
  if (!deal) return '查询实时价格'
  return formatCurrency(deal.total_price ?? deal.price, deal.currency)
}

function recommendationImage(card: RecCardDto) {
  const destination = card.preview_deal?.destination_city
    ?? recommendationTitle(card).split('→').at(-1)?.trim()
    ?? ''
  const code = card.preview_deal?.destination_code ?? MOBILE_DESTINATION_CODES[destination] ?? destination
  return MOBILE_DESTINATION_IMAGES[code]
    ?? `https://picsum.photos/seed/${encodeURIComponent(code || destination || 'trip')}/640/760`
}

export function MobileAppPage() {
  const [activeTab, setActiveTab] = React.useState<MobileTab>('chat')
  const [chatQuery, setChatQuery] = React.useState<string | null>(null)
  const [memory, setMemory] = React.useState<MobileMemory>({ memories: [], query_history: [] })
  const [recommendations, setRecommendations] = React.useState<RecCardDto[]>([])
  const [alerts, setAlerts] = React.useState<AlertItemDto[]>([])
  const [loading, setLoading] = React.useState(true)
  const [memoryState, setMemoryState] = React.useState<'loading' | 'ready' | 'error'>('loading')
  const [account, setAccount] = React.useState<MobileAccount>({ userId: null, phone: null, loggedIn: false })
  const [phoneLoginAvailable, setPhoneLoginAvailable] = React.useState(false)
  const [choosingCompanion, setChoosingCompanion] = React.useState(false)

  const loadData = React.useCallback(() => {
    let active = true
    setLoading(true)
    Promise.allSettled([
      memoryApi.get(),
      recApi.list({ limit: 6, offset: 0 }),
      alertsApi.list(),
    ]).then(([memoryResult, recommendationResult, alertsResult]) => {
      if (!active) return
      if (memoryResult.status === 'fulfilled') {
        setMemory({
          memories: memoryResult.value.memories ?? [],
          query_history: memoryResult.value.query_history ?? [],
        })
        setMemoryState('ready')
        setAccount(readMobileAccount())
      } else {
        setMemoryState('error')
      }
      if (recommendationResult.status === 'fulfilled') {
        setRecommendations(recommendationResult.value.cards ?? [])
      }
      if (alertsResult.status === 'fulfilled') {
        setAlerts(alertsResult.value.alerts ?? [])
      }
      setLoading(false)
    })
    return () => { active = false }
  }, [])

  React.useEffect(() => loadData(), [loadData])

  React.useEffect(() => {
    let active = true
    authApi.status()
      .then((status) => { if (active) setPhoneLoginAvailable(status.phone_login_available) })
      .catch(() => { if (active) setPhoneLoginAvailable(false) })
    return () => { active = false }
  }, [])

  const startChat = (query: string) => {
    const value = query.trim()
    if (!value) return
    setChatQuery(value)
    setActiveTab('chat')
  }

  const savedCompanion = (profile: { kind: CompanionKind; name: string }) => {
    const companionMemory: MemoryItemDto = {
      field: 'companion_profile',
      value: profile,
      label: '旅伴档案',
      value_display: profile.name,
      source: 'manual',
    }
    setMemory((current) => ({
      ...current,
      memories: [companionMemory, ...current.memories.filter((item) => item.field !== 'companion_profile')],
    }))
    setChoosingCompanion(false)
  }

  const accountChanged = () => {
    setAccount(readMobileAccount())
    loadData()
  }

  const hasCompanion = memory.memories.some((item) => item.field === 'companion_profile')
  const showingCompanionSetup = memoryState === 'ready' && (!hasCompanion || choosingCompanion)

  return (
    <div className="min-h-[100dvh] bg-[#eadfd4] sm:grid sm:place-items-center sm:p-4">
      <main className="relative flex h-[100dvh] w-full flex-col overflow-hidden bg-brand-bg sm:h-[min(874px,calc(100dvh-2rem))] sm:w-[402px] sm:max-w-[calc(100vw-2rem)] sm:rounded-[52px] sm:border-[7px] sm:border-brand-text sm:shadow-[0_30px_90px_rgba(67,44,27,0.28)]">
        <div className="pointer-events-none absolute left-1/2 top-2 z-50 hidden h-7 w-[7.6rem] -translate-x-1/2 rounded-full bg-black sm:block" aria-hidden="true" />
        <div className="min-h-0 flex-1 overflow-hidden sm:pt-6">
          {memoryState === 'loading' ? (
            <MobileLaunchScreen />
          ) : memoryState === 'error' ? (
            <MobileLoadError onRetry={loadData} />
          ) : showingCompanionSetup ? (
            <MobileCompanionOnboarding
              current={hasCompanion ? companionFromMemory(memory.memories) : null}
              phoneLoginAvailable={phoneLoginAvailable}
              onSaved={savedCompanion}
              onAccountChanged={accountChanged}
              onCancel={hasCompanion ? () => setChoosingCompanion(false) : undefined}
            />
          ) : activeTab === 'explore' ? (
            <MobileExploreHome
              loading={loading}
              memory={memory}
              recommendations={recommendations}
              onSearch={startChat}
              onOpenMemory={() => setActiveTab('memory')}
            />
          ) : activeTab === 'chat' ? (
            <ChatPage
              compact
              assistantName={companionFromMemory(memory.memories).name}
              recentQuery={memory.query_history[0] ? queryText(memory.query_history[0]) : null}
              onOpenExplore={() => setActiveTab('explore')}
              initialQuery={chatQuery}
              onInitialQueryConsumed={() => setChatQuery(null)}
              onAlertCreated={loadData}
            />
          ) : activeTab === 'memory' ? (
            <MobileMemoryPage memory={memory} loading={loading} onRefresh={loadData} />
          ) : (
            <MobileProfile
              memory={memory}
              alerts={alerts}
              account={account}
              phoneLoginAvailable={phoneLoginAvailable}
              onAccountChanged={accountChanged}
              onChooseCompanion={() => setChoosingCompanion(true)}
              onOpenMemory={() => setActiveTab('memory')}
              onOpenChat={() => setActiveTab('chat')}
            />
          )}
        </div>

        {memoryState === 'ready' && !showingCompanionSetup ? <MobileBottomNav activeTab={activeTab} onChange={setActiveTab} /> : null}
      </main>
    </div>
  )
}

function MobileLaunchScreen() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-10 text-center">
      <div className="grid h-16 w-16 place-items-center rounded-[24px] bg-brand-text text-white shadow-card">
        <Plane className="h-7 w-7" />
      </div>
      <div className="mt-5 font-serif text-3xl font-black text-brand-text">正在接上你的旅程</div>
      <p className="mt-2 text-xs leading-6 text-brand-muted">读取账号、旅伴和机票偏好…</p>
    </div>
  )
}

function MobileLoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-10 text-center">
      <div className="grid h-14 w-14 place-items-center rounded-[22px] bg-brand-orange-light text-brand-orange"><X className="h-6 w-6" /></div>
      <div className="mt-5 text-xl font-black text-brand-text">暂时没有接上记忆</div>
      <p className="mt-2 text-xs leading-6 text-brand-muted">账号数据没有加载成功，请检查网络后重试。</p>
      <button type="button" onClick={onRetry} className="mt-5 h-11 rounded-2xl bg-brand-text px-6 text-sm font-black text-white">重新加载</button>
    </div>
  )
}

function MobileCompanionOnboarding({
  current,
  phoneLoginAvailable,
  onSaved,
  onAccountChanged,
  onCancel,
}: {
  current: { kind: CompanionKind; name: string } | null
  phoneLoginAvailable: boolean
  onSaved: (profile: { kind: CompanionKind; name: string }) => void
  onAccountChanged: () => void
  onCancel?: () => void
}) {
  const [kind, setKind] = React.useState<CompanionKind>(current?.kind ?? 'cat')
  const [name, setName] = React.useState(current?.name ?? COMPANION_DEFAULTS.cat)
  const [saving, setSaving] = React.useState(false)
  const [showLogin, setShowLogin] = React.useState(false)
  const [error, setError] = React.useState('')

  const choose = (nextKind: CompanionKind) => {
    setKind(nextKind)
    setName(COMPANION_DEFAULTS[nextKind])
    setError('')
  }

  const save = async () => {
    const companionName = name.trim()
    if (!companionName) {
      setError('给旅伴取一个名字再出发吧。')
      return
    }
    setSaving(true)
    setError('')
    try {
      await memoryApi.patch({ field: 'companion_profile', value: { kind, name: companionName } })
      onSaved({ kind, name: companionName })
    } catch {
      setError('旅伴暂时没有保存成功，请再试一次。')
    } finally {
      setSaving(false)
    }
  }

  if (showLogin) {
    return (
      <div className="thin-scrollbar h-full overflow-y-auto px-5 pb-8 pt-[max(1.25rem,env(safe-area-inset-top))]">
        <button type="button" onClick={() => setShowLogin(false)} className="inline-flex items-center gap-1 text-xs font-black text-brand-muted"><ArrowLeft className="h-4 w-4" />返回选择旅伴</button>
        <MobileOtpForm onSuccess={() => { setShowLogin(false); onAccountChanged() }} />
      </div>
    )
  }

  return (
    <div className="thin-scrollbar h-full overflow-y-auto px-5 pb-8 pt-[max(1.25rem,env(safe-area-inset-top))]">
      <header className="flex items-start justify-between">
        <div>
          <div className="text-[10px] font-black tracking-[0.2em] text-brand-orange">{current ? '我的旅伴' : '第一次见面'}</div>
          <h1 className="mt-1 font-serif text-[2rem] font-black leading-tight text-brand-text">{current ? '重新选择旅伴' : '先选一个旅伴吧'}</h1>
        </div>
        {onCancel ? <button type="button" aria-label="关闭旅伴选择" onClick={onCancel} className="grid h-10 w-10 place-items-center rounded-2xl bg-white text-brand-muted shadow-sm"><X className="h-4 w-4" /></button> : null}
      </header>
      <p className="mt-3 text-xs leading-6 text-brand-muted">它会陪你查票、记下偏好、发现低价和写旅行手帐，但不会替你做购买决定。</p>

      <div className="mt-5 grid grid-cols-3 gap-2.5">
        {COMPANION_CHOICES.map((choice) => {
          const selected = choice.kind === kind
          return (
            <button key={choice.kind} type="button" aria-pressed={selected} onClick={() => choose(choice.kind)} className={`rounded-[22px] border p-2.5 text-center transition ${selected ? 'border-brand-orange bg-brand-orange-light shadow-sm' : 'border-brand-text/7 bg-white'}`}>
              <div className="mx-auto w-full max-w-[5.2rem]"><MobileCompanion kind={choice.kind} /></div>
              <div className="mt-2 text-xs font-black text-brand-text">{choice.title}</div>
            </button>
          )
        })}
      </div>

      <section className="mt-5 grid grid-cols-[5.5rem_minmax(0,1fr)] items-center gap-4 rounded-[26px] bg-brand-text p-4 text-white">
        <MobileCompanion kind={kind} />
        <div className="min-w-0">
          <div className="text-[10px] font-bold text-white/55">给它取个你喜欢的名字</div>
          <label htmlFor="mobile-companion-name" className="mt-2 block text-xs font-black text-white/80">旅伴名字</label>
          <input id="mobile-companion-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={12} className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-white/10 px-3 text-sm font-black text-white placeholder:text-white/35" />
        </div>
      </section>

      <button type="button" onClick={() => choose('plain')} className={`mt-3 flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-left ${kind === 'plain' ? 'border-brand-orange bg-brand-orange-light' : 'border-brand-text/7 bg-white'}`}>
        <span><span className="block text-xs font-black text-brand-text">暂时不显示宠物</span><span className="mt-1 block text-[10px] text-brand-muted">保留账号和记忆，只使用纯净模式</span></span>
        {kind === 'plain' ? <Check className="h-4 w-4 text-brand-orange" /> : null}
      </button>

      {error ? <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-xs font-bold text-red-700">{error}</p> : null}
      <button type="button" disabled={saving} onClick={() => void save()} className="mt-4 h-12 w-full rounded-2xl bg-brand-orange text-sm font-black text-white shadow-sm disabled:opacity-45">{saving ? '正在保存…' : current ? '保存新的旅伴' : `和${name.trim() || '旅伴'}一起开始`}</button>

      {phoneLoginAvailable && !current ? (
        <button type="button" onClick={() => setShowLogin(true)} className="mt-4 w-full text-center text-xs font-black text-brand-muted">已有账号？先登录，再接回原来的旅伴</button>
      ) : null}
    </div>
  )
}

function MobileOtpForm({ onSuccess }: { onSuccess: () => void }) {
  const [phone, setPhone] = React.useState('')
  const [code, setCode] = React.useState('')
  const [sent, setSent] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState('')

  const requestCode = async () => {
    const normalized = normalizePhone(phone)
    if (!/^\+?\d{8,15}$/.test(normalized)) {
      setError('请输入正确的手机号。')
      return
    }
    setBusy(true)
    setError('')
    try {
      await authApi.requestOtp(normalized)
      setSent(true)
    } catch {
      setError('验证码暂时没有发送成功，请稍后再试。')
    } finally {
      setBusy(false)
    }
  }

  const verify = async () => {
    if (!/^\d{6}$/.test(code.trim())) {
      setError('请输入 6 位验证码。')
      return
    }
    setBusy(true)
    setError('')
    try {
      const normalized = normalizePhone(phone)
      await authApi.verify(normalized, code.trim())
      window.localStorage.setItem('fs_phone', normalized)
      onSuccess()
    } catch {
      setError('验证码不正确或已经过期。')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="mt-6 rounded-[28px] bg-white p-5 shadow-sm">
      <div className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-orange-light text-brand-orange"><LockKeyhole className="h-5 w-5" /></div>
      <h2 className="mt-4 text-xl font-black text-brand-text">手机号登录</h2>
      <p className="mt-2 text-xs leading-6 text-brand-muted">登录后会把这台设备上的偏好、查询、提醒和旅伴接入正式账号。</p>
      <label htmlFor="mobile-account-phone" className="mt-4 block text-xs font-black text-brand-text">手机号</label>
      <input id="mobile-account-phone" value={phone} onChange={(event) => setPhone(event.target.value)} inputMode="tel" placeholder="例如：13800000000" className="mt-2 h-11 w-full rounded-xl border border-brand-text/10 bg-brand-bg px-3 text-sm font-semibold" />
      {sent ? (
        <>
          <label htmlFor="mobile-account-code" className="mt-4 block text-xs font-black text-brand-text">验证码</label>
          <input id="mobile-account-code" value={code} onChange={(event) => setCode(event.target.value)} inputMode="numeric" maxLength={6} placeholder="6 位验证码" className="mt-2 h-11 w-full rounded-xl border border-brand-text/10 bg-brand-bg px-3 text-sm font-semibold tracking-[0.3em]" />
        </>
      ) : null}
      {error ? <p className="mt-3 text-xs font-bold text-red-700">{error}</p> : null}
      <button type="button" disabled={busy} onClick={() => void (sent ? verify() : requestCode())} className="mt-4 h-11 w-full rounded-xl bg-brand-text text-sm font-black text-white disabled:opacity-45">{busy ? '请稍候…' : sent ? '登录并接回数据' : '获取验证码'}</button>
    </section>
  )
}

function MobileExploreHome({
  loading,
  memory,
  recommendations,
  onSearch,
  onOpenMemory,
}: {
  loading: boolean
  memory: MobileMemory
  recommendations: RecCardDto[]
  onSearch: (query: string) => void
  onOpenMemory: () => void
}) {
  const [query, setQuery] = React.useState('')
  const [blindPick, setBlindPick] = React.useState<RecCardDto | null>(null)
  const companion = companionFromMemory(memory.memories)
  const preferenceCount = memory.memories.filter((item) => !INTERNAL_MEMORY_FIELDS.has(item.field)).length
  const ideaCount = explicitIdeaCount(memory.memories)

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    onSearch(query)
  }
  const drawDestination = () => {
    if (!recommendations.length) return
    setBlindPick(recommendations[Math.floor(Math.random() * recommendations.length)])
  }

  return (
    <div className="thin-scrollbar h-full overflow-y-auto px-4 pb-8 pt-[max(1.1rem,env(safe-area-inset-top))]">
      <header className="flex items-center justify-between">
        <div>
          <div className="text-[9px] font-black tracking-[0.12em] text-brand-orange">你的机票发现与出行陪伴 Agent</div>
          <h1 className="mt-1 font-serif text-[2rem] font-black leading-tight text-brand-text">探索灵感</h1>
        </div>
        <button type="button" aria-label="查看提醒" className="grid h-10 w-10 place-items-center rounded-2xl border border-brand-text/8 bg-white text-brand-text shadow-sm">
          <Bell className="h-4 w-4" />
        </button>
      </header>

      <section className="relative mt-4 overflow-hidden rounded-[24px] bg-brand-text p-3.5 text-white shadow-card">
        <div className="absolute -right-6 -top-8 h-24 w-24 rounded-full bg-brand-orange/35 blur-2xl" />
        <div className="relative flex items-center gap-3">
          <div className="w-14 shrink-0"><MobileCompanion kind={companion.kind} /></div>
          <div className="min-w-0 flex-1">
            <div className="text-[10px] font-bold text-white/55">和 {companion.name} 一起逛逛</div>
            <h2 className="mt-0.5 text-base font-black">从真实推荐里发现下一程</h2>
            <div className="mt-1.5 flex gap-3 text-[9px] font-bold text-white/60">
              <span>{preferenceCount} 项偏好</span>
              <span>{ideaCount} 个关注</span>
              <span>{memory.query_history.length} 次查询</span>
            </div>
          </div>
        </div>
      </section>

      <div className="mt-3 grid grid-cols-[minmax(0,1fr)_5.25rem] gap-2.5">
        <form onSubmit={submit} className="flex min-w-0 items-center gap-2 rounded-[20px] border border-brand-orange/15 bg-white p-2.5 pl-3 shadow-sm">
          <Search className="h-4 w-4 shrink-0 text-brand-orange" />
          <input
            id="mobile-flight-query"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="探索页出发计划"
            placeholder="说一个想去的地方"
            className="min-w-0 flex-1 bg-transparent py-1 text-xs font-semibold text-brand-text placeholder:font-normal placeholder:text-brand-muted/65"
          />
          <button type="submit" aria-label="开始查询" disabled={!query.trim()} className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-brand-orange text-white disabled:opacity-35">
            <Send className="h-4 w-4" />
          </button>
        </form>
        <button type="button" onClick={drawDestination} disabled={!recommendations.length} className="flex flex-col items-center justify-center rounded-[20px] bg-[#fff0dc] text-[10px] font-black text-brand-orange disabled:opacity-40">
          <Gift className="mb-1 h-4 w-4" />
          盲盒抽
        </button>
      </div>

      {blindPick ? (
        <section aria-label="盲盒结果" className="mt-3 flex items-center gap-3 rounded-[20px] border border-dashed border-brand-orange/35 bg-white px-3 py-2.5">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-brand-orange-light text-brand-orange"><Sparkles className="h-4 w-4" /></div>
          <div className="min-w-0 flex-1">
            <div className="text-[9px] font-black text-brand-orange">今天的盲盒目的地</div>
            <div className="truncate text-xs font-black text-brand-text">{recommendationTitle(blindPick)}</div>
          </div>
          <button type="button" onClick={() => onSearch(blindPick.query_hint || `查询${recommendationTitle(blindPick)}的机票`)} className="rounded-xl bg-brand-text px-3 py-2 text-[10px] font-black text-white">去查票</button>
        </section>
      ) : null}

      <section className="mt-5">
        <div className="flex items-end justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold text-brand-orange"><Compass className="h-4 w-4" />真实推荐</div>
            <h2 className="mt-1 text-xl font-black text-brand-text">为你发现</h2>
          </div>
          <span className="text-[10px] font-semibold text-brand-muted">向下继续发现</span>
        </div>

        <div className="mt-3 columns-2 gap-3">
          {loading ? (
            [0, 1, 2, 3].map((item) => <div key={item} className={`mb-3 break-inside-avoid animate-pulse rounded-[22px] bg-white/70 ${item % 2 ? 'h-52' : 'h-44'}`} />)
          ) : recommendations.length ? (
            recommendations.map((card, index) => (
              <button
                key={card.id ?? `${recommendationTitle(card)}-${index}`}
                type="button"
                aria-label={`查看推荐 ${recommendationTitle(card)}`}
                onClick={() => onSearch(card.query_hint || `查询${recommendationTitle(card)}的机票`)}
                className="mb-3 w-full break-inside-avoid overflow-hidden rounded-[22px] border border-brand-text/7 bg-white text-left shadow-sm transition active:scale-[0.98]"
              >
                <div
                  className={`relative bg-cover bg-center ${index % 3 === 1 ? 'h-36' : index % 3 === 2 ? 'h-24' : 'h-28'}`}
                  style={{ backgroundImage: `linear-gradient(to top, rgba(35,22,14,.64), transparent 58%), url("${recommendationImage(card)}")` }}
                >
                  <div className="absolute inset-x-0 bottom-0 p-3 text-xs font-black text-white">{recommendationTitle(card)}</div>
                </div>
                <div className="p-3">
                  <div className="text-sm font-black text-brand-orange">{recommendationPrice(card)}</div>
                  <p className="mt-1 line-clamp-2 text-[10px] leading-4 text-brand-muted">{card.reason || '进入对话获取最新可售结果'}</p>
                  <div className="mt-2 flex items-center justify-between text-[9px] font-bold text-brand-text">
                    <span>查看实时航班</span><ChevronRight className="h-3.5 w-3.5" />
                  </div>
                </div>
              </button>
            ))
          ) : (
            <button type="button" onClick={() => onSearch('帮我看看最近有什么值得关注的特价机票')} className="flex w-full items-center gap-3 rounded-[24px] border border-dashed border-brand-text/12 bg-white/60 p-5 text-left">
              <MapPin className="h-5 w-5 text-brand-orange" />
              <span className="text-sm font-semibold leading-6 text-brand-muted">还没有可展示的真实推荐，发起一次查询看看。</span>
              <ChevronRight className="ml-auto h-4 w-4 text-brand-muted" />
            </button>
          )}
        </div>
      </section>

      <button type="button" onClick={onOpenMemory} className="mt-3 flex w-full items-center gap-3 rounded-[22px] bg-[#fff0dc] p-4 text-left">
        <div className="grid h-10 w-10 place-items-center rounded-2xl bg-white text-brand-orange"><BookHeart className="h-4 w-4" /></div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-black text-brand-text">看看它记住了什么</div>
          <div className="mt-1 text-[10px] leading-4 text-brand-muted">偏好、关注、查询和手帐彼此分开。</div>
        </div>
        <ChevronRight className="h-4 w-4 text-brand-muted" />
      </button>
    </div>
  )
}

function MobileMemoryPage({
  memory,
  loading,
  onRefresh,
}: {
  memory: MobileMemory
  loading: boolean
  onRefresh: () => void
}) {
  const [section, setSection] = React.useState<MobileMemorySection>('preferences')
  const [editingField, setEditingField] = React.useState<string | null>(null)
  const [confirmingField, setConfirmingField] = React.useState<string | null>(null)
  const [draft, setDraft] = React.useState('')
  const [savingField, setSavingField] = React.useState<string | null>(null)
  const [addingPreference, setAddingPreference] = React.useState(false)
  const [newField, setNewField] = React.useState('budget')
  const [newValue, setNewValue] = React.useState('')
  const [ideaText, setIdeaText] = React.useState('')
  const [error, setError] = React.useState('')
  const companion = companionFromMemory(memory.memories)
  const preferences = memory.memories.filter((item) => !INTERNAL_MEMORY_FIELDS.has(item.field))
  const ideas = travelIdeas(memory.memories)

  const beginEdit = (item: MemoryItemDto) => {
    setError('')
    setConfirmingField(null)
    setEditingField(item.field)
    setDraft(preferenceDraft(item))
  }

  const savePreference = async (field: string, valueDraft: string) => {
    setError('')
    let value: number | string[] | string
    try {
      value = parsePreferenceDraft(field, valueDraft)
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '偏好格式不正确')
      return
    }
    setSavingField(field)
    try {
      await memoryApi.patch({ field, value })
      setEditingField(null)
      setAddingPreference(false)
      setNewValue('')
      onRefresh()
    } catch {
      setError('暂时没有保存成功，请稍后再试。')
    } finally {
      setSavingField(null)
    }
  }

  const forgetPreference = async (field: string) => {
    setSavingField(field)
    setError('')
    try {
      await memoryApi.del(field)
      setConfirmingField(null)
      onRefresh()
    } catch {
      setError('暂时无法忘记这项偏好。')
    } finally {
      setSavingField(null)
    }
  }

  const saveIdeas = async (nextIdeas: TravelIdea[]) => {
    setSavingField('travel_ideas')
    setError('')
    try {
      await memoryApi.patch({ field: 'travel_ideas', value: nextIdeas })
      setIdeaText('')
      onRefresh()
    } catch {
      setError('这个关注暂时没有保存成功。')
    } finally {
      setSavingField(null)
    }
  }

  const memorySections: Array<{ id: MobileMemorySection; label: string; count: number }> = [
    { id: 'preferences', label: '偏好', count: preferences.length },
    { id: 'ideas', label: '关注', count: ideas.length },
    { id: 'queries', label: '查询', count: memory.query_history.length },
    { id: 'journal', label: '手帐', count: 0 },
  ]

  return (
    <div className="thin-scrollbar h-full overflow-y-auto px-4 pb-8 pt-[max(1.1rem,env(safe-area-inset-top))]">
      <header className="flex items-start justify-between px-1">
        <div>
          <div className="text-[10px] font-black tracking-[0.2em] text-brand-orange">只记真实发生的事</div>
          <h1 className="mt-1 font-serif text-[2rem] font-black leading-tight text-brand-text">我的记忆</h1>
        </div>
        <button type="button" aria-label="刷新手机端记忆" onClick={onRefresh} className="grid h-10 w-10 place-items-center rounded-2xl border border-brand-text/8 bg-white text-brand-text shadow-sm">
          <Clock3 className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </header>

      <section className="mt-4 grid grid-cols-[4.4rem_minmax(0,1fr)] items-center gap-4 rounded-[25px] bg-brand-text p-4 text-white">
        <MobileCompanion kind={companion.kind} />
        <div className="min-w-0">
          <div className="text-[11px] font-bold text-white/60">{companion.name} 的记忆盒</div>
          <div className="mt-1 text-lg font-black">你说过的，可以修改</div>
          <p className="mt-1 text-[11px] leading-5 text-white/65">搜索记录和明确关注分开放，手帐只写真正成行。</p>
        </div>
      </section>

      <nav aria-label="手机端记忆分类" className="mt-4 grid grid-cols-4 gap-1 rounded-[20px] bg-white p-1.5 shadow-sm">
        {memorySections.map((item) => (
          <button key={item.id} type="button" aria-pressed={section === item.id} onClick={() => setSection(item.id)} className={`rounded-[15px] px-1 py-2.5 text-xs font-black transition ${section === item.id ? 'bg-brand-text text-white' : 'text-brand-muted'}`}>
            <span className="block">{item.label}</span>
            <span className={`mt-0.5 block text-[10px] ${section === item.id ? 'text-white/55' : 'text-brand-orange'}`}>{item.count}</span>
          </button>
        ))}
      </nav>

      {error ? <div className="mt-3 rounded-2xl bg-[#fff0dc] px-4 py-3 text-xs font-bold text-brand-text">{error}</div> : null}

      <div className="mt-5">
        {section === 'preferences' ? (
          <section>
            <div className="flex items-center justify-between px-1">
              <div>
                <h2 className="text-lg font-black text-brand-text">机票偏好</h2>
                <p className="mt-1 text-[11px] text-brand-muted">下次查价和排序会使用这些内容</p>
              </div>
              <button type="button" onClick={() => setAddingPreference((current) => !current)} className="inline-flex items-center gap-1 rounded-xl bg-brand-orange-light px-3 py-2 text-xs font-black text-brand-orange">
                {addingPreference ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
                {addingPreference ? '收起' : '添加'}
              </button>
            </div>

            {addingPreference ? (
              <div className="mt-3 space-y-3 rounded-[22px] border border-brand-orange/15 bg-white p-4">
                <select value={newField} onChange={(event) => { setNewField(event.target.value); setNewValue('') }} aria-label="手机端偏好类型" className="h-11 w-full rounded-xl border border-brand-text/10 bg-brand-bg px-3 text-sm font-bold text-brand-text">
                  {PREFERENCE_OPTIONS.map((option) => <option key={option.field} value={option.field}>{option.label}</option>)}
                </select>
                <input value={newValue} onChange={(event) => setNewValue(event.target.value)} aria-label="手机端偏好内容" type={newField === 'budget' ? 'number' : 'text'} placeholder={newField === 'budget' ? '例如：800' : '多项内容用顿号分开'} className="h-11 w-full rounded-xl border border-brand-text/10 bg-brand-bg px-3 text-sm font-semibold" />
                <button type="button" disabled={!newValue.trim() || savingField === newField} onClick={() => void savePreference(newField, newValue)} className="h-11 w-full rounded-xl bg-brand-text text-sm font-black text-white disabled:opacity-40">保存偏好</button>
              </div>
            ) : null}

            <div className="mt-3 space-y-3">
              {preferences.length ? preferences.map((item) => (
                <article key={item.field} className="rounded-[22px] border border-brand-text/7 bg-white p-4 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-[10px] font-bold text-brand-orange">{item.source === 'manual' ? '你亲自确认' : '根据真实行为学习'}</div>
                      <h3 className="mt-1 text-base font-black text-brand-text">{item.label}</h3>
                    </div>
                    {editingField !== item.field && confirmingField !== item.field ? (
                      <div className="flex gap-2">
                        <button type="button" aria-label={`手机端编辑${item.label}`} onClick={() => beginEdit(item)} className="grid h-8 w-8 place-items-center rounded-xl bg-brand-bg text-brand-muted"><PencilLine className="h-3.5 w-3.5" /></button>
                        <button type="button" aria-label={`手机端忘记${item.label}`} onClick={() => { setEditingField(null); setConfirmingField(item.field) }} className="grid h-8 w-8 place-items-center rounded-xl bg-brand-bg text-brand-muted"><Trash2 className="h-3.5 w-3.5" /></button>
                      </div>
                    ) : null}
                  </div>

                  {editingField === item.field ? (
                    <div className="mt-3">
                      <input aria-label={`手机端修改${item.label}`} value={draft} onChange={(event) => setDraft(event.target.value)} type={item.field === 'budget' ? 'number' : 'text'} className="h-11 w-full rounded-xl border border-brand-orange/30 bg-brand-bg px-3 text-sm font-semibold" />
                      <div className="mt-2 flex gap-2">
                        <button type="button" onClick={() => void savePreference(item.field, draft)} disabled={savingField === item.field} className="inline-flex h-9 flex-1 items-center justify-center gap-1 rounded-xl bg-brand-text text-xs font-black text-white"><Check className="h-3.5 w-3.5" />保存</button>
                        <button type="button" onClick={() => setEditingField(null)} className="h-9 flex-1 rounded-xl border border-brand-text/10 text-xs font-black text-brand-muted">取消</button>
                      </div>
                    </div>
                  ) : confirmingField === item.field ? (
                    <div className="mt-3 rounded-xl bg-red-50 p-3">
                      <p className="text-xs leading-5 text-red-700">忘记后，这项内容不再参与推荐。</p>
                      <div className="mt-2 flex gap-2">
                        <button type="button" onClick={() => void forgetPreference(item.field)} className="h-9 flex-1 rounded-xl bg-red-600 text-xs font-black text-white">确认忘记</button>
                        <button type="button" onClick={() => setConfirmingField(null)} className="h-9 flex-1 rounded-xl bg-white text-xs font-black text-red-700">取消</button>
                      </div>
                    </div>
                  ) : (
                    <p className="mt-3 text-sm font-semibold leading-6 text-brand-muted">{item.value_display || '已记录'}</p>
                  )}
                </article>
              )) : (
                <MobileEmpty title="还没有机票偏好" detail="完成一次查询，或者亲自添加预算和出行习惯。" />
              )}
            </div>
          </section>
        ) : section === 'ideas' ? (
          <section>
            <h2 className="px-1 text-lg font-black text-brand-text">你明确说过的关注</h2>
            <p className="mt-1 px-1 text-[11px] leading-5 text-brand-muted">只有你亲自保存的想法才会在这里，系统不会从查询里猜。</p>
            <div className="mt-3 flex gap-2 rounded-[20px] bg-white p-3">
              <input aria-label="手机端新增明确关注" value={ideaText} onChange={(event) => setIdeaText(event.target.value)} placeholder="例如：秋天想去青岛吹海风" className="min-w-0 flex-1 bg-transparent px-1 text-sm font-semibold" />
              <button type="button" aria-label="保存明确关注" disabled={!ideaText.trim() || savingField === 'travel_ideas'} onClick={() => void saveIdeas([{ id: `${Date.now()}`, text: ideaText.trim(), created_at: new Date().toISOString() }, ...ideas])} className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-orange text-white disabled:opacity-35"><Plus className="h-4 w-4" /></button>
            </div>
            <div className="mt-3 space-y-3">
              {ideas.length ? ideas.map((idea) => (
                <article key={idea.id} className="rounded-[22px] bg-white p-4 shadow-sm">
                  <div className="flex items-center justify-between text-[10px] font-bold text-brand-orange"><span>你亲自记录</span><span>{shortDate(idea.created_at)}</span></div>
                  <p className="mt-3 text-sm font-black leading-6 text-brand-text">{idea.text}</p>
                  <button type="button" onClick={() => void saveIdeas(ideas.filter((item) => item.id !== idea.id))} className="mt-3 inline-flex items-center gap-1 text-[11px] font-bold text-brand-muted"><Trash2 className="h-3.5 w-3.5" />忘掉这个关注</button>
                </article>
              )) : <MobileEmpty title="还没有明确关注" detail="在上面亲自记下一个想去的地方或出发理由。" />}
            </div>
          </section>
        ) : section === 'queries' ? (
          <section>
            <h2 className="px-1 text-lg font-black text-brand-text">最近查询</h2>
            <p className="mt-1 px-1 text-[11px] leading-5 text-brand-muted">这里只说明查过，不代表你明确想去。</p>
            <div className="mt-3 space-y-3">
              {memory.query_history.length ? memory.query_history.map((item) => (
                <article key={item.id} className="flex gap-3 rounded-[22px] bg-white p-4 shadow-sm">
                  <div className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-brand-orange-light text-brand-orange"><Search className="h-4 w-4" /></div>
                  <div className="min-w-0">
                    <div className="text-[10px] font-bold text-brand-orange">真实查询 · {shortDate(item.created_at)}</div>
                    <p className="mt-1 text-sm font-black leading-6 text-brand-text">{queryText(item)}</p>
                  </div>
                </article>
              )) : <MobileEmpty title="还没有查询记录" detail="从对话页发起真实机票查询后会出现在这里。" />}
            </div>
          </section>
        ) : (
          <section aria-label="旅行手帐留白页" className="relative overflow-hidden rounded-[18px_26px_20px_28px] border-2 border-[#725b49]/20 bg-[#fffaf0] px-5 py-5 shadow-[5px_7px_0_rgba(92,68,46,0.08)]" style={{ backgroundImage: 'linear-gradient(rgba(121,174,191,0.12) 1px, transparent 1px)', backgroundSize: '100% 25px' }}>
            <div className="absolute left-3.5 top-0 h-full border-l-2 border-dashed border-[#dc7d61]/25" />
            <div className="absolute left-1/2 top-0 h-5 w-20 -translate-x-1/2 -translate-y-1.5 -rotate-2 bg-[#f4cf86]/75" />
            <div className="absolute right-4 top-4 rotate-6 rounded-full border-2 border-[#d47752]/30 px-2 py-1 text-[8px] font-black text-[#b7674c]">尚未成行</div>
            <div className="relative pl-3">
              <div className="text-[9px] font-black tracking-[0.15em] text-[#9a674b]">TRAVEL NOTE · 第一页</div>
              <h2 className="mt-3 max-w-[13rem] rotate-[-1deg] font-serif text-[1.65rem] font-black leading-tight text-[#493526]">把真正出发的那天，留给手帐</h2>
              <div className="mt-4 grid grid-cols-[minmax(0,1fr)_5.8rem] items-center gap-3">
                <div>
                  <div className="inline-block -rotate-1 bg-[#f9dda3]/65 px-2 py-1 text-[10px] font-black text-[#725b49]">等待第一段旅程</div>
                  <p className="mt-2 text-[11px] font-semibold leading-5 text-[#725b49]">确认买票或录入真实行程后，{companion.name} 才会写下日期、目的地和当时的想法。</p>
                </div>
                <div className="rotate-2"><MobileCompanion kind={companion.kind} pose="journal" /></div>
              </div>
              <div className="mt-4 rotate-[0.4deg] rounded-[14px_18px_13px_16px] border border-dashed border-[#c97858]/40 bg-white/45 px-3 py-3">
                <div className="flex items-center gap-2 text-[10px] font-black text-[#725b49]"><Plane className="h-3.5 w-3.5 text-[#d47752]" />未来的一页会记录</div>
                <div className="mt-2 flex flex-wrap gap-1.5 text-[9px] font-bold text-[#876d58]">
                  <span className="rounded-full bg-[#f7e8d1] px-2 py-1">出发日期</span>
                  <span className="rounded-full bg-[#f7e8d1] px-2 py-1">真实行程</span>
                  <span className="rounded-full bg-[#f7e8d1] px-2 py-1">你的想法</span>
                  <span className="rounded-full bg-[#f7e8d1] px-2 py-1">旅伴小记</span>
                </div>
              </div>
              <p className="mt-4 border-t border-dashed border-[#d47752]/35 pt-3 text-[10px] font-semibold leading-5 text-[#876d58]">查询、关注和点击预订仍只保留原本含义，不会被写成已经去过。</p>
            </div>
          </section>
        )}
      </div>
    </div>
  )
}

function MobileEmpty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="rounded-[22px] border border-dashed border-brand-text/12 bg-white/55 px-5 py-8 text-center">
      <div className="text-sm font-black text-brand-text">{title}</div>
      <p className="mt-2 text-xs leading-5 text-brand-muted">{detail}</p>
    </div>
  )
}

function MobileProfile({
  memory,
  alerts,
  account,
  phoneLoginAvailable,
  onAccountChanged,
  onChooseCompanion,
  onOpenMemory,
  onOpenChat,
}: {
  memory: MobileMemory
  alerts: AlertItemDto[]
  account: MobileAccount
  phoneLoginAvailable: boolean
  onAccountChanged: () => void
  onChooseCompanion: () => void
  onOpenMemory: () => void
  onOpenChat: () => void
}) {
  const companion = companionFromMemory(memory.memories)
  const [showLogin, setShowLogin] = React.useState(false)
  const [showAlerts, setShowAlerts] = React.useState(false)
  return (
    <div className="thin-scrollbar h-full overflow-y-auto px-4 pb-8 pt-[max(1.1rem,env(safe-area-inset-top))]">
      <div className="text-[10px] font-black tracking-[0.2em] text-brand-orange">我的空间</div>
      <h1 className="mt-1 font-serif text-[2rem] font-black leading-tight text-brand-text">账号与旅伴</h1>

      <section className="mt-4 rounded-[24px] border border-brand-text/7 bg-white p-4 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-brand-text text-white"><UserCheck className="h-4 w-4" /></div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-[10px] font-bold text-brand-muted">
              <span className={`h-2 w-2 rounded-full ${account.loggedIn ? 'bg-emerald-500' : 'bg-amber-400'}`} />
              {account.loggedIn ? '已登录并同步' : '游客模式'}
            </div>
            <div className="mt-1 text-base font-black text-brand-text">{account.loggedIn ? maskPhone(account.phone) : '先在这台设备继续使用'}</div>
            <p className="mt-1 text-[10px] leading-5 text-brand-muted">{account.loggedIn ? '偏好、旅伴和提醒会跟随账号。' : '这台设备会继续使用当前记忆；绑定手机号后才能跨设备接回。'}</p>
          </div>
        </div>
        <div className="mt-3 flex items-center justify-between rounded-xl bg-brand-bg px-3 py-2 text-[9px] font-semibold text-brand-muted">
          <span>{account.loggedIn ? '跨设备同步已开启' : '仅当前设备可直接使用'}</span>
          {account.userId ? <span>编号 {shortAccountId(account.userId)}</span> : null}
        </div>
        {!account.loggedIn ? (
          phoneLoginAvailable ? (
            <button type="button" onClick={() => setShowLogin((value) => !value)} className="mt-3 h-10 w-full rounded-xl bg-brand-text text-xs font-black text-white">{showLogin ? '收起登录' : '绑定手机号，开启跨设备同步'}</button>
          ) : (
            <div className="mt-3 flex items-center gap-2 rounded-xl bg-[#fff0dc] px-3 py-2.5 text-[10px] font-semibold text-brand-text"><ShieldCheck className="h-4 w-4 text-brand-orange" />跨设备同步暂未开放，不影响当前设备使用</div>
          )
        ) : null}
      </section>

      {showLogin && phoneLoginAvailable ? <MobileOtpForm onSuccess={() => { setShowLogin(false); onAccountChanged() }} /> : null}

      <section className="mt-3 flex items-center gap-3 rounded-[24px] bg-brand-text p-4 text-white shadow-sm">
        <div className="w-16 shrink-0"><MobileCompanion kind={companion.kind} /></div>
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-bold text-white/55">当前旅伴</div>
          <div className="mt-0.5 text-lg font-black">{companion.name}</div>
          <div className="mt-1 text-[10px] leading-4 text-white/60">陪你记忆和提醒，不替你做购买决定。</div>
        </div>
        <button type="button" onClick={onChooseCompanion} className="shrink-0 rounded-xl bg-white/10 px-3 py-2 text-[10px] font-black text-white">更换</button>
      </section>

      <section className="mt-3 grid grid-cols-3 gap-2" aria-label="账号数据概览">
        <ProfileStat label="偏好" value={memory.memories.filter((item) => !INTERNAL_MEMORY_FIELDS.has(item.field)).length} />
        <ProfileStat label="查询" value={memory.query_history.length} />
        <ProfileStat label="提醒" value={alerts.length} />
      </section>

      <div className="mt-4 space-y-2.5">
        <ProfileRow icon={<Heart />} title="管理机票偏好" detail="添加、修改或忘记预算和出行习惯" onClick={onOpenMemory} />
        <ProfileRow icon={<BookHeart />} title="查看旅行手帐" detail="确认成行后才会写入真实旅行" onClick={onOpenMemory} />
        <ProfileRow icon={<MessageCircle />} title="继续查票对话" detail="接着当前上下文补充时间和条件" onClick={onOpenChat} />
        <ProfileRow icon={<Bell />} title="价格提醒" detail={alerts.length ? `${alerts.length} 条提醒已保存到后端` : '还没有创建价格提醒'} onClick={() => setShowAlerts((value) => !value)} />
      </div>

      {showAlerts ? (
        <section className="mt-4 space-y-2 rounded-[24px] bg-white p-4 shadow-sm" aria-label="手机端价格提醒列表">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-black text-brand-text">后端价格提醒</h2>
            <span className="text-[10px] font-bold text-brand-orange">与网页端同步</span>
          </div>
          {alerts.length ? alerts.map((alert) => (
            <div key={alert.id} className="flex items-center justify-between gap-3 rounded-2xl bg-brand-bg px-3 py-3">
              <div className="min-w-0">
                <div className="text-xs font-black text-brand-text">{alert.origin} → {alert.destination}</div>
                <div className="mt-1 text-[10px] text-brand-muted">{alert.depart_date} · {alert.status === 'triggered' ? '已触发' : '监控中'}</div>
              </div>
              <div className="shrink-0 text-sm font-black text-brand-orange">≤ ¥{alert.target_price}</div>
            </div>
          )) : <p className="rounded-2xl bg-brand-bg px-4 py-5 text-center text-xs leading-5 text-brand-muted">从航班卡点击“监控价格”后，提醒会出现在这里。</p>}
        </section>
      ) : null}
    </div>
  )
}

function ProfileRow({ icon, title, detail, onClick }: { icon: React.ReactElement; title: string; detail: string; onClick?: () => void }) {
  return (
    <button type="button" onClick={onClick} className="flex w-full items-center gap-3 rounded-[20px] border border-brand-text/7 bg-white p-3.5 text-left">
      <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-brand-orange-light text-brand-orange [&>svg]:h-4 [&>svg]:w-4">{icon}</div>
      <div className="min-w-0 flex-1">
        <div className="text-xs font-black text-brand-text">{title}</div>
        <div className="mt-0.5 text-[10px] leading-4 text-brand-muted">{detail}</div>
      </div>
      <ChevronRight className="h-4 w-4 text-brand-muted" />
    </button>
  )
}

function ProfileStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-[18px] bg-white px-2 py-3 text-center shadow-sm">
      <div className="text-base font-black text-brand-text">{value}</div>
      <div className="mt-0.5 text-[9px] font-bold text-brand-muted">{label}</div>
    </div>
  )
}

function MobileBottomNav({ activeTab, onChange }: { activeTab: MobileTab; onChange: (tab: MobileTab) => void }) {
  const items: Array<{ id: MobileTab; label: string; icon: React.ReactElement }> = [
    { id: 'chat', label: '对话', icon: <MessageCircle /> },
    { id: 'explore', label: '探索', icon: <Compass /> },
    { id: 'memory', label: '记忆', icon: <BookHeart /> },
    { id: 'profile', label: '我的', icon: <UserRound /> },
  ]
  return (
    <nav aria-label="手机端主导航" className="relative z-30 grid shrink-0 grid-cols-4 border-t border-brand-text/8 bg-white/95 px-3 pb-[max(0.65rem,env(safe-area-inset-bottom))] pt-2 backdrop-blur-xl sm:pb-5">
      {items.map((item) => {
        const active = item.id === activeTab
        return (
          <button key={item.id} type="button" aria-label={item.label} aria-pressed={active} onClick={() => onChange(item.id)} className={`flex min-h-12 flex-col items-center justify-center gap-1 rounded-2xl text-[11px] font-bold transition [&>svg]:h-5 [&>svg]:w-5 ${active ? 'bg-brand-orange-light text-brand-orange' : 'text-brand-muted'}`}>
            {item.icon}
            {item.label}
          </button>
        )
      })}
      <span className="pointer-events-none absolute bottom-1 left-1/2 hidden h-1 w-28 -translate-x-1/2 rounded-full bg-black sm:block" aria-hidden="true" />
    </nav>
  )
}
