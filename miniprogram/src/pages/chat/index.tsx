import { Button, Input, ScrollView, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useCallback, useRef, useState } from 'react'

import { CompanionSetup } from '../../components/CompanionSetup'
import { FlightCard } from '../../components/FlightCard'
import { submitPriceAlert } from '../../services/alerts'
import { miniApi } from '../../services/api'
import type {
  CompanionProfile,
  DealCard,
  MemoryResponse,
  SearchResponse,
} from '../../types/api'
import {
  companionFromMemory,
  hasCompanion,
} from '../../utils/companion'
import './index.scss'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  deals?: DealCard[]
}

function answerFromSearch(response: SearchResponse) {
  const deals = response.deals || []
  if (!deals.length) {
    return (
      response.recommendation?.text ||
      response.fallback?.reason ||
      '我还需要更多信息才能开始搜索。'
    )
  }
  const best = deals[0]
  const bestPrice = best.total_price ?? best.base_price
  const priceKind = best.total_price !== null ? '完整总价' : '平台展示价'
  const headline =
    typeof bestPrice === 'number'
      ? `已找到 ${deals.length} 个可核验航班。综合你的条件，最合适的是 ${best.flight_no}，${priceKind} ¥${bestPrice}，来自${best.platform}；下方只展示这一张推荐卡。`
      : `已找到 ${deals.length} 个可核验航班。综合你的条件，最合适的是 ${best.flight_no}；下方只展示这一张推荐卡。`
  const list = deals
    .map((deal, index) => {
      const price = deal.total_price ?? deal.base_price
      const routeKind =
        deal.stops === 0 ? '直飞' : `${deal.stops}次中转`
      return `${index + 1}. ${deal.flight_no} ${deal.airline}｜${deal.depart_time}→${deal.arrive_time}｜${routeKind}｜${deal.platform}｜${
        typeof price === 'number' ? `¥${price}` : '价格待确认'
      }`
    })
    .join('\n')
  return `${headline}\n\n全部航班\n${list}`
}

