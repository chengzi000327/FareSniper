'use client'

import React from 'react'
import Image from 'next/image'
import { AnimatePresence, motion } from 'motion/react'
import { DiscoveryCardContent } from '@/components/discovery-card-content'
import {
  ArrowLeft,
  ArrowRight,
  BellRing,
  BrainCircuit,
  Check,
  Clock3,
  Coins,
  Database,
  ExternalLink,
  Gauge,
  GraduationCap,
  Luggage,
  Maximize2,
  Minimize2,
  Network,
  NotebookText,
  Plane,
  Radar,
  Radio,
  RefreshCw,
  Route,
  SearchCheck,
  ServerCog,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react'

const PRODUCT_URL = 'https://frontend-production-9c2c.up.railway.app/'

type SlideDefinition = {
  id: string
  label: string
  duration: string
  notes: string[]
}

const SLIDES: SlideDefinition[] = [
  {
    id: 'opening',
    label: '开场',
    duration: '00:30',
    notes: [
      '搜索机票并不难，真正困难的是：搜到之后，我们仍然不知道该不该买。',
      'FareSniper 不替所有人定义特价，而是记住每个人自己的特价标准。',
    ],
  },
  {
    id: 'profile',
    label: '关于我',
    duration: '02:30',
    notes: [
      '我目前在中国科学院大学攻读信息系统工程管理硕士，关注 AI Agent 和复杂 AI 平台的产品落地。',
      'Keep 让我开始思考 Agent 如何通过状态、工具与校验真正完成任务；智谱让我建立评测和 Bad Case 闭环；百度 AIHC 让我理解复杂平台中的资源、权限和调度。',
      'FareSniper 是这些经历的交汇点：既要自然交互，也要可验证、可观测、可持续学习。',
    ],
  },
  {
    id: 'deal-definition',
    label: '用户洞察',
    duration: '01:10',
    notes: [
      '用户焦虑的不是找不到价格，而是价格一直在变：早上看、晚上看、第二天看，可能是三个数字。一次搜索只能截到一个点。',
      '刚需用户等的是心理价进入固定时段，弹性用户等的是某一天出现低点，带行李用户等的是完整成本真正划算。FareSniper 监控的是每个人自己的购买窗口。',
    ],
  },
  {
    id: 'trust',
    label: '竞品与缺口',
    duration: '01:00',
    notes: [
      '市场并不缺单点能力：OTA 和比价回答现在谁便宜，价格工具回答买还是等，通用 AI 负责自然语言。',
      '真正缺口是三件事没有进入同一闭环：持续变化的多平台价格、含税费行李的完整成本，以及用户自己的时间和偏好。',
    ],
  },
  {
    id: 'product',
    label: '产品方案',
    duration: '01:20',
    notes: [
      'FareSniper 把 Search 和 Monitor 分开：搜索时实时拉取当前事实，关注后持续刷新价格。',
      '当价格进入个人阈值，再结合完整成本与记忆给出提醒。创新点不是多一个聊天框，而是把一次搜索变成持续决策关系。',
    ],
  },
  {
    id: 'demo',
    label: '现场演示',
    duration: '02:30',
    notes: [
      '现场输入：下周五从北京到长治。',
      '依次说明日期归一化、机场范围、多来源查询、完整成本拆分、平台跳转与记忆写回。',
      '若网络不稳定，就使用本页结果卡继续讲，不在台上重复刷新。',
    ],
  },
  {
    id: 'architecture',
    label: '技术架构',
    duration: '02:10',
    notes: [
      '这五层不是为了堆技术名词，而是把一次请求里不同职责讲清楚。请求从左到右依次经过，每层只解决一个具体问题。',
      '第一层先确认用户身份，取回当前会话和长期偏好，例如常用机场、时间、行李和预算。',
      '第二层把用户的一句话整理成可查询条件。缺少真正无法查询的信息才追问，表达有歧义时才让模型判断。',
      '第三层分别查询飞猪、携程缓存和 Google 航班。每个来源有自己的查询模块和超时控制，单个来源失败不影响其他来源。',
      '第四层等可用结果收齐后，统一税费、行李、平台和更新时间，遍历全部候选，再按完整成本与用户偏好筛选排序。',
      '第五层让回答和价格卡读取同一份结果；用户关注后，后台继续检查价格并发送提醒。模型只解释推荐，不能自己改价格和排序。',
    ],
  },
  {
    id: 'decisions',
    label: '评测闭环',
    duration: '01:40',
    notes: [
      '离线有 50 条种子样本，覆盖正常、相对日期、多轮追问、边界异常与对抗；评测意图、追问、信号、建议和格式。',
      '线上 LangSmith Trace 发现问题后，按 P0–P3 定级，再固化为最小复现样本和单元、契约或 E2E 回归测试。',
      '典型 Bad Case 包括旧日期串线、慢 Provider 拖垮请求、不合资格或异币种报价误胜，以及 AI 文案与卡片价格不一致。',
    ],
  },
  {
    id: 'monitoring',
    label: '演进路线',
    duration: '01:20',
    notes: [
      '有了评测护栏，再看当前实现与下一步演进。当前闭环已经能完成三件事：用户创建价格提醒，后台每 15 分钟检查缓存报价，达到目标价后通过 Web Push 通知。携程快照每小时刷新。',
      '下一步不是增加更多定时任务，而是回答四个问题：什么时候提高检查频率，什么时候真的值得提醒，如何保证通知不丢不重，以及如何安全发布规则变化。',
      '购买窗口由时间、行李、完整成本、目标价和历史低位共同决定；规则负责触发，模型只把原因解释给用户。这也是 FareSniper 从盯价工具走向出行决策 Agent 的路径。',
    ],
  },
  {
    id: 'closing',
    label: '结尾',
    duration: '00:50',
    notes: [
      '当前边界是部分平台不会返回完整税费和行李字段，因此产品必须诚实展示数据状态。',
      '长期目标不是成为另一个卖票平台，而是成为代表用户做出行决策的 Agent。',
    ],
  },
]

export function OpenMicDeck() {
  const [index, setIndex] = React.useState(0)
  const [direction, setDirection] = React.useState(1)
  const [notesOpen, setNotesOpen] = React.useState(false)
  const [isFullscreen, setIsFullscreen] = React.useState(false)

  const goTo = React.useCallback((next: number) => {
    const bounded = Math.max(0, Math.min(SLIDES.length - 1, next))
    setIndex((current) => {
      setDirection(bounded >= current ? 1 : -1)
      return bounded
    })
  }, [])

  React.useEffect(() => {
    const fromHash = Number(window.location.hash.replace('#slide-', '')) - 1
    if (Number.isInteger(fromHash) && fromHash >= 0 && fromHash < SLIDES.length) {
      setIndex(fromHash)
    }
  }, [])

  React.useEffect(() => {
    window.history.replaceState(null, '', `#slide-${index + 1}`)
  }, [index])

  React.useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'ArrowRight' || event.key === 'PageDown' || event.key === ' ') {
        event.preventDefault()
        goTo(index + 1)
      } else if (event.key === 'ArrowLeft' || event.key === 'PageUp') {
        event.preventDefault()
        goTo(index - 1)
      } else if (event.key === 'Home') {
        goTo(0)
      } else if (event.key === 'End') {
        goTo(SLIDES.length - 1)
      } else if (event.key.toLowerCase() === 'n') {
        setNotesOpen((open) => !open)
      } else if (event.key === 'Escape' && notesOpen) {
        setNotesOpen(false)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [goTo, index, notesOpen])

  React.useEffect(() => {
    const onFullscreen = () => setIsFullscreen(Boolean(document.fullscreenElement))
    document.addEventListener('fullscreenchange', onFullscreen)
    return () => document.removeEventListener('fullscreenchange', onFullscreen)
  }, [])

  const toggleFullscreen = async () => {
    if (document.fullscreenElement) {
      await document.exitFullscreen()
    } else {
      await document.documentElement.requestFullscreen()
    }
  }

  const slide = SLIDES[index]

  return (
    <div className="fixed inset-0 z-50 flex min-h-[100dvh] flex-col overflow-hidden bg-brand-bg text-brand-text selection:bg-brand-orange selection:text-white">
      <header className="relative z-30 flex h-16 shrink-0 items-center gap-4 border-b border-brand-text/10 bg-brand-bg/95 px-4 backdrop-blur sm:px-7">
        <button
          type="button"
          aria-label="返回 FareSniper"
          title="返回 FareSniper"
          onClick={() => window.open(PRODUCT_URL, '_blank', 'noopener,noreferrer')}
          className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brand-orange text-white shadow-sm"
        >
          <Plane className="h-5 w-5" />
        </button>
        <div className="min-w-0">
          <div className="truncate text-sm font-black">FareSniper</div>
          <div className="truncate text-[11px] text-brand-muted">产品开放麦 · 陈永琪</div>
        </div>
        <div className="ml-auto hidden min-w-32 items-center gap-3 sm:flex">
          <span className="text-xs font-semibold text-brand-muted">{slide.duration}</span>
          <div className="h-1.5 w-28 overflow-hidden rounded-full bg-brand-orange-light">
            <motion.div
              className="h-full rounded-full bg-brand-orange"
              animate={{ width: `${((index + 1) / SLIDES.length) * 100}%` }}
            />
          </div>
        </div>
        <IconButton
          label={notesOpen ? '关闭讲稿' : '打开讲稿'}
          onClick={() => setNotesOpen((open) => !open)}
          active={notesOpen}
        >
          <NotebookText className="h-4 w-4" />
        </IconButton>
        <IconButton
          label={isFullscreen ? '退出全屏' : '进入全屏'}
          onClick={() => void toggleFullscreen()}
        >
          {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
        </IconButton>
      </header>

      <main className="relative min-h-0 flex-1 overflow-hidden">
        <AnimatePresence mode="wait" initial={false} custom={direction}>
          <motion.section
            key={slide.id}
            custom={direction}
            initial={{ opacity: 0, x: direction > 0 ? 36 : -36 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: direction > 0 ? -24 : 24 }}
            transition={{ duration: 0.28, ease: 'easeOut' }}
            className="absolute inset-0 overflow-y-auto px-5 py-7 sm:px-9 sm:py-9 lg:px-14 lg:py-10"
          >
            <SlideContent id={slide.id} />
          </motion.section>
        </AnimatePresence>
      </main>

      <footer className="relative z-30 flex h-16 shrink-0 items-center border-t border-brand-text/10 bg-brand-bg/95 px-4 backdrop-blur sm:px-7">
        <div className="flex items-center gap-2">
          <IconButton label="上一页" onClick={() => goTo(index - 1)} disabled={index === 0}>
            <ArrowLeft className="h-4 w-4" />
          </IconButton>
          <IconButton label="下一页" onClick={() => goTo(index + 1)} disabled={index === SLIDES.length - 1}>
            <ArrowRight className="h-4 w-4" />
          </IconButton>
        </div>
        <nav aria-label="演示章节" className="mx-auto flex items-center gap-1.5">
          {SLIDES.map((item, slideIndex) => (
            <button
              key={item.id}
              type="button"
              aria-label={`第 ${slideIndex + 1} 页：${item.label}`}
              aria-current={slideIndex === index ? 'page' : undefined}
              title={item.label}
              onClick={() => goTo(slideIndex)}
              className={`h-2 rounded-full transition-all ${
                slideIndex === index ? 'w-7 bg-brand-orange' : 'w-2 bg-brand-text/20 hover:bg-brand-muted'
              }`}
            />
          ))}
        </nav>
        <div className="w-[76px] text-right text-xs font-bold tabular-nums text-brand-muted">
          {String(index + 1).padStart(2, '0')} / {String(SLIDES.length).padStart(2, '0')}
        </div>
      </footer>

      <AnimatePresence>
        {notesOpen ? (
          <motion.aside
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ duration: 0.24, ease: 'easeOut' }}
            aria-label="当前页讲稿"
            className="absolute inset-x-0 bottom-16 z-40 max-h-[52dvh] overflow-y-auto border-t border-brand-text/15 bg-brand-text px-5 py-5 text-white shadow-2xl sm:px-10"
          >
            <div className="mx-auto flex max-w-5xl items-start gap-5">
              <div className="min-w-0 flex-1">
                <div className="text-xs font-bold text-brand-orange-light">{slide.label} · {slide.duration}</div>
                <div className="mt-3 space-y-2">
                  {slide.notes.map((note) => (
                    <p key={note} className="text-sm leading-7 text-white/85 sm:text-base">{note}</p>
                  ))}
                </div>
              </div>
              <IconButton label="关闭讲稿" onClick={() => setNotesOpen(false)} inverted>
                <X className="h-4 w-4" />
              </IconButton>
            </div>
          </motion.aside>
        ) : null}
      </AnimatePresence>
    </div>
  )
}

