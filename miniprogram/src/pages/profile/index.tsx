import { Text, View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'

import { ensureWechatSession, miniApi } from '../../services/api'
import type { MemoryResponse } from '../../types/api'
import './index.scss'

const FIELD_LABELS: Record<string, string> = {
  budget: '心理价位',
  budget_ceiling: '预算上限',
  frequent_cities: '常去城市',
  preferred_airlines: '偏好航司',
  constraints: '出行约束',
  travel_scenes: '出行场景',
}

const VALUE_LABELS: Record<string, string> = {
  direct_only: '只看直飞',
  avoid_redeye: '避开红眼航班',
  checked_baggage: '需要托运行李',
  carry_on_only: '只带随身行李',
}

function displayValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value
      .map((item) => VALUE_LABELS[String(item)] || String(item))
      .join('、')
  }
  return VALUE_LABELS[String(value)] || String(value)
}

export default function ProfilePage() {
  const [memory, setMemory] = useState<MemoryResponse | null>(null)
  const [userId, setUserId] = useState('')

  useDidShow(() => {
    void (async () => {
      try {
        await ensureWechatSession()
        setUserId(miniApi.userId())
        setMemory(await miniApi.memory())
      } catch {
        await Taro.showToast({
          title: '用户信息暂时没有加载出来',
          icon: 'none',
        })
      }
    })()
  })

  return (
    <View className="page-shell profile-page">
      <View className="profile-page__identity">
        <View className="profile-page__avatar">橙</View>
        <View>
          <Text className="page-title">我的 FareSniper</Text>
          <Text className="page-subtitle">
            {userId ? `微信账号已连接 · ${userId.slice(0, 12)}` : '正在连接微信账号'}
          </Text>
        </View>
      </View>

      <Text className="section-title">Agent 记住了什么</Text>
      <View className="profile-page__memories card">
        {memory?.memories.length ? (
          memory.memories.map((item) => (
            <View className="profile-memory" key={item.field}>
              <Text className="profile-memory__label">
                {FIELD_LABELS[item.field] || item.field}
              </Text>
              <Text className="profile-memory__value">
                {displayValue(item.value)}
              </Text>
            </View>
          ))
        ) : (
          <View className="empty-state">
            <Text className="empty-title">还没有形成稳定偏好</Text>
            <Text className="empty-detail">
              多完成几次搜索后，Agent 会逐步理解你的特价定义。
            </Text>
          </View>
        )}
      </View>

      <Text className="section-title">最近问过</Text>
      <View className="profile-page__history card">
        {memory?.query_history.slice(0, 5).map((item, index) => (
          <View className="profile-query" key={String(item.id || index)}>
            <Text>
              {item.query_text || item.query || '一次机票搜索'}
            </Text>
          </View>
        ))}
        {!memory?.query_history.length ? (
          <View className="empty-state">
            <Text className="empty-detail">搜索记录会显示在这里。</Text>
          </View>
        ) : null}
      </View>

      <View className="profile-page__notice">
        <Text className="profile-page__notice-title">关于微信提醒</Text>
        <Text className="profile-page__notice-detail">
          微信只会发送你主动订阅的价格监控消息；每条一次性订阅在成功发送后即被消费。
        </Text>
      </View>
    </View>
  )
}
