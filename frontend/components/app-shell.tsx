'use client'

import React from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowRight, Radar, Sparkles } from 'lucide-react'
import { MainLayout } from '@/components/main-layout'
import { DiscoveryCardContent } from '@/components/discovery-card-content'

export function AppShell() {
  const [view, setView] = React.useState<'landing' | 'app'>('landing')

  return (
    <div className="app-shell overflow-hidden bg-brand-bg text-brand-text selection:bg-brand-orange selection:text-white">
      <AnimatePresence mode="wait">
        {view === 'landing' ? (
          <motion.div
            key="landing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, y: -20 }}
            className="relative flex min-h-screen items-start justify-center px-4 pb-10 pt-24 sm:px-8 sm:pb-12 sm:pt-28 lg:items-center lg:px-12 lg:py-10 xl:px-20 2xl:px-36"
          >
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_75%_20%,rgba(255,138,61,0.12),transparent_22%),radial-gradient(circle_at_20%_85%,rgba(255,237,213,0.9),transparent_30%)]" />

            <div className="absolute left-4 right-4 top-5 flex max-w-[calc(100vw-2rem)] items-start gap-3 sm:left-8 sm:right-auto sm:top-7 sm:max-w-[80vw] sm:items-center">
              <div className="mt-1 h-3 w-3 shrink-0 rounded-full bg-brand-text sm:mt-0 sm:h-4 sm:w-4" />
              <div className="flex flex-col">
                <span className="text-sm font-bold tracking-tight sm:text-base lg:text-lg">
                  特价机票发现平台：懂你的航线才叫真特价。
                </span>
                <span className="text-[10px] uppercase tracking-[0.22em] text-brand-muted sm:text-xs sm:tracking-[0.3em]">
                  FareSniper: I remember your dreams, so I track your deals
                </span>
              </div>
            </div>

            <div className="relative z-10 grid w-full max-w-6xl gap-14 lg:grid-cols-[minmax(0,0.7fr)_minmax(0,1fr)] lg:items-center xl:max-w-7xl xl:gap-20">
              <motion.div
                initial={{ opacity: 0, x: -40 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.8, ease: 'easeOut' }}
                className="flex max-w-[34rem] flex-col items-start xl:max-w-[36rem]"
              >
                <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-brand-orange/20 bg-orange-50 px-4 py-2 text-[11px] font-bold text-brand-orange sm:px-5 sm:text-xs">
                  <Radar className="h-4 w-4 animate-pulse" />
                  <span className="leading-relaxed">携程、飞猪与国际航司/销售平台实时比价</span>
                </div>

                <h1 className="font-serif text-[clamp(3rem,12vw,4.2rem)] leading-[0.94] sm:text-[clamp(3.8rem,9vw,5rem)] lg:text-[clamp(2.9rem,4vw,4.8rem)] xl:text-[clamp(3.15rem,3.7vw,5rem)]">
                  <span className="block">发现特价，</span>
                  <span className="block italic text-brand-orange">遇见惊喜。</span>
                </h1>

                <p className="mt-8 max-w-[33rem] text-[15px] leading-8 text-brand-muted sm:text-base lg:text-[15px] xl:text-[17px]">
                  输入航线和未来日期后，系统会逐步展示各来源状态。价格、税费与行李规则以预订页为准。
                </p>

                <div className="mt-10 flex flex-col items-start gap-4">
                  <motion.button
                    onClick={() => setView('app')}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="group inline-flex items-center gap-3 rounded-2xl bg-brand-text px-7 py-4 text-base font-semibold text-white shadow-card transition hover:bg-brand-orange"
                  >
                    <Sparkles className="h-5 w-5" />
                    开启特价发现之旅
                  </motion.button>
                  <p className="text-sm leading-7 text-brand-muted">
                    携程、飞猪与国际航司/销售平台实时比价
                  </p>
                </div>

                <div className="mt-14 flex w-full flex-col items-start gap-5 border-t border-brand-text/10 pt-8 sm:flex-row sm:items-center">
                  <p className="text-sm leading-7 text-brand-muted">
                    来源可能返回实时结果、小时快照或暂时不可用状态
                  </p>
                </div>
              </motion.div>

              <div className="relative mx-auto flex min-h-[360px] w-full max-w-xl items-center justify-center sm:min-h-[420px] sm:max-w-2xl lg:min-h-[520px] lg:max-w-none lg:justify-end xl:min-h-[590px] xl:max-w-3xl xl:pt-20">
                <div className="absolute inset-0 rounded-full bg-brand-orange/10 blur-3xl" />
                <div className="absolute right-2 top-0 hidden items-center gap-3 text-[11px] tracking-[0.02em] text-brand-muted xl:flex">
                  <span>滑动或点击卡片查看更多发现</span>
                  <ArrowRight className="h-4 w-4" />
                </div>

                <motion.div
                  initial={{ opacity: 0, scale: 0.92, x: -20, rotate: -8 }}
                  animate={{ opacity: 1, scale: 1, x: 0, rotate: -4 }}
                  transition={{ duration: 0.8, delay: 0.2 }}
                  whileHover={{ rotate: -2, scale: 1.02, zIndex: 20 }}
                  className="absolute left-0 top-6 z-10 w-[92%] max-w-[32rem] overflow-hidden rounded-[28px] border border-brand-orange/10 bg-white shadow-[0_24px_80px_-24px_rgba(67,44,27,0.28)] sm:top-8 sm:w-[74%] lg:left-auto lg:right-[17%] lg:top-14 lg:w-[66%] xl:right-[19%] xl:top-16 xl:w-[62%] 2xl:right-[16%] 2xl:w-[64%]"
                >
                  <DiscoveryCardContent
                    from="上海"
                    to="三亚"
                    basePrice={null}
                    tax={null}
                    baggageFee={null}
                    hasBaggage={null}
                    platform="飞猪旅行"
                    recommendScore="--"
                    compact
                    prices={[
                      { name: '飞猪旅行', price: null, status: 'loading' },
                      { name: '携程旅行', price: null, status: 'queued' },
                    ]}
                  />
                </motion.div>

                <motion.div
                  initial={{ opacity: 0, scale: 0.92, x: 20, rotate: 8 }}
                  animate={{ opacity: 1, scale: 1, x: 0, rotate: 4 }}
                  transition={{ duration: 0.8, delay: 0.4 }}
                  whileHover={{ rotate: 2, scale: 1.02, zIndex: 20 }}
                  className="absolute bottom-0 right-0 w-[92%] max-w-[32rem] overflow-hidden rounded-[28px] border border-brand-orange/10 bg-white shadow-[0_24px_80px_-24px_rgba(67,44,27,0.28)] sm:w-[74%] lg:right-[2%] lg:bottom-1 lg:w-[66%] xl:right-[3%] xl:bottom-0 xl:w-[62%] 2xl:right-[4%] 2xl:w-[64%]"
                >
                  <DiscoveryCardContent
                    from="上海"
                    to="新加坡"
                    basePrice={null}
                    tax={null}
                    baggageFee={null}
                    hasBaggage={null}
                    platform="国际航司/销售平台"
                    recommendScore="--"
                    compact
                    prices={[
                      {
                        name: '国际航司/销售平台',
                        price: null,
                        status: 'loading',
                      },
                      { name: '飞猪旅行', price: null, status: 'empty' },
                    ]}
                  />
                </motion.div>
              </div>
            </div>
          </motion.div>
        ) : (
          <MainLayout key="app" onBack={() => setView('landing')} />
        )}
      </AnimatePresence>
    </div>
  )
}
