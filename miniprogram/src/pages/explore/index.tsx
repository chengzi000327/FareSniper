import { Button, Image, Text, View } from '@tarojs/components'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import { useCallback, useState } from 'react'

import { miniApi } from '../../services/api'
import type { RecommendationCard } from '../../types/api'
import './index.scss'

const ASSET_BASE =
  process.env.TARO_APP_ASSET_BASE_URL ||
  'https://frontend-production-9c2c.up.railway.app'

const DESTINATION_IMAGE: Record<string, string> = {
  三亚: `${ASSET_BASE}/images/destinations/SYX.jpg`,
  厦门: `${ASSET_BASE}/images/destinations/XMN.jpg`,
  上海: `${ASSET_BASE}/images/destinations/SHA.jpg`,
  成都: `${ASSET_BASE}/images/destinations/CTU.jpg`,
}

function destinationFromTitle(title = '') {
  const parts = title.split('→')
  return parts[parts.length - 1]?.trim() || ''
}

export default function ExplorePage() {
  const [cards, setCards] = useState<RecommendationCard[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setCards(await miniApi.recommendations())
    } catch {
      await Taro.showToast({
        title: '推荐暂时没有加载出来',
        icon: 'none',
      })
    } finally {
      setLoading(false)
      Taro.stopPullDownRefresh()
    }
  }, [])

  useDidShow(() => {
    void load()
  })
  usePullDownRefresh(() => {
    void load()
  })

  const openChat = (query: string) => {
    Taro.switchTab({
      url: '/pages/chat/index',
      success: () => {
        Taro.setStorageSync('fs_pending_query', query)
      },
    })
  }

  return (
    <View className="page-shell explore-page">
      <View className="explore-page__brand">
        <View className="explore-page__mark">✈</View>
        <View>
          <Text className="page-title">今天想去哪里</Text>
          <Text className="page-subtitle">
            结合你的预算、时间和行李要求，寻找真正适合你的特价。
          </Text>
        </View>
      </View>

      <Button
        className="explore-page__search"
        onClick={() => openChat('帮我看看最近有哪些值得去的特价航线')}
      >
        <Text>输入目的地、日期或预算</Text>
        <Text className="explore-page__search-action">开始搜索</Text>
      </Button>

      <Text className="section-title">为你发现</Text>
      {loading ? (
        <View className="card empty-state">
          <Text className="empty-title">正在整理适合你的航线</Text>
          <Text className="empty-detail">
            会优先考虑完整总价，而不是只看票面数字。
          </Text>
        </View>
      ) : null}

      <View className="explore-page__grid">
        {cards.map((card) => {
          const destination = destinationFromTitle(card.title)
          return (
            <View
              className="explore-card"
              key={card.id || card.title}
              onClick={() =>
                openChat(card.query_hint || `搜索${card.title}的机票`)
              }
            >
              <Image
                className="explore-card__image"
                mode="aspectFill"
                src={
                  DESTINATION_IMAGE[destination] ||
                  `${ASSET_BASE}/images/destinations/SYX.jpg`
                }
              />
              <View className="explore-card__shade" />
              <View className="explore-card__content">
                <Text className="explore-card__title">{card.title}</Text>
                <Text className="explore-card__reason">{card.reason}</Text>
                <View className="explore-card__tags">
                  {(card.tags || []).slice(0, 2).map((tag) => (
                    <Text className="explore-card__tag" key={tag}>
                      {tag}
                    </Text>
                  ))}
                </View>
              </View>
            </View>
          )
        })}
      </View>
    </View>
  )
}