export default function ChatPage() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedDeal, setSelectedDeal] = useState<DealCard | null>(null)
  const [targetPrice, setTargetPrice] = useState('')
  const [savingAlert, setSavingAlert] = useState(false)
  const [memory, setMemory] = useState<MemoryResponse | null>(null)
  const [choosingCompanion, setChoosingCompanion] = useState(false)
  const sessionId = useRef<string | null>(null)
  const pendingQueryRef = useRef('')

  const sendQuery = useCallback(
    async (rawQuery?: string) => {
      const query = (rawQuery ?? input).trim()
      if (!query || loading) return
      setInput('')
      setLoading(true)
      const requestId = Date.now()
      setMessages((current) => [
        ...current,
        {
          id: `user_${requestId}`,
          role: 'user',
          text: query,
        },
      ])
      try {
        const response = await miniApi.search(query, sessionId.current)
        sessionId.current = response.session_id
        const answer = answerFromSearch(response)
        setMessages((current) => [
          ...current,
          {
            id: `assistant_${requestId}`,
            role: 'assistant',
            text: answer,
            deals: response.deals?.slice(0, 1) || [],
          },
        ])
      } catch {
        setMessages((current) => [
          ...current,
          {
            id: `error_${requestId}`,
            role: 'assistant',
            text: '这次搜索没有成功，请稍后重试。',
          },
        ])
      } finally {
        setLoading(false)
      }
    },
    [input, loading],
  )

  useDidShow(() => {
    void (async () => {
      try {
        const nextMemory = await miniApi.memory()
        setMemory(nextMemory)
        const forceChoose =
          Taro.getStorageSync<boolean>('fs_choose_companion') === true
        if (forceChoose) Taro.removeStorageSync('fs_choose_companion')
        const shouldChoose = forceChoose || !hasCompanion(nextMemory.memories)
        setChoosingCompanion(shouldChoose)
        if (shouldChoose) {
          await Taro.hideTabBar({ animation: false })
        } else {
          await Taro.showTabBar({ animation: false })
        }
      } catch {
        setMemory({ memories: [], query_history: [] })
      }

      const pending = Taro.getStorageSync<string>('fs_pending_query')
      if (pending && pending !== pendingQueryRef.current) {
        pendingQueryRef.current = pending
        Taro.removeStorageSync('fs_pending_query')
        await sendQuery(pending)
      }
    })()
  })

  const companion = companionFromMemory(memory?.memories || [])
  const isWelcome = !messages.length && !loading

  const companionSaved = async (profile: CompanionProfile) => {
    setMemory((current) => ({
      memories: [
        {
          field: 'companion_profile',
          value: profile,
          label: '旅伴档案',
          value_display: profile.name,
          source: 'manual',
        },
        ...(current?.memories || []).filter(
          (item) => item.field !== 'companion_profile',
        ),
      ],
      query_history: current?.query_history || [],
    }))
    setChoosingCompanion(false)
    await Taro.showTabBar({ animation: false })
  }

  const openAlertSetup = (deal: DealCard) => {
    const currentPrice = deal.total_price ?? deal.base_price
    setSelectedDeal(deal)
    setTargetPrice(
      currentPrice === null || currentPrice === undefined
        ? ''
        : String(Math.round(currentPrice)),
    )
  }

  const confirmAlert = async () => {
    if (!selectedDeal || savingAlert) return
    const parsedPrice = Number(targetPrice)
    if (!Number.isInteger(parsedPrice) || parsedPrice <= 0) {
      await Taro.showToast({ title: '请输入正确的目标价', icon: 'none' })
      return
    }
    setSavingAlert(true)
    try {
      await submitPriceAlert(selectedDeal, parsedPrice)
      setSelectedDeal(null)
    } catch {
      await Taro.showToast({ title: '监控暂时没有创建成功', icon: 'none' })
    } finally {
      setSavingAlert(false)
    }
  }

  return (
    <View className="chat-page">
      <ScrollView className="chat-page__scroll" scrollY>
        <View className="chat-page__content">
          <View className="chat-page__header">
            <View>
              <Text className="chat-page__online">
                你的机票发现与出行陪伴 AGENT
              </Text>
              <Text className="chat-page__title">对话空间</Text>
            </View>
          </View>

          {isWelcome ? (
            <View className="chat-page__welcome">
              <Text className="chat-page__welcome-kicker">
                ✦　{companion.name}在这里
              </Text>
              <Text className="chat-page__welcome-title">先说一个想法就好</Text>
              <Text className="chat-page__welcome-detail">
                不必一次把条件说全。我会接着当前对话，只追问真正缺少的内容。
              </Text>
              <View className="chat-page__suggestions">
                {[
                  {
                    icon: '✈',
                    title: '想去一个地方',
                    detail: '例如：下周末上海去厦门',
                    query: '下周末上海去厦门',
                  },
                  {
                    icon: '⌖',
                    title: '看看近期特价',
                    detail: '从真实推荐里发现下一程',
                    query: '帮我看看最近有什么值得关注的特价机票',
                  },
                  {
                    icon: '◷',
                    title: '接着最近查询',
                    detail: '继续补充日期、预算和行李',
                    query:
                      memory?.query_history[0] &&
                      typeof memory.query_history[0].query === 'object'
                        ? memory.query_history[0].query.text ||
                          '继续我最近的机票查询'
                        : '继续我最近的机票查询',
                  },
                ].map((item) => (
                  <Button
                    key={item.title}
                    onClick={() => void sendQuery(item.query)}
                  >
                    <Text className="chat-page__starter-icon">{item.icon}</Text>
                    <View className="chat-page__starter-copy">
                      <Text>{item.title}</Text>
                      <Text>{item.detail}</Text>
                    </View>
                    <Text className="chat-page__starter-arrow">›</Text>
                  </Button>
                ))}
              </View>
              <View className="chat-page__promise">
                <Text />
                <Text>只展示可核验的真实结果</Text>
                <Text />
              </View>
            </View>
          ) : null}

          <View className="chat-page__messages">
            {messages.map((message) => (
              <View className="chat-turn" key={message.id}>
                <View
                  className={`chat-bubble chat-bubble--${message.role}`}
                >
                  <Text>{message.text}</Text>
                </View>
                {message.deals?.length ? (
                  <View className="chat-page__deals">
                    <Text className="section-title">可核验航班</Text>
                    {message.deals.map((deal) => (
                      <FlightCard
                        deal={deal}
                        key={deal.id}
                        onMonitor={openAlertSetup}
                      />
                    ))}
                  </View>
                ) : null}
              </View>
            ))}
            {loading ? (
              <View className="chat-bubble chat-bubble--assistant search-progress">
                <View className="search-progress__radar">
                  <View className="search-progress__radar-ring" />
                  <View className="search-progress__radar-sweep" />
                  <View className="search-progress__radar-dot" />
                </View>
                <Text className="search-progress__title">
                  正在为您深度扫描全网特价资源...
                </Text>
              </View>
            ) : null}
          </View>

          <View className="chat-page__composer chat-page__composer--fixed">
            <Input
              className="chat-page__input"
              confirmType="send"
              placeholder="补充目的地、日期或预算…"
              value={input}
              onInput={(event) => setInput(event.detail.value)}
              onConfirm={() => void sendQuery()}
            />
            <Button
              className="chat-page__send"
              disabled={!input.trim() || loading}
              onClick={() => void sendQuery()}
            >
              ➤
            </Button>
          </View>
        </View>
      </ScrollView>

      {selectedDeal ? (
        <View
          className="alert-sheet__backdrop"
          onClick={() => !savingAlert && setSelectedDeal(null)}
        >
          <View
            className="alert-sheet"
            onClick={(event) => event.stopPropagation()}
          >
            <View className="alert-sheet__handle" />
            <Text className="alert-sheet__title">设置目标总价</Text>
            <Text className="alert-sheet__route">
              {selectedDeal.origin_city} → {selectedDeal.destination_city} ·{' '}
              {selectedDeal.depart_date}
            </Text>
            <View className="alert-sheet__price-input">
              <Text>¥</Text>
              <Input
                autoFocus
                type="number"
                value={targetPrice}
                onInput={(event) => setTargetPrice(event.detail.value)}
              />
            </View>
            <Text className="alert-sheet__hint">
              当完整总价不高于目标价时提醒你。微信订阅授权只会在确认后弹出。
            </Text>
            <View className="alert-sheet__actions">
              <Button
                className="alert-sheet__cancel"
                disabled={savingAlert}
                onClick={() => setSelectedDeal(null)}
              >
                取消
              </Button>
              <Button
                className="primary-button alert-sheet__confirm"
                disabled={savingAlert}
                onClick={() => void confirmAlert()}
              >
                {savingAlert ? '正在创建…' : '确认监控'}
              </Button>
            </View>
          </View>
        </View>
      ) : null}

      {choosingCompanion && memory ? (
        <CompanionSetup
          current={
            hasCompanion(memory.memories)
              ? companionFromMemory(memory.memories)
              : null
          }
          onSaved={(profile) => void companionSaved(profile)}
          onCancel={
            hasCompanion(memory.memories)
              ? () => {
                  setChoosingCompanion(false)
                  void Taro.showTabBar({ animation: false })
                }
              : undefined
          }
        />
      ) : null}
    </View>
  )
}