function IconButton({
  label,
  onClick,
  children,
  active = false,
  disabled = false,
  inverted = false,
}: {
  label: string
  onClick: () => void
  children: React.ReactNode
  active?: boolean
  disabled?: boolean
  inverted?: boolean
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className={`flex h-9 w-9 items-center justify-center rounded-2xl border transition disabled:cursor-not-allowed disabled:opacity-30 ${
        inverted
          ? 'border-white/20 text-white hover:bg-white/10'
          : active
            ? 'border-brand-orange bg-brand-orange-light text-brand-orange'
            : 'border-brand-text/10 bg-white text-brand-text hover:border-brand-orange hover:text-brand-orange'
      }`}
    >
      {children}
    </button>
  )
}

function SlideContent({ id }: { id: string }) {
  switch (id) {
    case 'opening':
      return <OpeningSlide />
    case 'profile':
      return <ProfileSlide />
    case 'deal-definition':
      return <DealDefinitionSlide />
    case 'trust':
      return <TrustSlide />
    case 'product':
      return <ProductSlide />
    case 'demo':
      return <DemoSlide />
    case 'architecture':
      return <ArchitectureSlide />
    case 'monitoring':
      return <MonitoringSlide />
    case 'decisions':
      return <DecisionsSlide />
    default:
      return <ClosingSlide />
  }
}

