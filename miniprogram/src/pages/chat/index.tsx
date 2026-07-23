import { Button, Input, ScrollView, Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useRef, useState } from 'react'

import { FlightCard } from '../../components/FlightCard'
import { submitPriceAlert } from '../../services/alerts'
import { miniApi } from '../../services/api'
import type { DealCard } from '../../types/api'
import './index.scss'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
}

export default function ChatPage() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      text: '告诉我出发地、目的地、日期和预算。我会在要素完整后再开始查票。',
    },
  ])
  const [deals, setDeals] = useState<DealCard[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedDeal, setSelectedDeal] = useState<DealCard | null>(null)
  const [targetPrice, setTargetPrice] = useState('')
  const sessionId = useRef<string | null>(null)

  useDidShow(() => {
    const pending = Taro.getStorageSync<string>('fs_pending_query')
    if (pending) {
      setInput(pending)
      Taro.removeStorageSync('fs_pending_query')
    }
  })

  const send = async () => {
    const query = input.trim()
    if (!query || loading) return
    setInput('')
    setLoading(true)
    setMessages((current) => [
      ...current,
      {
        id: `user_${Date.now()}`,
        role: 'user',
        text: query,
      },
    ])
    try {
      const response = await miniApi.search(query, sessionId.current)
      sessionId.current = response.session_id
      setDeals(response.deals || [])
      const answer =
        response.recommendation?.text ||
        response.fallback?.reason ||
        '我还需要更多信息才能开始搜索。'
      setMessages((current) => [
        ...current,
        {
          id: `assistant_${Date.now()}`,
          role: 'assistant',
          text: answer,
        },
      ])
    } catch {
      setMessages((current) => [
        ...current,
        {
          id: `error_${Date.now()}`,
          role: 'assistant',
          text: '这次搜索没有成功，请稍后重试。',
        },
      ])
    } finally {
      setLoading(false)
    }
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
    if (!selectedDeal) return
    const parsedPrice = Number(targetPrice)
    if (!Number.isInteger(parsedPrice) || parsedPrice <= 0) {
      await Taro.showToast({ title: '请输入正确的目标价', icon: 'none' })
      return
    }
    await submitPriceAlert(selectedDeal, parsedPrice)
    setSelectedDeal(null)
  }

  return (
    <View className="chat-page">
      <ScrollView className="chat-page__scroll" scrollY>
        <View className="chat-page__content">
          <Text className="page-title">对话空间</Text>
          <Text className="page-subtitle">
            我会先确认城市、日期和预算，再聚合各平台的完整总价。
          </Text>

          <View className="chat-page__messages">
            {messages.map((message) => (
              <View
                className={`chat-bubble chat-bubble--${message.role}`}
                key={message.id}
              >
                <Text>{message.text}</Text>
              </View>
            ))}
            {loading ? (
              <View className="chat-bubble chat-bubble--assistant">
                <Text>正在获取飞猪、携程等平台的报价…</Text>
              </View>
            ) : null}
          </View>

          {deals.length ? (
            <View className="chat-page__deals">
              <Text className="section-title">搜索结果</Text>
              {deals.map((deal) => (
                <FlightCard
                  deal={deal}
                  key={deal.id}
                  onMonitor={openAlertSetup}
                />
              ))}
            </View>
          ) : null}
        </View>
      </ScrollView>

      <View className="chat-page__composer">
        <Input
          className="chat-page__input"
          confirmType="send"
          placeholder="例如：下周五北京去三亚，预算800"
          value={input}
          onInput={(event) => setInput(event.detail.value)}
          onConfirm={() => void send()}
        />
        <Button
          className="chat-page__send"
          disabled={!input.trim() || loading}
          onClick={() => void send()}
        >
          发送
        </Button>
      </View>

      {selectedDeal ? (
        <View
          className="alert-sheet__backdrop"
          onClick={() => setSelectedDeal(null)}
        >
          <View className="alert-sheet" onClick={(event) => event.stopPropagation()}>
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
                onClick={() => setSelectedDeal(null)}
              >
                取消
              </Button>
              <Button
                className="primary-button alert-sheet__confirm"
                onClick={() => void confirmAlert()}
              >
                确认监控
              </Button>
            </View>
          </View>
        </View>
      ) : null}
    </View>
  )
}
