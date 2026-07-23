import Taro from '@tarojs/taro'

import { miniApi } from './api'
import type { DealCard } from '../types/api'

const TEMPLATE_ID =
  process.env.TARO_APP_WECHAT_PRICE_ALERT_TEMPLATE_ID || ''

function bestPrice(deal: DealCard): number | null {
  return deal.total_price ?? deal.base_price ?? null
}

async function requestWechatNotification(): Promise<boolean> {
  if (miniApi.isMock()) return true
  if (!TEMPLATE_ID) {
    await Taro.showToast({
      title: '微信提醒模板尚未配置',
      icon: 'none',
    })
    return false
  }
  try {
    const result = await Taro.requestSubscribeMessage({
      tmplIds: [TEMPLATE_ID],
    } as Taro.requestSubscribeMessage.Option)
    const subscription =
      result as Taro.requestSubscribeMessage.SuccessCallbackResult
    return subscription[TEMPLATE_ID] === 'accept'
  } catch {
    return false
  }
}

export async function submitPriceAlert(
  deal: DealCard,
  targetPrice: number,
): Promise<void> {
  const price = bestPrice(deal)
  if (price === null || deal.currency !== 'CNY') {
    await Taro.showToast({
      title: '这条报价暂不支持监控',
      icon: 'none',
    })
    return
  }
  if (!Number.isInteger(targetPrice) || targetPrice <= 0) {
    await Taro.showToast({
      title: '请输入正确的目标价',
      icon: 'none',
    })
    return
  }

  const notifyWechat = await requestWechatNotification()

  const created = await miniApi.createAlert({
    origin: deal.origin_code,
    destination: deal.destination_code,
    depart_date: deal.depart_date,
    target_price: targetPrice,
    current_price: Math.round(price),
    currency: deal.currency,
    notify_wechat: notifyWechat,
  })

  await Taro.showModal({
    title: '监控已创建',
    content:
      created.wechat_notification === 'subscribed'
        ? '达到目标价后会通过微信服务通知提醒你。'
        : '监控会继续运行；你可以在监控页再次开启微信提醒。',
    showCancel: false,
  })
}

export async function enableWechatNotification(
  alertId: string,
): Promise<boolean> {
  if (!(await requestWechatNotification())) {
    await Taro.showToast({
      title: '尚未获得微信提醒授权',
      icon: 'none',
    })
    return false
  }
  await miniApi.subscribeAlert(alertId)
  await Taro.showToast({
    title: '微信提醒已开启',
    icon: 'success',
  })
  return true
}
