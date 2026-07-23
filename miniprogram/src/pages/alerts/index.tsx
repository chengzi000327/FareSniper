import { Button, Text, View } from '@tarojs/components'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import { useCallback, useState } from 'react'

import { enableWechatNotification } from '../../services/alerts'
import { miniApi } from '../../services/api'
import type { AlertItem } from '../../types/api'
import './index.scss'

function statusLabel(alert: AlertItem) {
  if (alert.status === 'triggered') return '已达到目标价'
  if (alert.status === 'paused') return '已暂停'
  if (alert.status === 'cancelled') return '已取消'
  return '监控中'
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setAlerts(await miniApi.alerts())
    } catch {
      await Taro.showToast({
        title: '监控列表加载失败',
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

  const toggle = async (alert: AlertItem) => {
    const next = alert.status === 'paused' ? 'active' : 'paused'
    try {
      await miniApi.updateAlert(alert.id, next)
      await load()
      await Taro.showToast({
        title: next === 'active' ? '已继续监控' : '已暂停监控',
        icon: 'success',
      })
    } catch {
      await Taro.showToast({
        title: '操作失败，请稍后重试',
        icon: 'none',
      })
    }
  }

  const enableWechat = async (alert: AlertItem) => {
    try {
      if (await enableWechatNotification(alert.id)) {
        await load()
      }
    } catch {
      await Taro.showToast({
        title: '微信提醒开启失败',
        icon: 'none',
      })
    }
  }

  return (
    <View className="page-shell alerts-page">
      <Text className="page-title">价格监控</Text>
      <Text className="page-subtitle">
        Worker 会持续检查最新报价；达到目标价后通过你授权的微信服务通知提醒。
      </Text>

      <View className="alerts-page__summary card">
        <View>
          <Text className="alerts-page__summary-value">
            {alerts.filter((item) => item.status === 'active').length}
          </Text>
          <Text className="alerts-page__summary-label">正在监控</Text>
        </View>
        <View>
          <Text className="alerts-page__summary-value">
            {alerts.filter((item) => item.status === 'triggered').length}
          </Text>
          <Text className="alerts-page__summary-label">已经命中</Text>
        </View>
        <View>
          <Text className="alerts-page__summary-value">15分钟</Text>
          <Text className="alerts-page__summary-label">最快检查</Text>
        </View>
      </View>

      <Text className="section-title">我的航线</Text>
      {!loading && !alerts.length ? (
        <View className="card empty-state">
          <Text className="empty-title">还没有监控任务</Text>
          <Text className="empty-detail">
            在航班结果卡中点击“监控这个价格”即可创建。
          </Text>
        </View>
      ) : null}

      {alerts.map((alert) => (
        <View className="alert-card card" key={alert.id}>
          <View
            className="alert-card__main"
            onClick={() =>
              Taro.navigateTo({
                url: `/pages/alert-detail/index?alertId=${alert.id}`,
              })
            }
          >
            <View>
              <Text className="alert-card__route">
                {alert.origin} → {alert.destination}
              </Text>
              <Text className="alert-card__date">{alert.depart_date}</Text>
            </View>
            <View className="alert-card__target">
              <Text className="alert-card__target-label">目标总价</Text>
              <Text className="alert-card__target-value">
                ≤ ¥{alert.target_price}
              </Text>
            </View>
          </View>
          <View className="alert-card__latest">
            <View>
              <Text className="alert-card__latest-label">最新报价</Text>
              <Text className="alert-card__latest-value">
                {alert.latest_price ? `¥${alert.latest_price}` : '等待数据'}
              </Text>
            </View>
            <Text className="alert-card__status">{statusLabel(alert)}</Text>
          </View>
          {alert.status === 'active' || alert.status === 'paused' ? (
            <View className="alert-card__actions">
              {!['subscribed', 'queued', 'retrying'].includes(
                alert.notification_status,
              ) ? (
                <Button
                  className="secondary-button alert-card__button"
                  onClick={() => void enableWechat(alert)}
                >
                  开启微信提醒
                </Button>
              ) : null}
              <Button
                className="secondary-button alert-card__button"
                onClick={() => void toggle(alert)}
              >
                {alert.status === 'paused' ? '继续监控' : '暂停监控'}
              </Button>
            </View>
          ) : null}
        </View>
      ))}
    </View>
  )
}
