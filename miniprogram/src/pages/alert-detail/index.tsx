import { Button, Text, View } from '@tarojs/components'
import Taro, { useLoad } from '@tarojs/taro'
import { useState } from 'react'

import { miniApi } from '../../services/api'
import type { AlertItem } from '../../types/api'
import './index.scss'

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
    await miniApi.updateAlert(alert.id, 'cancelled')
    setAlert({ ...alert, status: 'cancelled' })
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
          <Text>
            {alert.notification_status === 'subscribed'
              ? '已订阅'
              : alert.notification_status === 'sent'
                ? '已发送'
                : alert.notification_status}
          </Text>
        </View>
        <View className="detail-fact">
          <Text>监控状态</Text>
          <Text>{alert.status}</Text>
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
