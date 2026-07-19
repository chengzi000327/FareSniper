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
  Eye,
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
    label: '核心洞察',
    duration: '01:20',
    notes: [
      '特价不是统一的最低数字。时间、预算和行李不同，用户眼里的最优解也不同。',
      '所以产品目标不是找出一个全网统一最低价，而是求出用户约束下的相对最优解。',
    ],
  },
  {
    id: 'trust',
    label: '信任缺口',
    duration: '01:00',
    notes: [
      '我不需要证明某个平台一定在杀熟，但用户已经无法验证推荐究竟是在服务自己，还是服务平台转化。',
      '解决办法不是再造一个更黑的推荐模型，而是让证据可比较、来源可追溯、缺失信息不伪造。',
    ],
  },
  {
    id: 'product',
    label: '产品方案',
    duration: '01:30',
    notes: [
      'FareSniper 用一个闭环完成四件事：理解需求、聚合比较、解释价格、沉淀记忆。',
      '它的差异不是多一个聊天框，而是把用户标准和多平台事实放进同一个决策过程。',
    ],
  },
  {
    id: 'demo',
    label: '现场演示',
    duration: '03:00',
    notes: [
      '现场输入：下周五从北京到长治。',
      '依次说明日期归一化、机场范围、多来源查询、完整成本拆分、平台跳转与记忆写回。',
      '若网络不稳定，就使用本页结果卡继续讲，不在台上重复刷新。',
    ],
  },
  {
    id: 'architecture',
    label: 'Agent 内部',
    duration: '02:30',
    notes: [
      '不要按组件名念架构。沿着一次请求讲：恢复上下文 → 识别与追问 → 并行搜索 → 归一化证据 → 冻结后输出。',
      '模型 8 秒超时或关键要素不完整时进入确定性槽位链；单个 Provider 10 秒超时或熔断时，其他来源仍可继续返回。',
      '核心分工是：LLM 负责理解与工具编排，工程系统负责日期、机场、价格、新鲜度和最终事实。',
    ],
  },
  {
    id: 'decisions',
    label: '可信闭环',
    duration: '01:50',
    notes: [
      '可信依赖四个不变量：关键槽位完整、未知字段不补全、winner 资格可复算、文案和卡片共享冻结快照。',
      '形成两个反馈环：用户行为进入可编辑记忆并影响下一次排序；LangSmith Trace 进入 Bad Case、修正规则或 Provider、再做回归测试。',
      '因此闭环不是“模型越用越聪明”，而是每次错误都能定位，每次改动都能验证。',
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
      <div className="relative mx-auto w-full max-w-sm lg:max-w-[17rem] 2xl:max-w-sm">
        <div className="absolute -bottom-4 -left-4 h-full w-full rounded-[28px] bg-brand-orange" />
        <Image
          src="/open-mic/chen-yongqi.png"
          alt="陈永琪"
          width={617}
          height={617}
          priority
          className="relative aspect-square w-full rounded-[28px] border border-brand-text/10 bg-white object-cover object-top shadow-card"
        />
        <div className="relative mt-4 border-l-4 border-brand-orange pl-4">
          <h2 className="text-3xl font-black">陈永琪</h2>
          <p className="mt-2 text-base font-semibold text-brand-muted">AI 产品经理 · Agent 产品实践者</p>
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
  const personas = [
    {
      title: '时间优先',
      quote: '我只能周五晚上走',
      answer: '合适时段 > 最低裸价',
      icon: <Clock3 className="h-7 w-7" />,
      color: 'bg-brand-orange/10 text-brand-orange',
    },
    {
      title: '价格优先',
      quote: '日期可以改，只要够便宜',
      answer: '可调整日期换取低价',
      icon: <Coins className="h-7 w-7" />,
      color: 'bg-brand-orange-light text-brand-orange',
    },
    {
      title: '完整成本优先',
      quote: '我要带一个 20kg 行李箱',
      answer: '裸票价 ≠ 最终成本',
      icon: <Luggage className="h-7 w-7" />,
      color: 'bg-green-50 text-green-600',
    },
  ]
  return (
    <div className="mx-auto flex min-h-full max-w-7xl flex-col justify-center">
      <SlideHeading eyebrow="02 · INSIGHT" title="特价，从来不是统一的最低数字" />
      <p className="mt-4 max-w-5xl text-base leading-7 text-brand-muted sm:text-lg">
        同一张机票，对不同的人可能有完全不同的价值。产品真正要求解的是用户约束下的相对最优解。
      </p>
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        {personas.map((persona, order) => (
          <article key={persona.title} className="rounded-[28px] border border-brand-text/5 bg-white p-5 shadow-card">
            <div className={`flex h-10 w-10 items-center justify-center rounded-2xl [&>svg]:h-6 [&>svg]:w-6 ${persona.color}`}>{persona.icon}</div>
            <div className="mt-5 text-xs font-black text-brand-muted">0{order + 1}</div>
            <h3 className="mt-2 text-xl font-black">{persona.title}</h3>
            <p className="mt-3 min-h-12 border-l-2 border-brand-orange/30 pl-4 text-base leading-6 text-brand-muted">“{persona.quote}”</p>
            <div className="mt-3 flex items-center gap-2 text-sm font-bold text-brand-orange">
              <ArrowRight className="h-4 w-4" />
              {persona.answer}
            </div>
          </article>
        ))}
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-3 rounded-[24px] border border-brand-orange/10 bg-brand-orange/5 px-6 py-4 text-base font-bold sm:text-lg">
        <span className="text-brand-orange">个人特价</span>
        <span>=</span>
        <span>满足出行约束</span>
        <span>+</span>
        <span>完整成本较低</span>
        <span>+</span>
        <span>符合个人偏好</span>
      </div>
    </div>
  )
}

function TrustSlide() {
  const rows = [
    ['平台 A', '¥420', '待确认', '不含', '¥?'],
    ['平台 B', '¥455', '¥100', '20KG', '¥555'],
    ['平台 C', '¥399', '¥100', '+¥120', '¥619'],
  ]
  return (
    <div className="mx-auto grid min-h-full max-w-7xl items-center gap-10 lg:grid-cols-[0.88fr_1.12fr] lg:gap-14">
      <div>
        <SlideHeading eyebrow="03 · TRUST GAP" title="用户不缺推荐，缺的是验证推荐的证据" />
        <p className="mt-6 text-lg leading-9 text-brand-muted">
          黑箱推荐让用户难以判断：这是最适合我的结果，还是平台最希望我购买的结果？
        </p>
        <div className="mt-8 space-y-4">
          <TrustPoint icon={<Network />} text="同一航班，多平台并排比较" />
          <TrustPoint icon={<Eye />} text="实时数据与历史快照明确标注" />
          <TrustPoint icon={<ShieldCheck />} text="缺失字段保持未知，不伪造免费" />
        </div>
      </div>
      <div className="min-w-0 overflow-hidden rounded-[28px] border border-brand-text/5 bg-white shadow-card">
        <div className="flex items-center justify-between border-b border-brand-text/10 px-5 py-4">
          <div>
            <div className="text-sm font-black">同一航班 · 不同答案</div>
            <div className="mt-1 text-xs text-brand-muted">裸价并不等于完整成本</div>
          </div>
          <SearchCheck className="h-5 w-5 text-green-600" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead className="bg-brand-orange/5 text-brand-muted">
              <tr>{['来源', '票价', '机建燃油', '行李', '可比较总价'].map((title) => <th key={title} className="px-5 py-3 font-bold">{title}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-brand-text/5">
              {rows.map((row, rowIndex) => (
                <tr key={row[0]} className={rowIndex === 1 ? 'bg-green-50/70' : ''}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className={`px-5 py-4 ${cellIndex === 4 ? 'font-black text-brand-orange' : ''}`}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function ProductSlide() {
  const steps = [
    { label: '理解', detail: '城市、日期、预算、时段', icon: <BrainCircuit /> },
    { label: '比较', detail: '飞猪实时 + 携程快照', icon: <Network /> },
    { label: '解释', detail: '票价、税费、行李、来源', icon: <SearchCheck /> },
    { label: '记住', detail: '查询、点击与长期偏好', icon: <Database /> },
  ]
  return (
    <div className="mx-auto flex min-h-full max-w-7xl flex-col justify-center">
      <SlideHeading eyebrow="04 · PRODUCT" title="从一次搜索，走向持续决策" />
      <p className="mt-4 max-w-4xl text-lg leading-8 text-brand-muted">
        FareSniper 的核心不是增加一个聊天入口，而是把用户标准、多平台事实和可解释记忆放进同一个决策闭环。
      </p>
      <div className="mt-8 grid gap-4 lg:grid-cols-4">
        {steps.map((step, index) => (
          <React.Fragment key={step.label}>
            <div className="relative rounded-[28px] border border-brand-text/5 bg-white p-6 shadow-card">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-text text-white [&>svg]:h-5 [&>svg]:w-5">{step.icon}</div>
              <div className="mt-8 text-xs font-black text-brand-orange">STEP 0{index + 1}</div>
              <h3 className="mt-2 text-2xl font-black">{step.label}</h3>
              <p className="mt-3 text-sm leading-7 text-brand-muted">{step.detail}</p>
            </div>
          </React.Fragment>
        ))}
      </div>
      <div className="mt-8 grid gap-4 border-t border-brand-text/10 pt-7 md:grid-cols-3">
        <Metric value="< 5 min" label="目标决策时间" />
        <Metric value="同源" label="AI 回答与价格卡片" />
        <Metric value="可解释" label="推荐依据与记忆来源" />
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
  const stages = [
    {
      step: '01',
      label: '上下文与路由',
      detail: 'Redis 恢复 30 分钟会话槽位，PostgreSQL 偏好注入上下文。',
      flow: '动态意图 → ReAct',
      icon: <BrainCircuit />,
    },
    {
      step: '02',
      label: '要素校验与工具',
      detail: '缺少出发地、目的地或日期就先追问；用户身份由服务端注入。',
      flow: 'ask_user | search_flights',
      icon: <Route />,
    },
    {
      step: '03',
      label: '并行数据面',
      detail: '飞猪实时、携程快照与国际来源按航线并发，逐来源返回状态。',
      flow: 'async + 10s timeout',
      icon: <Network />,
    },
    {
      step: '04',
      label: '证据与输出',
      detail: 'FlightOffer 归一、去重和排序；冻结事实后同时生成文案与卡片。',
      flow: 'Normalize → Freeze → Render',
      icon: <BadgeCheck />,
    },
  ]
  return (
    <div className="mx-auto flex min-h-full max-w-7xl flex-col justify-center">
      <SlideHeading eyebrow="06 · REQUEST LIFECYCLE" title="一次请求，如何变成一份可验证的推荐" />
      <p className="mt-3 max-w-5xl text-base leading-7 text-brand-muted">
        主链负责完成任务，异常链保证可退化，证据链确保每一个价格都能追溯。
      </p>
      <div className="mt-6 grid items-stretch gap-4 lg:grid-cols-4">
        {stages.map((stage, index) => (
          <div
            key={stage.label}
            className={`relative rounded-[24px] border p-5 shadow-sm ${
              index === 1
                ? 'border-brand-orange/30 bg-brand-orange-light'
                : index === 3
                  ? 'border-green-200 bg-green-50'
                  : 'border-brand-text/5 bg-white'
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brand-text text-white [&>svg]:h-5 [&>svg]:w-5">{stage.icon}</div>
              <span className="text-xs font-black text-brand-orange">{stage.step}</span>
            </div>
            <h3 className="mt-4 text-lg font-black">{stage.label}</h3>
            <p className="mt-2 min-h-12 text-sm leading-6 text-brand-muted">{stage.detail}</p>
            <div className="mt-3 border-t border-brand-text/10 pt-3 text-xs font-bold text-brand-text">{stage.flow}</div>
            {index < stages.length - 1 ? (
              <ArrowRight className="absolute -right-3 top-1/2 z-10 hidden h-5 w-5 -translate-y-1/2 rounded-full bg-brand-bg text-brand-orange lg:block" />
            ) : null}
          </div>
        ))}
      </div>
      <div className="mt-5 grid gap-4 lg:grid-cols-3">
        <ArchitectureBand icon={<RefreshCw />} title="模型失败可退化" detail="LLM 8 秒超时后转入确定性槽位链，继续追问或搜索。" />
        <ArchitectureBand icon={<ShieldCheck />} title="来源失败可隔离" detail="Provider 10 秒超时；连续失败触发熔断，其他来源仍返回部分结果。" />
        <ArchitectureBand icon={<Radar />} title="链路全程可观测" detail="flight_search → provider.* → normalize → rank → stream_results。" />
      </div>
    </div>
  )
}

function DecisionsSlide() {
  const invariants = [
    ['输入完整', '机场目录与未来日期确定性校验；关键槽位不全，不启动搜索。'],
    ['数据诚实', '未知税费和行李保留 null；实时、过期、排队、超时状态全部显式。'],
    ['赢家可复算', '只有满足新鲜度、价格与链接条件的报价能成为 winning_price。'],
    ['输出同源', 'ResponseFacts 深拷贝并冻结；AI 文案和卡片只读取同一份快照。'],
  ]
  return (
    <div className="mx-auto flex min-h-full max-w-7xl flex-col justify-center">
      <SlideHeading eyebrow="07 · TRUSTED SYSTEM" title="可信不是模型说对，而是系统让它难以说错" />
      <div className="mt-6 grid gap-4 lg:grid-cols-4">
        {invariants.map(([title, detail], index) => (
          <div key={title} className="rounded-[24px] border border-brand-text/5 bg-white p-5 shadow-card">
            <div className="text-xs font-black text-brand-orange">INVARIANT 0{index + 1}</div>
            <h3 className="mt-3 text-lg font-black">{title}</h3>
            <p className="mt-2 text-sm leading-6 text-brand-muted">{detail}</p>
          </div>
        ))}
      </div>
      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <FeedbackLoop
          icon={<Database />}
          title="个性化反馈环"
          flow="查询 / 点击 → 偏好提取 → PostgreSQL → 下一轮 Context"
          detail="记忆只改变排序与解释，不修改供应商价格，并允许用户查看和编辑。"
        />
        <FeedbackLoop
          icon={<Radar />}
          title="质量反馈环"
          flow="LangSmith Trace → Bad Case → 规则 / Prompt / Provider → 回归测试"
          detail="错误能定位到模型、参数、数据源或映射层，每次修复都有可验证出口。"
        />
      </div>
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

function TrustPoint({ icon, text }: { icon: React.ReactElement; text: string }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-brand-text/5 bg-white px-4 py-3 text-base font-semibold text-brand-muted shadow-sm [&>svg]:h-5 [&>svg]:w-5 [&>svg]:text-green-600">
      {icon}{text}
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

function ArchitectureBand({ icon, title, detail }: { icon: React.ReactElement; title: string; detail: string }) {
  return (
    <div className="grid grid-cols-[2.5rem_minmax(0,1fr)] gap-3 rounded-[24px] border border-brand-text/5 bg-white p-4 shadow-sm">
      <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-brand-orange/10 text-brand-orange [&>svg]:h-5 [&>svg]:w-5">{icon}</div>
      <div>
        <h3 className="font-black">{title}</h3>
        <p className="mt-1 text-sm leading-6 text-brand-muted">{detail}</p>
      </div>
    </div>
  )
}

function FeedbackLoop({
  icon,
  title,
  flow,
  detail,
}: {
  icon: React.ReactElement
  title: string
  flow: string
  detail: string
}) {
  return (
    <div className="grid grid-cols-[2.75rem_minmax(0,1fr)] gap-3 rounded-[24px] border border-brand-orange/10 bg-brand-orange/5 p-4">
      <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-brand-orange text-white [&>svg]:h-5 [&>svg]:w-5">{icon}</div>
      <div>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h3 className="font-black">{title}</h3>
          <span className="text-xs font-bold text-brand-orange">{flow}</span>
        </div>
        <p className="mt-1 text-sm leading-6 text-brand-muted">{detail}</p>
      </div>
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
