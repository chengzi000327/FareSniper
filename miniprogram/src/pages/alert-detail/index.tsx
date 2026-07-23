import { Button, Text, View } from '@tarojs/components'
import Taro, { useLoad } from '@tarojs/taro'
import { useState } from 'react'

import { miniApi } from '../../services/api'
import type { AlertItem } from '../../types/api'
import './index.scss'

function notificationLabel(status: string) {
  if (status === 'subscribed') return '已订阅'
  if (status === 'queued') return '等待发送'
  if (status === 'retrying') return '发送重试中'
  if (status === 'sent') return '已发送'
  if (status === 'failed') return '发送失败'
  return '未开启'
}

function alertStatusLabel(status: string) {
  if (status === 'active') return '监控中'
  if (status === 'paused') return '已暂停'
  if (status === 'triggered') return '已达到目标价'
  if (status === 'cancelled') return '已取消'
  return status
}

export default function AlertDetailPage() {
  const [alert, setAlert] = useState<AlertItem | null>(null)

  useLoad((options) => {
    const alertId = String(options.alertId || '')
    if (!alertId) return
    void miniApi
      .alert(alertId)
      .then(setAlert)
      .catch(() =>
        Taro.showToast({
          title: '监控详情加载失败',
          icon: 'none',
        }),
      )
  })

  if (!alert) {
    return (
      <View className="page-shell">
        <View className="card empty-state">
          <Text className="empty-title">正在读取监控详情</Text>
        </View>
      </View>
    )
  }

  const cancel = async () => {
    const result = await Taro.showModal({
      title: '取消这条监控？',
      content: '取消后不会再检查价格，也不会发送微信提醒。',
    })
    if (!result.confirm) return
    try {
      await miniApi.updateAlert(alert.id, 'cancelled')
      setAlert({ ...alert, status: 'cancelled' })
      await Taro.showToast({
        title: '监控已取消',
        icon: 'success',
      })
    } catch {
      await Taro.showToast({
        title: '取消失败，请稍后重试',
        icon: 'none',
      })
    }
  }

  return (
    <View className="page-shell detail-page">
      <View className="detail-page__hero card">
        <Text className="detail-page__eyebrow">价格监控</Text>
        <Text className="detail-page__route">
          {alert.origin} → {alert.destination}
        </Text>
        <Text className="detail-page__date">{alert.depart_date}</Text>

        <View className="detail-page__prices">
          <View>
            <Text className="detail-page__price-label">最新总价</Text>
            <Text className="detail-page__price-value">
              {alert.latest_price ? `¥${alert.latest_price}` : '等待数据'}
            </Text>
          </View>
          <View className="detail-page__target">
            <Text className="detail-page__price-label">目标总价</Text>
            <Text className="detail-page__target-value">
              ¥{alert.target_price}
            </Text>
          </View>
        </View>
      </View>

      <View className="detail-page__facts card">
        <View className="detail-fact">
          <Text>报价平台</Text>
          <Text>{alert.latest_provider || '等待报价'}</Text>
        </View>
        <View className="detail-fact">
          <Text>最近检查</Text>
          <Text>
            {alert.latest_quote_at
              ? new Date(alert.latest_quote_at).toLocaleString()
              : '尚未检查'}
          </Text>
        </View>
        <View className="detail-fact">
          <Text>微信通知</Text>
          <Text>{notificationLabel(alert.notification_status)}</Text>
        </View>
        <View className="detail-fact">
          <Text>监控状态</Text>
          <Text>{alertStatusLabel(alert.status)}</Text>
        </View>
      </View>

      {alert.status !== 'cancelled' ? (
        <Button
          className="secondary-button detail-page__cancel"
          onClick={() => void cancel()}
        >
          取消监控
        </Button>
      ) : null}
    </View>
  )
}
