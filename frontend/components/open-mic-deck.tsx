'use client'

import React from 'react'
import Image from 'next/image'
import { AnimatePresence, motion } from 'motion/react'
import { DiscoveryCardContent } from '@/components/discovery-card-content'
import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
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
  RefreshCw,
  Route,
  SearchCheck,
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
    duration: '02:30',
    notes: [
      '一条请求只走六步：组装 Context → 意图与槽位 → Agent 规划 → 多源并发 → 事实裁决 → SSE 输出与提醒。',
      '意图链路是 Registry 召回候选、确定性抽槽和必填校验，ReAct 只处理歧义并选择 Typed Tool。',
      '模型负责理解、规划和解释；Harness 负责状态、权限、超时、报价资格、同源输出与 Trace。',
    ],
  },
  {
    id: 'decisions',
    label: '评测闭环',
    duration: '02:00',
    notes: [
      '离线有 50 条种子样本，覆盖正常、相对日期、多轮追问、边界异常与对抗；评测意图、追问、信号、建议和格式。',
      '线上 LangSmith Trace 发现问题后，按 P0–P3 定级，再固化为最小复现样本和单元、契约或 E2E 回归测试。',
      '典型 Bad Case 包括旧日期串线、慢 Provider 拖垮请求、不合资格或异币种报价误胜，以及 AI 文案与卡片价格不一致。',
    ],
  },
  {
    id: 'closing',
    label: '结尾',
    duration: '01:10',
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
  const nodes = [
    {
      tag: 'INPUT',
      label: 'Context',
      detail: 'API + Redis 会话 + PG 记忆',
      icon: <Database />,
    },
    {
      tag: 'UNDERSTAND',
      label: 'Intent',
      detail: 'Registry 召回 → 抽槽 → 必填校验',
      icon: <SearchCheck />,
    },
    {
      tag: 'PLAN',
      label: 'Agent',
      detail: 'ReAct 决策 → Typed Tool Router',
      icon: <BrainCircuit />,
    },
    {
      tag: 'FETCH',
      label: 'Providers',
      detail: '飞猪实时｜携程快照｜国际源',
      icon: <Network />,
    },
    {
      tag: 'DECIDE',
      label: 'Truth',
      detail: 'FlightOffer → 完整成本 → winner',
      icon: <BadgeCheck />,
    },
    {
      tag: 'DELIVER',
      label: 'Output',
      detail: 'ResponseFacts → SSE / 卡片 / 提醒',
      icon: <Sparkles />,
    },
  ]
  return (
    <div className="mx-auto flex min-h-full max-w-7xl flex-col justify-center">
      <SlideHeading eyebrow="06 · TECHNICAL CHAIN" title="从一句需求，到一条可验证的购买建议" />
      <p className="mt-3 max-w-5xl text-base leading-7 text-brand-muted">
        每个节点只有一个职责；任何模型或数据源失败，都不能越过事实边界。
      </p>
      <div className="mt-6 grid items-stretch gap-3 lg:grid-cols-6">
        {nodes.map((node, index) => (
          <ArchitectureNode key={node.label} {...node} index={index} total={nodes.length} />
        ))}
      </div>
      <div className="mt-5 grid gap-3 lg:grid-cols-[0.82fr_1.38fr_1fr]">
        <HarnessRail label="MODEL" value="歧义理解 · 工具规划 · 结果解释" tone="model" />
        <HarnessRail label="HARNESS" value="状态 · 权限 · 超时 · 报价资格 · Grounding" tone="harness" />
        <HarnessRail label="OBSERVE" value="LangSmith Trace → Bad Case → Gate" tone="failure" />
      </div>
      <div className="mt-3 flex items-center justify-center gap-2 text-sm font-bold text-brand-muted">
        <RefreshCw className="h-4 w-4 text-brand-orange" />
        点击 / 盯价 / 购买信号 → 可解释记忆 → 下一次排序
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
      <SlideHeading eyebrow="07 · EVALUATION HARNESS" title="Bad Case 不是事故记录，而是回归资产" />
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
        <div className="text-sm font-black text-brand-orange">08 · WHAT NEXT</div>
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

function ArchitectureNode({
  icon,
  tag,
  label,
  detail,
  index,
  total,
}: {
  icon: React.ReactElement
  tag: string
  label: string
  detail: string
  index: number
  total: number
}) {
  return (
    <div className={`relative flex min-h-44 flex-col rounded-[20px] border p-4 shadow-sm ${
      index === 1
        ? 'border-brand-orange/30 bg-brand-orange-light'
        : index === total - 2
          ? 'border-green-200 bg-green-50'
          : 'border-brand-text/5 bg-white'
    }`}>
      <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-brand-text text-white [&>svg]:h-5 [&>svg]:w-5">{icon}</div>
      <div className="mt-4 text-[10px] font-black text-brand-orange">{tag}</div>
      <h3 className="mt-1 text-lg font-black">{label}</h3>
      <p className="mt-auto pt-3 text-xs font-semibold leading-5 text-brand-muted">{detail}</p>
      {index < total - 1 ? <ArrowRight className="absolute -right-2.5 top-1/2 z-10 hidden h-5 w-5 -translate-y-1/2 rounded-full bg-brand-bg text-brand-orange lg:block" /> : null}
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
    <div className={`rounded-[18px] border border-transparent px-4 py-3 shadow-sm ${toneClass}`}>
      <div className={`text-[10px] font-black ${tone === 'harness' ? 'text-brand-orange-light' : 'text-brand-orange'}`}>{label}</div>
      <div className="mt-1 text-xs font-bold">{value}</div>
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