function OpeningSlide() {
  return (
    <div className="relative mx-auto flex min-h-full max-w-7xl items-center overflow-hidden">
      <div className="absolute right-0 top-1/2 hidden w-[52%] -translate-y-1/2 opacity-95 lg:block">
        <FarePreview compact />
      </div>
      <div className="relative z-10 max-w-3xl py-10">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-brand-orange/20 bg-orange-50 px-4 py-2 text-sm font-bold text-brand-orange">
          <Radar className="h-4 w-4" />
          产品开放麦 · 15 MIN
        </div>
        <h1 className="font-serif text-6xl font-black leading-[0.95] text-brand-text sm:text-7xl lg:text-8xl">
          FareSniper
        </h1>
        <p className="mt-7 max-w-2xl text-2xl font-bold leading-tight text-brand-text sm:text-3xl">
          会记住你如何定义“特价”的<br className="hidden sm:block" />机票决策 Agent
        </p>
        <p className="mt-7 max-w-lg text-base leading-8 text-brand-muted sm:text-lg">
          不是替所有人寻找同一个最低数字，而是在用户约束下，用多平台完整成本找到相对最优解。
        </p>
        <div className="mt-10 flex flex-wrap gap-3 text-sm font-semibold">
          <Tag icon={<Network />} label="多平台证据" />
          <Tag icon={<BrainCircuit />} label="个性化判断" />
          <Tag icon={<Database />} label="可解释记忆" />
        </div>
      </div>
    </div>
  )
}

function ProfileSlide() {
  const experiences = [
    {
      company: '百度 · 百舸 AIHC',
      role: 'AI 平台产品实习生',
      detail: '全托管资源池、队列权限与调度策略，推动复杂云产品需求落地。',
      icon: <Gauge className="h-5 w-5" />,
    },
    {
      company: '智谱华章 Z.ai',
      role: 'AI 产品实习生',
      detail: '搭建多模态评测与 Bad Case 闭环，将判题规则一致率提升至 98.5%。',
      icon: <SearchCheck className="h-5 w-5" />,
    },
    {
      company: 'Keep · AI 平台事业部',
      role: 'AI 产品实习生',
      detail: '参与 Workflow 向 Agent 模式升级，设计 State、Tool Use 与多轮校验。',
      icon: <BrainCircuit className="h-5 w-5" />,
    },
  ]

  return (
    <div className="mx-auto grid min-h-full max-w-7xl items-center gap-8 lg:grid-cols-[0.68fr_1.32fr] lg:gap-12">
      <div className="mx-auto w-full max-w-[15rem] sm:max-w-[16rem] lg:max-w-[14rem] 2xl:max-w-[16rem]">
        <div className="relative">
          <div className="absolute -bottom-3 -left-3 h-full w-full rounded-[28px] bg-brand-orange" />
          <Image
            src="/open-mic/chen-yongqi-open-mic.jpg"
            alt="陈永琪"
            width={1366}
            height={2048}
            priority
            className="relative aspect-[3/4] w-full rounded-[28px] border border-brand-text/10 bg-white object-cover object-[center_52%] shadow-card"
          />
        </div>
        <div className="mt-5 border-l-4 border-brand-orange pl-4">
          <h2 className="text-3xl font-black">陈永琪</h2>
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-sm font-semibold">
            <span className="whitespace-nowrap text-brand-muted">AI 产品经理</span>
            <span className="whitespace-nowrap text-brand-orange">Agent 产品实践者</span>
          </div>
        </div>
      </div>

      <div className="min-w-0 lg:py-0">
        <SlideHeading eyebrow="01 · ABOUT ME" title="把复杂 AI 系统，变成可验证的产品" />
        <div className="mt-4 flex items-start gap-3 border-y border-brand-text/10 py-2 text-sm leading-7 text-brand-muted sm:text-base">
          <GraduationCap className="mt-1 h-5 w-5 shrink-0 text-brand-orange" />
          <span><strong className="text-brand-text">中国科学院大学</strong> · 信息系统工程管理硕士在读</span>
        </div>
        <div className="mt-3 divide-y divide-brand-text/10">
          {experiences.map((experience) => (
            <div key={experience.company} className="grid gap-3 py-3 sm:grid-cols-[2.2rem_11rem_minmax(0,1fr)] sm:items-start">
              <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-brand-orange/10 text-brand-orange">
                {experience.icon}
              </div>
              <div>
                <div className="font-black">{experience.company}</div>
                <div className="mt-1 text-sm text-brand-muted">{experience.role}</div>
              </div>
              <p className="text-sm leading-6 text-brand-muted">{experience.detail}</p>
            </div>
          ))}
        </div>
        <p className="mt-4 max-w-3xl text-base font-bold leading-7 text-brand-text">
          FareSniper 是三段经历的交汇点：Agent 架构、评测闭环，以及复杂平台的工程落地。
        </p>
      </div>
    </div>
  )
}

