import { Button, Image, Input, Text, View } from '@tarojs/components'
import Taro, {
  useDidShow,
  usePullDownRefresh,
  useReachBottom,
} from '@tarojs/taro'
import { useCallback, useRef, useState } from 'react'

import { Companion } from '../../components/Companion'
import { miniApi } from '../../services/api'
import type { MemoryResponse, RecommendationCard } from '../../types/api'
import {
  companionFromMemory,
  explicitIdeaCount,
  preferenceCount,
} from '../../utils/companion'
import canImage from '../../assets/destinations/CAN.jpg'
import ctuImage from '../../assets/destinations/CTU.jpg'
import shaImage from '../../assets/destinations/SHA.jpg'
import syxImage from '../../assets/destinations/SYX.jpg'
import xmnImage from '../../assets/destinations/XMN.jpg'
import './index.scss'

const PAGE_SIZE = 10

const DESTINATION_IMAGE: Record<string, string> = {
  三亚: syxImage,
  厦门: xmnImage,
  上海: shaImage,
  成都: ctuImage,
  广州: canImage,
}

function destinationFromTitle(title = '') {
  const parts = title.split('→')
  return parts[parts.length - 1]?.trim() || ''
}

function recommendationKey(card: RecommendationCard) {
  return card.id || card.title?.trim() || card.query_hint?.trim() || ''
}

function mergeRecommendationCards(
  current: RecommendationCard[],
  incoming: RecommendationCard[],
) {
  const seen = new Set(
    current.map(recommendationKey).filter((key) => Boolean(key)),
  )
  return [
    ...current,
    ...incoming.filter((card) => {
      const key = recommendationKey(card)
      if (!key || seen.has(key)) return false
      seen.add(key)
      return true
    }),
  ]
}

function fallbackVariant(value: string) {
  return [...value].reduce((sum, character) => sum + character.charCodeAt(0), 0) % 5
}