function DealDefinitionSlide() {
  const users = [
    {
      title: '刚需型',
      question: '周五晚必须走，现在该买吗？',
      constraint: '日期与时段固定',
      advantage: '持续盯同一路线，进入心理价就提醒',
      icon: <Clock3 className="h-7 w-7" />,
      color: 'bg-brand-orange/10 text-brand-orange',
    },
    {
      title: '弹性型',
      question: '日期能换，哪一天真的更便宜？',
      constraint: '价格优先，日期可调',
      advantage: '跨日期记录波动，识别个人低价窗口',
      icon: <Coins className="h-7 w-7" />,
      color: 'bg-brand-orange-light text-brand-orange',
    },
    {
      title: '全成本型',
      question: '带 20KG 行李，低价票还便宜吗？',
      constraint: '税费与行李不可忽略',
      advantage: '统一票价、机建燃油与行李成本',
      icon: <Luggage className="h-7 w-7" />,
      color: 'bg-green-50 text-green-600',
    },
  ]
  const priceMoments = [
    ['08:00', '¥620'],
    ['14:00', '¥480'],
    ['22:00', '¥560'],
  ]
  return (
    <div className="mx-auto flex min-h-full max-w-7xl flex-col justify-center">
      <SlideHeading eyebrow="02 · USER INSIGHT" title="用户不是在找最低价，而是在等购买窗口" />
      <div className="mt-4 flex flex-col gap-3 rounded-[20px] border border-brand-orange/10 bg-brand-orange/5 px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-xs font-black text-brand-orange">同一航线 · 同一天</div>
          <div className="mt-1 text-sm font-bold text-brand-text">机票价格随库存持续变化，一次搜索只截到一个点。</div>
        </div>
        <div className="flex items-center gap-2 sm:gap-4">
          {priceMoments.map(([time, price], index) => (
            <React.Fragment key={time}>
              <div className="text-center">
                <div className={`text-lg font-black ${index === 1 ? 'text-green-600' : 'text-brand-text'}`}>{price}</div>
                <div className="text-[10px] font-bold text-brand-muted">{time}</div>
              </div>
              {index < priceMoments.length - 1 ? <ArrowRight className="h-4 w-4 text-brand-orange" /> : null}
            </React.Fragment>
          ))}
        </div>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        {users.map((user) => (
          <article key={user.title} className="rounded-[24px] border border-brand-text/5 bg-white p-5 shadow-card">
            <div className="flex items-center justify-between gap-3">
              <div className={`flex h-10 w-10 items-center justify-center rounded-2xl [&>svg]:h-6 [&>svg]:w-6 ${user.color}`}>{user.icon}</div>
              <span className="text-xs font-black text-brand-muted">{user.constraint}</span>
            </div>
            <h3 className="mt-4 text-xl font-black">{user.title}</h3>
            <p className="mt-2 min-h-12 text-base font-semibold leading-6 text-brand-text">“{user.question}”</p>
            <div className="mt-3 border-t border-brand-text/10 pt-3">
              <div className="text-[10px] font-black text-brand-orange">核心竞争力</div>
              <div className="mt-1 text-sm font-bold leading-6 text-brand-muted">{user.advantage}</div>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}

function TrustSlide() {
  const questions = [
    {
      question: '现在谁便宜？',
      category: 'OTA / 比价',
      answer: '擅长展示此刻的可售结果',
      gap: '跨平台口径与完整成本仍需用户核对',
      advantage: '多来源统一为同一份可比较事实',
      icon: <Network />,
    },
    {
      question: '什么时候买？',
      category: '价格提醒 / 预测',
      answer: '擅长追踪路线或判断买与等',
      gap: '价格变化与个人时段、预算、行李彼此分离',
      advantage: '监控的是个人购买窗口，不只是价格曲线',
      icon: <Radar />,
    },
    {
      question: '哪张适合我？',
      category: '通用 AI',
      answer: '擅长理解自然语言与偏好',
      gap: '缺少持续、可追溯的交易级价格事实',
      advantage: '记忆参与排序，结论绑定来源与数据状态',
      icon: <BrainCircuit />,
    },
  ]
  return (
    <div className="mx-auto flex min-h-full max-w-7xl flex-col justify-center">
      <SlideHeading eyebrow="03 · COMPETITIVE GAP" title="不是没有单点能力，而是缺少同一个决策闭环" />
      <p className="mt-3 max-w-5xl text-base leading-7 text-brand-muted">
        不列品牌功能表，只用用户最终要回答的三个问题看市场缺口。
      </p>
      <div className="mt-5 grid gap-4 lg:grid-cols-3">
        {questions.map((item) => (
          <article key={item.question} className="rounded-[24px] border border-brand-text/5 bg-white p-5 shadow-card">
            <div className="flex items-center justify-between gap-3">
              <div className="text-brand-orange [&>svg]:h-6 [&>svg]:w-6">{item.icon}</div>
              <span className="text-[10px] font-black text-brand-muted">{item.category}</span>
            </div>
            <h3 className="mt-4 text-2xl font-black">{item.question}</h3>
            <div className="mt-4 space-y-3 text-sm leading-6">
              <MarketAnswer label="已有答案" value={item.answer} />
              <MarketAnswer label="仍然缺少" value={item.gap} />
              <MarketAnswer label="FareSniper" value={item.advantage} highlight />
            </div>
          </article>
        ))}
      </div>
      <div className="mt-5 flex items-center gap-3 rounded-[20px] bg-brand-text px-5 py-3 text-sm font-bold text-white">
        <SearchCheck className="h-5 w-5 shrink-0 text-brand-orange-light" />
        市场空白 = 动态价格 × 完整成本 × 个人约束，三者尚未形成一条可信链路。
      </div>
    </div>
  )
}

function ProductSlide() {
  const steps = [
    { label: '定义购买条件', detail: '航线 · 日期 · 预算 · 时段 · 行李', icon: <BrainCircuit /> },
    { label: '实时拉取', detail: '查询时并发获取当前可用报价', icon: <Network /> },
    { label: '持续监控', detail: '关注后刷新价格并保留新鲜度', icon: <Radar /> },
    { label: '解释并提醒', detail: '阈值 + 完整成本 + 记忆 → 建议', icon: <SearchCheck /> },
  ]
  return (
    <div className="mx-auto flex min-h-full max-w-7xl flex-col justify-center">
      <SlideHeading eyebrow="04 · PRODUCT" title="不是替你搜一次，而是替你盯到值得买" />
      <p className="mt-4 max-w-4xl text-lg leading-8 text-brand-muted">
        搜索回答“现在有什么”，监控回答“什么时候值得买”。
      </p>
      <div className="mt-6 grid gap-4 lg:grid-cols-4">
        {steps.map((step, index) => (
          <div key={step.label} className="relative rounded-[24px] border border-brand-text/5 bg-white p-5 shadow-card">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brand-text text-white [&>svg]:h-5 [&>svg]:w-5">{step.icon}</div>
            <div className="mt-6 text-xs font-black text-brand-orange">STEP 0{index + 1}</div>
            <h3 className="mt-2 text-xl font-black">{step.label}</h3>
            <p className="mt-3 text-sm leading-7 text-brand-muted">{step.detail}</p>
            {index < steps.length - 1 ? <ArrowRight className="absolute -right-3 top-1/2 z-10 hidden h-6 w-6 -translate-y-1/2 rounded-full bg-brand-bg text-brand-orange lg:block" /> : null}
          </div>
        ))}
      </div>
      <div className="mt-6 grid gap-4 border-t border-brand-text/10 pt-5 md:grid-cols-3">
        <Metric value="实时" label="搜索时获取当前价格" />
        <Metric value="持续" label="关注后追踪价格变化" />
        <Metric value="同源" label="回答、卡片与提醒共用事实" />
      </div>
    </div>
  )
}

function DemoSlide() {
  return (
    <div className="mx-auto grid min-h-full max-w-7xl items-center gap-9 lg:grid-cols-[0.72fr_1.28fr] lg:gap-12">
      <div>
        <SlideHeading eyebrow="05 · LIVE DEMO" title="一句自然语言，完成一次可验证决策" />
        <div className="mt-7 rounded-[24px] bg-brand-text p-5 text-lg font-semibold leading-8 text-white shadow-card">
          “下周五从北京到长治”
        </div>
        <div className="mt-6 space-y-3">
          {['相对日期转换为具体日期', '城市映射到机场查询范围', '多来源结果统一成完整成本', '结果写入记忆并支持持续盯价'].map((item) => (
            <div key={item} className="flex items-center gap-3 text-sm font-semibold text-brand-muted sm:text-base">
              <Check className="h-4 w-4 shrink-0 text-green-600" />
              {item}
            </div>
          ))}
        </div>
        <a
          href={PRODUCT_URL}
          target="_blank"
          rel="noreferrer"
          className="mt-8 inline-flex h-11 items-center gap-2 rounded-2xl bg-brand-orange px-5 text-sm font-black text-white shadow-card transition hover:bg-brand-text"
        >
          打开现场产品
          <ExternalLink className="h-4 w-4" />
        </a>
      </div>
      <FarePreview compact />
    </div>
  )
}

function ArchitectureSlide() {
  const steps = [
    {
      number: '1',
      layer: '用户与偏好',
      title: '先知道是谁在问、他在意什么',
      detail: '确认登录身份，取回当前会话与长期偏好：常用机场、时间、行李、预算。',
      tech: 'FastAPI · bootstrap_session · Redis · PostgreSQL',
      flow: [
        { label: '用户输入自然语言', detail: '航线 · 日期 · 预算 · 行李等约束' },
        { label: '确认用户身份', detail: '登录凭证 JWT → user_id' },
        { label: '接上当前对话', detail: 'Redis 取回已确认的航线、日期等条件' },
        { label: '读取长期偏好', detail: 'PostgreSQL：常用机场、预算、航司与行李习惯' },
        { label: '形成用户上下文', detail: '身份 + 当前对话 + 长期偏好 + 本轮原话' },
      ],
      tone: 'blue' as const,
      icon: <ServerCog />,
    },
    {
      number: '2',
      layer: '理解需求',
      title: '把一句话整理成查询条件',
      detail: '识别出发地、目的地、日期等信息；确实缺信息才追问，有歧义时再让模型判断。',
      tech: 'fast_intent_match · ReAct · slot_filling · tool_router',
      flow: [
        { label: '判断用户要做什么', detail: '查航班 / 设置提醒 / 查询偏好' },
        { label: '整理查询条件', detail: '出发地 · 目的地 · 日期 · 预算 · 约束' },
        { label: '必要条件是否齐全？', detail: '先由规则检查，不让模型随意猜测' },
        {
          split: [
            { label: '不齐全', detail: '只追问缺失的一项' },
            { label: '齐全', detail: '选择下一步工具' },
          ],
          note: '用户补充后回到本层；有歧义时模型协助判断',
        },
        { label: '执行工具', detail: 'search_flights / set_alert / get_preferences' },
      ],
      tone: 'orange' as const,
      icon: <BrainCircuit />,
    },
    {
      number: '3',
      layer: '查询航班',
      title: '分别去多个来源查真实航班',
      detail: '飞猪、携程缓存和 Google 航班各有独立查询模块；同时发起查询，单个来源失败不影响其他来源。',
      tech: 'FlightQuery · search_flights · FlightSearchAggregator · 来源查询模块',
      flow: [
        { label: '整理统一查询', detail: '城市 → 机场范围；日期 → YYYY-MM-DD' },
        { label: '同时启动来源查询', detail: '每个来源独立超时、熔断与状态' },
        {
          split: [
            { label: '飞猪', detail: 'FlyAI CLI · 实时查询' },
            { label: '携程', detail: '读取 Mac 上传的价格快照' },
            { label: 'Google Flights', detail: 'SerpAPI · 国际来源' },
          ],
        },
        { label: '收齐所有可用来源', detail: '成功 · 无结果 · 超时 · 停用 · 过期' },
      ],
      tone: 'purple' as const,
      icon: <Network />,
    },
    {
      number: '4',
      layer: '比较与推荐',
      title: '收齐可用结果，再统一比较',
      detail: '统一税费、行李、平台和更新时间，保留缺失项，再按完整成本与个人偏好筛选和排序。',
      tech: 'FlightOffer · normalizer · preference_matcher · ResponseFacts',
      flow: [
        { label: '合并同一航班报价', detail: '航班号 + 机场 + 日期 + 时间' },
        { label: '校验报价可信度', detail: '数字价格 · HTTPS 链接 · 数据时效' },
        { label: '保留完整信息', detail: '票价 · 税费 · 行李 · 平台 · 更新时间' },
        { label: '计算完整成本', detail: '未知字段保持未知，不能默认成 0' },
        { label: '遍历全部候选', detail: '结合预算、航司、时间和行李偏好排序' },
        { label: '生成共同事实', detail: '最低价、航班卡与推荐共用同一结果' },
      ],
      tone: 'amber' as const,
      icon: <ShieldCheck />,
    },
    {
      number: '5',
      layer: '回答与持续盯价',
      title: '给出结果，关注后继续盯价',
      detail: '回答与价格卡使用同一份结果；关注后持续检查目标价，命中时提醒并更新用户偏好。',
      tech: 'NDJSON · render_response · memory writeback · PriceAlert · Worker · Web Push',
      flow: [
        { label: '展示搜索过程', detail: '来源状态与阶段结果只用于进度反馈' },
        { label: '交付最终结果', detail: '回答 + 航班卡 + 来源状态 + 推荐理由' },
        {
          split: [
            { label: '写回记忆', detail: '搜索、点击、收藏与明确偏好' },
            { label: '创建盯价', detail: '航线、日期与目标价' },
          ],
        },
        { label: 'Worker 定期检查', detail: '读取缓存中的最新可用报价' },
        { label: '达到目标价后提醒', detail: '标记已触发并发送 Web Push' },
        { label: '进入下一次决策', detail: '新行为成为下一次排序的偏好信号' },
      ],
      tone: 'green' as const,
      icon: <Radio />,
    },
  ]
  return (
    <div className="mx-auto flex min-h-full max-w-[1600px] flex-col justify-start py-1 2xl:justify-center">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="text-xs font-black text-brand-orange sm:text-sm">06 · 技术架构</div>
          <h2 className="mt-2 max-w-5xl font-serif text-3xl font-black leading-tight sm:text-4xl">用户说一句话之后，系统实际做了什么</h2>
        </div>
        <span className="self-start rounded-full border border-green-200 bg-green-50 px-3 py-1 text-[10px] font-black text-green-700 sm:self-auto">当前版本 · 已上线</span>
      </div>
      <p className="mt-1 max-w-5xl text-xs leading-5 text-brand-muted">五层对应五个真实问题，请求从左到右经过：认识用户 → 听懂需求 → 查询航班 → 比较推荐 → 回答并持续盯价</p>
      <div className="mt-3 grid items-stretch gap-3 lg:grid-cols-5">
        {steps.map((step, index) => (
          <RequestStep key={step.number} {...step} index={index} />
        ))}
      </div>
      <div className="mt-3 grid gap-3 border-t border-brand-text/10 pt-3 lg:grid-cols-2">
        <HarnessRail label="模型负责" value="理解歧义 · 选择工具 · 解释推荐" tone="model" />
        <HarnessRail label="系统负责" value="确认身份 · 接上对话 · 真实查询 · 来源状态 · 完整成本 · 全量比较 · 排序 · 提醒" tone="harness" />
      </div>
      <div className="mt-1 rounded-lg border border-dashed border-emerald-300 bg-emerald-50/60 px-4 py-1.5 text-[10px] font-bold text-emerald-800">
        反馈闭环：第 5 层记录的搜索、点击、收藏和盯价行为，会在下一次请求中被第 1 层重新读取。
      </div>
    </div>
  )
}

function MonitoringSlide() {
  const monitorChain = [
    {
      label: '创建价格提醒',
      detail: '航线 · 日期 · 目标价',
      status: 'live' as const,
      icon: <BellRing />,
    },
    {
      label: '每 15 分钟检查',
      detail: '读取缓存中的最新报价',
      status: 'live' as const,
      icon: <Clock3 />,
    },
    {
      label: '命中后通知',
      detail: 'Web Push · 标记已触发',
      status: 'live' as const,
      icon: <Radio />,
    },
    {
      label: '动态检查频率',
      detail: '越临期或越接近目标价，查得越勤',
      status: 'next' as const,
      icon: <RefreshCw />,
    },
    {
      label: '判断购买窗口',
      detail: '价格 · 时间 · 行李 · 历史低位',
      status: 'next' as const,
      icon: <Radar />,
    },
    {
      label: '可靠多渠道通知',
      detail: '先落库再投递 · 飞书 · 微信',
      status: 'next' as const,
      icon: <Radio />,
    },
  ]
  const capabilities = [
    {
      title: '什么时候查',
      current: '所有提醒固定每 15 分钟检查',
      target: '临近出发或接近目标价时自动加快',
    },
    {
      title: '什么时候提醒',
      current: '只判断总价是否低于目标价',
      target: '同时满足时间、行李、完整成本和历史低位',
    },
    {
      title: '怎么避免漏通知',
      current: '触发后直接发送 Web Push',
      target: '事件先落库、幂等去重、失败自动重试',
    },
    {
      title: '怎么安全上线',
      current: 'LangSmith Trace + 自动化测试',
      target: '来源健康度、分阶段放量和一键回滚',
    },
  ]
  return (
    <div className="mx-auto flex min-h-full max-w-7xl flex-col justify-center">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <SlideHeading eyebrow="08 · 演进路线" title="当前已经做到什么，下一步还要补什么" />
        <div className="flex gap-2 text-[10px] font-black">
          <span className="rounded-full border border-green-200 bg-green-50 px-3 py-1 text-green-700">绿色 · 已上线</span>
          <span className="rounded-full border border-brand-orange/20 bg-brand-orange-light px-3 py-1 text-brand-orange">橙色 · 下一步</span>
        </div>
      </div>
      <p className="mt-2 max-w-5xl text-sm leading-6 text-brand-muted">
        当前已经能“盯目标价”；下一步要升级成“判断何时值得买，并保证消息送得到”。
      </p>
      <div className="mt-4 grid gap-2 lg:grid-cols-6">
        {monitorChain.map((node, index) => (
          <EngineeringChainNode key={node.label} {...node} index={index} total={monitorChain.length} />
        ))}
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-4">
        {capabilities.map((capability, index) => (
          <EvolutionCapability key={capability.title} {...capability} priority={index + 1} />
        ))}
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-[1.35fr_0.65fr]">
        <div className="rounded-lg bg-brand-text px-4 py-3 text-white shadow-card">
          <div className="text-[9px] font-black text-brand-orange-light">购买窗口的确定性条件</div>
          <div className="mt-1 text-sm font-bold leading-5">约束满足 ∧ 报价有效 ∧（总价达到目标 或 进入历史低位）</div>
        </div>
        <div className="flex items-center justify-center rounded-lg border border-brand-orange/20 bg-brand-orange-light px-4 py-3 text-center text-xs font-black text-brand-text">
          规则负责触发；模型只解释“为什么现在值得买”
        </div>
      </div>
    </div>
  )
}

function DecisionsSlide() {
  const evalFacts = [
    {
      value: '50',
      label: '离线种子样本',
      detail: '正常 · 日期 · 多轮 · 边界 · 对抗',
    },
    {
      value: '5',
      label: '评测维度',
      detail: '意图 · 追问 · 信号 · 建议 · 格式',
    },
    {
      value: 'P0–P3',
      label: '风险分级',
      detail: '安全 / 崩溃 → 体验与长尾',
    },
    {
      value: 'Trace→Gate',
      label: '修复闭环',
      detail: '线上发现 → 样本固化 → 回归门禁',
    },
  ]
  const badCases = [
    {
      layer: 'Intent / State',
      symptom: '用户改了航线，旧日期被错误沿用',
      guard: '清空旧日期 + 必填槽位追问 + 多轮回归',
    },
    {
      layer: 'Provider / Data',
      symptom: '慢来源拖垮请求，快来源结果也丢失',
      guard: '并发隔离 + 10s 超时 + 熔断与部分返回测试',
    },
    {
      layer: 'Truth / Ranking',
      symptom: '不合资格或异币种报价错误成为最低价',
      guard: '携程快照契约 / winner 资格 / 币种原子性测试',
    },
    {
      layer: 'Output / UX',
      symptom: 'AI 说 ¥700，卡片 ¥650；未知行李被当作免费',
      guard: 'ResponseFacts 同源 + null 保真 + 前后端契约测试',
    },
  ]
  return (
    <div className="mx-auto flex min-h-full max-w-7xl flex-col justify-center">
      <SlideHeading eyebrow="07 · 评测护栏" title="Bad Case 不是事故记录，而是回归资产" />
      <p className="mt-3 max-w-5xl text-base leading-7 text-brand-muted">
        线上 Trace 负责发现问题，离线数据集负责稳定复现，自动化门禁负责阻止同类错误再次上线。
      </p>
      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {evalFacts.map((fact) => (
          <EvalFact key={fact.label} {...fact} />
        ))}
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-[0.72fr_1.28fr]">
        <div className="rounded-[20px] bg-brand-text p-4 text-white shadow-card">
          <div className="flex items-center gap-2 text-xs font-black text-brand-orange-light">
            <RefreshCw className="h-4 w-4" />
            HARNESS QUALITY LOOP
          </div>
          <div className="mt-3 space-y-2.5">
            {[
              ['01', 'Observe', 'LangSmith span + 安全脱敏'],
              ['02', 'Triage', '按影响范围分为 P0–P3'],
              ['03', 'Reproduce', '固化最小输入、状态与 Provider fixture'],
              ['04', 'Gate', '单元 / 契约 / E2E 回归后再部署'],
            ].map(([step, title, detail]) => (
              <div key={step} className="grid grid-cols-[2rem_4.2rem_minmax(0,1fr)] items-baseline gap-2 border-b border-white/10 pb-2 last:border-0 last:pb-0">
                <span className="text-xs font-black text-brand-orange-light">{step}</span>
                <span className="text-sm font-black">{title}</span>
                <span className="text-xs leading-5 text-white/70">{detail}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="overflow-hidden rounded-[20px] border border-brand-text/5 bg-white shadow-sm">
          <div className="hidden grid-cols-[0.68fr_1.05fr_1.27fr] gap-3 border-b border-brand-text/10 bg-brand-orange-light px-4 py-2 text-xs font-black text-brand-text lg:grid">
            <span>失效层</span><span>真实 Bad Case</span><span>沉淀为 Harness Guard</span>
          </div>
          {badCases.map((badCase) => (
            <BadCaseRow key={badCase.layer} {...badCase} />
          ))}
        </div>
      </div>
      <p className="mt-3 text-center text-sm font-black text-brand-text">
        评测目标不是证明模型聪明，而是持续扩大 Harness 能够确定兜住的边界。
      </p>
    </div>
  )
}

function ClosingSlide() {
  return (
    <div className="mx-auto flex min-h-full max-w-7xl flex-col justify-center">
      <div className="max-w-5xl">
        <div className="text-sm font-black text-brand-orange">09 · 下一步</div>
        <h2 className="mt-4 font-serif text-5xl font-black leading-tight sm:text-6xl">
          不做另一个卖票平台，<br />做一个代表用户决策的 Agent。
        </h2>
        <p className="mt-4 max-w-3xl text-lg leading-8 text-brand-muted">
          它记住用户真正关心的东西，用多平台证据验证价格，并在合适的时间给出可解释的购买建议。
        </p>
      </div>
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <ClosingItem icon={<Network />} title="更多合规数据源" detail="提高国内外航线覆盖与字段完整度" />
        <ClosingItem icon={<Radar />} title="持续价格监控" detail="从一次搜索走向主动发现机会" />
        <ClosingItem icon={<Sparkles />} title="记忆驱动排序" detail="让每一次使用都更接近个人标准" />
      </div>
      <div className="mt-6 flex flex-col gap-4 border-t border-brand-text/10 pt-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-2xl font-black">FareSniper</div>
          <div className="mt-1 text-sm text-brand-muted">懂你的标准，才叫真特价。</div>
        </div>
        <a href={PRODUCT_URL} target="_blank" rel="noreferrer" className="inline-flex h-11 items-center gap-2 self-start rounded-2xl bg-brand-text px-5 text-sm font-black text-white shadow-card hover:bg-brand-orange sm:self-auto">
          体验产品
          <ExternalLink className="h-4 w-4" />
        </a>
      </div>
    </div>
  )
}

function SlideHeading({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div>
      <div className="text-xs font-black text-brand-orange sm:text-sm">{eyebrow}</div>
      <h2 className="mt-3 max-w-5xl font-serif text-4xl font-black leading-tight sm:text-5xl">{title}</h2>
    </div>
  )
}

function Tag({ icon, label }: { icon: React.ReactElement; label: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-2xl border border-brand-text/5 bg-white px-3 py-2 text-brand-muted shadow-sm [&>svg]:h-4 [&>svg]:w-4 [&>svg]:text-brand-orange">
      {icon}{label}
    </span>
  )
}

function MarketAnswer({
  label,
  value,
  highlight = false,
}: {
  label: string
  value: string
  highlight?: boolean
}) {
  return (
    <div className={`grid grid-cols-[4.5rem_minmax(0,1fr)] gap-2 border-b border-brand-text/10 pb-3 last:border-0 last:pb-0 ${highlight ? 'font-bold text-brand-text' : 'text-brand-muted'}`}>
      <span className={`text-xs font-black ${highlight ? 'text-brand-orange' : 'text-brand-muted'}`}>{label}</span>
      <span>{value}</span>
    </div>
  )
}

function Metric({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="text-3xl font-black text-brand-orange">{value}</div>
      <div className="mt-2 text-sm font-semibold text-brand-muted">{label}</div>
    </div>
  )
}

type ArchitectureLayerTone = 'blue' | 'orange' | 'purple' | 'amber' | 'green'

type ArchitectureFlowNode =
  | { label: string; detail: string }
  | { split: { label: string; detail: string }[]; note?: string }

function RequestStep({
  number,
  layer,
  title,
  detail,
  tech,
  flow,
  tone,
  icon,
  index,
}: {
  number: string
  layer: string
  title: string
  detail: string
  tech: string
  flow: ArchitectureFlowNode[]
  tone: ArchitectureLayerTone
  icon: React.ReactElement
  index: number
}) {
  const toneClasses: Record<ArchitectureLayerTone, { border: string; icon: string; number: string }> = {
    blue: { border: 'border-sky-200', icon: 'bg-sky-600', number: 'text-sky-700' },
    orange: { border: 'border-orange-200', icon: 'bg-orange-500', number: 'text-orange-700' },
    purple: { border: 'border-violet-200', icon: 'bg-violet-600', number: 'text-violet-700' },
    amber: { border: 'border-amber-200', icon: 'bg-amber-500', number: 'text-amber-700' },
    green: { border: 'border-emerald-200', icon: 'bg-emerald-600', number: 'text-emerald-700' },
  }
  const classes = toneClasses[tone]
  return (
    <div className={`relative flex min-h-[455px] flex-col rounded-xl border bg-white p-3 shadow-sm 2xl:min-h-[485px] 2xl:p-4 ${classes.border}`}>
      <div className="flex items-center gap-2">
        <span className={`flex h-9 w-9 items-center justify-center rounded-lg text-white [&>svg]:h-4 [&>svg]:w-4 ${classes.icon}`}>{icon}</span>
        <div>
          <span className={`text-[9px] font-black ${classes.number}`}>第 {number} 层</span>
          <div className="text-xs font-black text-brand-text">{layer}</div>
        </div>
      </div>
      <div className="mt-3 min-w-0">
        <h3 className="text-sm font-black leading-5 text-brand-text 2xl:text-base 2xl:leading-6">{title}</h3>
        <p className="mt-2 text-[9px] font-semibold leading-[14px] text-brand-muted 2xl:text-[11px] 2xl:leading-[18px]">{detail}</p>
      </div>
      <div className="mt-2 flex flex-1 flex-col border-t border-brand-text/10 pt-2">
        <div className={`mb-1 text-[9px] font-black ${classes.number}`}>仓库实现 · 本层流程</div>
        <div className="flex flex-1 flex-col gap-0.5">
          {flow.map((item, flowIndex) => (
            <React.Fragment key={'split' in item ? `split-${flowIndex}` : item.label}>
              {'split' in item ? (
                <div>
                  <div className={`grid gap-1 ${item.split.length === 3 ? 'grid-cols-1' : 'grid-cols-2'}`}>
                    {item.split.map((branch) => (
                      <div key={branch.label} className={`rounded-md border px-1.5 py-0.5 text-center ${classes.border} bg-brand-bg/50`}>
                        <div className="text-[9px] font-black leading-3">{branch.label}</div>
                        <div className="mt-0.5 text-[7px] font-semibold leading-[10px] text-brand-muted 2xl:text-[8px] 2xl:leading-3">{branch.detail}</div>
                      </div>
                    ))}
                  </div>
                  {item.note ? <div className="mt-0.5 text-center text-[7px] font-semibold leading-[10px] text-brand-muted">{item.note}</div> : null}
                </div>
              ) : (
                <div className={`rounded-md border px-2 py-0.5 text-center ${flowIndex === flow.length - 1 ? `${classes.border} bg-brand-bg/60` : 'border-brand-text/10 bg-white'}`}>
                  <div className="text-[9px] font-black leading-3 2xl:text-[10px]">{item.label}</div>
                  <div className="mt-0.5 text-[7px] font-semibold leading-[10px] text-brand-muted 2xl:text-[8px] 2xl:leading-3">{item.detail}</div>
                </div>
              )}
              {flowIndex < flow.length - 1 ? <ArrowRight className="mx-auto h-2 w-2 rotate-90 text-brand-text/45" strokeWidth={2} /> : null}
            </React.Fragment>
          ))}
        </div>
        <p className="mt-1 border-t border-brand-text/10 pt-1.5 text-[7px] font-bold leading-[11px] text-brand-text/55 2xl:text-[8px]">实际模块：{tech}</p>
      </div>
      {index < 4 ? (
        <ArrowRight aria-hidden="true" data-testid={`architecture-handoff-${number}`} className="absolute -bottom-3 left-1/2 z-20 h-5 w-5 -translate-x-1/2 rotate-90 rounded-full bg-brand-bg text-brand-orange lg:-right-4 lg:bottom-auto lg:left-auto lg:top-1/2 lg:translate-x-0 lg:-translate-y-1/2 lg:rotate-0" />
      ) : null}
    </div>
  )
}

function EngineeringChainNode({
  icon,
  label,
  detail,
  status,
  index,
  total,
}: {
  icon: React.ReactElement
  label: string
  detail: string
  status: 'live' | 'next'
  index: number
  total: number
}) {
  return (
    <div className={`relative min-h-24 rounded-lg border px-3 py-3 shadow-sm ${
      status === 'live' ? 'border-emerald-200 bg-emerald-50/60' : 'border-brand-orange/20 bg-brand-orange-light'
    }`}>
      <div className="flex items-center justify-between gap-2">
        <span className={`flex h-7 w-7 items-center justify-center rounded-md text-white [&>svg]:h-4 [&>svg]:w-4 ${status === 'live' ? 'bg-emerald-600' : 'bg-brand-text'}`}>{icon}</span>
        <span className={`text-[8px] font-black ${status === 'live' ? 'text-emerald-700' : 'text-brand-orange'}`}>{status === 'live' ? '已上线' : '下一步'}</span>
      </div>
      <h3 className="mt-2 text-sm font-black">{label}</h3>
      <p className="mt-1 text-[10px] font-semibold leading-4 text-brand-muted">{detail}</p>
      {index < total - 1 ? <ArrowRight className="absolute -right-2 top-1/2 z-10 hidden h-4 w-4 -translate-y-1/2 rounded-full bg-brand-bg text-brand-orange lg:block" /> : null}
    </div>
  )
}

function EvolutionCapability({
  title,
  current,
  target,
  priority,
}: {
  title: string
  current: string
  target: string
  priority: number
}) {
  return (
    <div className="rounded-lg border border-brand-text/10 bg-white px-4 py-3 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-black">{title}</h3>
        <span className="text-[9px] font-black text-brand-orange">问题 {priority}</span>
      </div>
      <div className="mt-2 rounded-md bg-brand-bg px-3 py-2 text-[10px] font-semibold leading-4 text-brand-muted">当前 · {current}</div>
      <ArrowRight className="mx-auto my-1 h-3.5 w-3.5 rotate-90 text-brand-orange" />
      <div className="rounded-md bg-brand-orange-light px-3 py-2 text-[10px] font-bold leading-4 text-brand-text">下一步 · {target}</div>
    </div>
  )
}

function HarnessRail({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone: 'model' | 'harness' | 'failure'
}) {
  const toneClass = tone === 'harness'
    ? 'bg-brand-text text-white'
    : tone === 'model'
      ? 'border-brand-orange/20 bg-brand-orange-light text-brand-text'
      : 'border-green-200 bg-green-50 text-brand-text'
  return (
    <div className={`rounded-lg border border-transparent px-4 py-2 shadow-sm ${toneClass}`}>
      <div className={`text-[9px] font-black ${tone === 'harness' ? 'text-brand-orange-light' : 'text-brand-orange'}`}>{label}</div>
      <div className="mt-0.5 text-[11px] font-bold">{value}</div>
    </div>
  )
}

function EvalFact({ value, label, detail }: { value: string; label: string; detail: string }) {
  return (
    <div className="rounded-[18px] border border-brand-text/5 bg-white px-4 py-3 shadow-sm sm:grid sm:grid-cols-[auto_minmax(0,1fr)] sm:items-center sm:gap-3">
      <div className="whitespace-nowrap text-lg font-black text-brand-orange sm:text-xl">{value}</div>
      <div className="mt-2 sm:mt-0">
        <div className="text-sm font-black">{label}</div>
        <div className="mt-0.5 text-[11px] text-brand-muted">{detail}</div>
      </div>
    </div>
  )
}

function BadCaseRow({ layer, symptom, guard }: { layer: string; symptom: string; guard: string }) {
  return (
    <div className="grid gap-1.5 border-b border-brand-text/10 px-4 py-3 text-xs leading-5 last:border-0 lg:grid-cols-[0.68fr_1.05fr_1.27fr] lg:gap-3 lg:py-2.5">
      <span className="font-black text-brand-orange">{layer}</span>
      <span className="font-semibold text-brand-text">{symptom}</span>
      <span className="text-brand-muted">{guard}</span>
    </div>
  )
}

function ClosingItem({ icon, title, detail }: { icon: React.ReactElement; title: string; detail: string }) {
  return (
    <div className="rounded-[28px] border border-brand-text/5 bg-white p-4 shadow-card">
      <div className="text-brand-orange [&>svg]:h-6 [&>svg]:w-6">{icon}</div>
      <h3 className="mt-3 text-lg font-black">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-brand-muted">{detail}</p>
    </div>
  )
}

function FarePreview({ compact = false }: { compact?: boolean }) {
  return (
    <div className="overflow-hidden rounded-[28px] border border-brand-orange/10 bg-white shadow-card">
      <DiscoveryCardContent
        from="北京"
        to="长治"
        date="2026-07-24"
        basePrice={250}
        totalPrice={350}
        tax={100}
        taxSource="regulatory_estimate"
        baggageFee={0}
        baggageAllowance="20KG"
        hasBaggage
        currency="CNY"
        platform="携程旅行"
        recommendScore="8.6"
        prices={[
          {
            id: 'open-mic-ctrip',
            name: '携程旅行',
            price: 350,
            currency: 'CNY',
            price_status: 'stale',
            provider_status: 'stale',
            data_provider: 'ctrip_snapshot',
            data_freshness: 'stale',
          },
          {
            id: 'open-mic-flyai',
            name: '飞猪旅行',
            price: 390,
            currency: 'CNY',
            price_status: 'priced',
            provider_status: 'success',
            data_provider: 'flyai',
            data_freshness: 'unknown',
          },
        ]}
        compact={compact}
        demo
      />
    </div>
  )
}