export default function ExplorePage() {
  const [cards, setCards] = useState<RecommendationCard[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [blindPick, setBlindPick] = useState<RecommendationCard | null>(null)
  const [memory, setMemory] = useState<MemoryResponse>({
    memories: [],
    query_history: [],
  })
  const [hasMore, setHasMore] = useState(false)
  const [nextOffset, setNextOffset] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)
  const [loadMoreError, setLoadMoreError] = useState(false)
  const loadingMoreRef = useRef(false)
  const feedGenerationRef = useRef(0)
  const initializedRef = useRef(false)

  const load = useCallback(async () => {
    const generation = feedGenerationRef.current + 1
    feedGenerationRef.current = generation
    loadingMoreRef.current = false
    setLoading(true)
    setLoadingMore(false)
    setLoadMoreError(false)
    try {
      const [page, nextMemory] = await Promise.all([
        miniApi.recommendationPage(PAGE_SIZE, 0),
        miniApi.memory(),
      ])
      if (generation !== feedGenerationRef.current) return
      setCards(mergeRecommendationCards([], page.cards))
      setHasMore(Boolean(page.has_more))
      setNextOffset(page.next_offset ?? page.cards.length)
      setMemory(nextMemory)
      initializedRef.current = true
    } catch {
      if (generation !== feedGenerationRef.current) return
      initializedRef.current = false
      await Taro.showToast({
        title: '推荐暂时没有加载出来',
        icon: 'none',
      })
    } finally {
      setLoading(false)
      Taro.stopPullDownRefresh()
    }
  }, [])

  const loadMore = useCallback(async () => {
    if (!hasMore || loadingMoreRef.current) return
    const generation = feedGenerationRef.current
    const offset = nextOffset
    loadingMoreRef.current = true
    setLoadingMore(true)
    setLoadMoreError(false)
    try {
      const page = await miniApi.recommendationPage(PAGE_SIZE, offset)
      if (generation !== feedGenerationRef.current) return
      setCards((current) => mergeRecommendationCards(current, page.cards))
      setHasMore(Boolean(page.has_more))
      setNextOffset(page.next_offset ?? offset + page.cards.length)
    } catch {
      if (generation === feedGenerationRef.current) {
        setLoadMoreError(true)
      }
    } finally {
      if (generation === feedGenerationRef.current) {
        loadingMoreRef.current = false
        setLoadingMore(false)
      }
    }
  }, [hasMore, nextOffset])

  useDidShow(() => {
    if (!initializedRef.current) {
      initializedRef.current = true
      void load()
    }
  })
  usePullDownRefresh(() => {
    void load()
  })
  useReachBottom(() => {
    void loadMore()
  })

  const openChat = (query: string) => {
    Taro.setStorageSync('fs_pending_query', query)
    Taro.switchTab({
      url: '/pages/chat/index',
    })
  }

  const companion = companionFromMemory(memory.memories)
  const columns = [
    cards.filter((_, index) => index % 2 === 0),
    cards.filter((_, index) => index % 2 === 1),
  ]

  return (
    <View className="page-shell explore-page">
      <View className="explore-page__header">
        <View>
          <Text className="eyebrow">你的机票发现与出行陪伴 AGENT</Text>
          <Text className="page-title">探索灵感</Text>
        </View>
      </View>

      <View className="explore-page__companion companion-card">
        <Companion
          kind={companion.kind}
          className="explore-page__companion-avatar"
        />
        <View className="explore-page__companion-copy">
          <Text className="explore-page__companion-kicker">
            和 {companion.name} 一起逛逛
          </Text>
          <Text className="explore-page__companion-title">从真实推荐里发现下一程</Text>
          <Text className="explore-page__companion-stats">
            {preferenceCount(memory.memories)} 项偏好　·　
            {explicitIdeaCount(memory.memories)} 个关注　·　
            {memory.query_history.length} 次查询
          </Text>
        </View>
      </View>

      <View className="explore-page__tools">
        <View className="explore-page__search">
          <Text className="explore-page__search-icon">⌕</Text>
          <Input className="explore-page__search-input" value={query} placeholder="说一个想去的地方" confirmType="send" onInput={(event) => setQuery(event.detail.value)} onConfirm={() => query.trim() && openChat(query.trim())} />
          <Button className="explore-page__send" disabled={!query.trim()} onClick={() => openChat(query.trim())}>➤</Button>
        </View>
        <Button className="explore-page__blind" disabled={!cards.length} onClick={() => setBlindPick(cards[Math.floor(Math.random() * cards.length)] || null)}>
          <Text className="explore-page__blind-icon">✦</Text>
          <Text className="explore-page__blind-text">抽取盲盒</Text>
        </Button>
      </View>

      {blindPick ? (
        <View className="explore-page__blind-result">
          <View><Text className="explore-page__blind-label">今天的盲盒目的地</Text><Text className="explore-page__blind-title">{blindPick.title}</Text></View>
          <Button onClick={() => openChat(blindPick.query_hint || `查询${blindPick.title}的机票`)}>去查票</Button>
        </View>
      ) : null}

      <View className="explore-page__section-head">
        <View><Text className="explore-page__real">⌖　真实推荐</Text><Text className="explore-page__section-title">为你发现</Text></View>
        <Text className="explore-page__more">向下继续发现</Text>
      </View>
      {loading ? (
        <View className="card empty-state">
          <Text className="empty-title">正在整理适合你的航线</Text>
          <Text className="empty-detail">
            会优先考虑完整总价，而不是只看票面数字。
          </Text>
        </View>
      ) : null}

      <View className="explore-page__grid">
        {columns.map((column, columnIndex) => (
          <View className="explore-page__column" key={columnIndex}>
            {column.map((card, itemIndex) => {
              const destination = destinationFromTitle(card.title)
              const image = DESTINATION_IMAGE[destination]
              return (
                <View
                  className={`explore-card explore-card--variant-${(itemIndex + columnIndex) % 3}`}
                  key={card.id || card.title}
                  onClick={() =>
                    openChat(card.query_hint || `搜索${card.title}的机票`)
                  }
                >
                  {image ? (
                    <Image
                      className="explore-card__image"
                      mode="aspectFill"
                      src={image}
                    />
                  ) : (
                    <View className="explore-card__image explore-card__image--fallback">
                      <View
                        className={`explore-card__fallback-color explore-card__fallback-color--${fallbackVariant(destination)}`}
                      >
                        <Text>{destination || '下一程'}</Text>
                      </View>
                    </View>
                  )}
                  <View className="explore-card__shade" />
                  <Text className="explore-card__title">{card.title}</Text>
                  <View className="explore-card__content">
                    <Text className="explore-card__price">
                      {card.preview_deal?.total_price
                        ? `¥${card.preview_deal.total_price}`
                        : '查询实时价格'}
                    </Text>
                    <Text className="explore-card__reason">
                      {card.reason || '进入对话获取最新可售结果'}
                    </Text>
                    <View className="explore-card__link">
                      <Text>查看实时航班</Text>
                      <Text>›</Text>
                    </View>
                  </View>
                </View>
              )
            })}
          </View>
        ))}
      </View>
      {!loading && cards.length ? (
        <View className="explore-page__feed-status">
          {loadingMore ? (
            <View className="explore-page__loading-more">
              <View className="explore-page__spinner" />
              <Text>正在发现更多真实目的地</Text>
            </View>
          ) : loadMoreError ? (
            <Button
              className="explore-page__retry"
              onClick={() => void loadMore()}
            >
              加载失败，点击重试
            </Button>
          ) : hasMore ? (
            <Text>继续下滑，自动发现更多</Text>
          ) : (
            <Text>本轮真实目的地已全部展示</Text>
          )}
        </View>
      ) : null}
    </View>
  )
}
