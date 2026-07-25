import { Button, Text, View } from '@tarojs/components'

import type { DealCard } from '../types/api'
import './FlightCard.scss'

function money(value: number | null | undefined) {
  return value === null || value === undefined ? '待确认' : `¥${value}`
}

function priceLabel(deal: DealCard) {
  return deal.total_price === null ? '平台展示价' : '完整总价'
}

export function FlightCard({
  deal,
  onMonitor,
}: {
  deal: DealCard
  onMonitor: (deal: DealCard) => void
}) {
  const price = deal.total_price ?? deal.base_price ?? null
  return (
    <View className="flight-card card">
      <View className="flight-card__header">
        <View className="flight-card__identity">
          <View className="flight-card__plane">✈</View>
          <View>
            <Text className="flight-card__route">
              {deal.origin_city} → {deal.destination_city}
            </Text>
            <Text className="flight-card__meta">
              {deal.depart_date} · {deal.flight_no} {deal.airline}
            </Text>
          </View>
        </View>
        <View className="flight-card__price">
          <Text className="flight-card__price-label">{priceLabel(deal)}</Text>
          <Text className="flight-card__price-value">{money(price)}</Text>
        </View>
      </View>

      <View className="flight-card__facts">
        <View>
          <Text className="flight-card__fact-label">票价</Text>
          <Text className="flight-card__fact-value">
            {money(deal.base_price)}
          </Text>
        </View>
        <View>
          <Text className="flight-card__fact-label">机建燃油</Text>
          <Text className="flight-card__fact-value">{money(deal.tax)}</Text>
        </View>
        <View>
          <Text className="flight-card__fact-label">行李额</Text>
          <Text className="flight-card__fact-value">
            {deal.baggage_allowance || '平台未返回'}
          </Text>
        </View>
        <View className="flight-card__total">
          <Text className="flight-card__fact-label">{priceLabel(deal)}</Text>
          <Text className="flight-card__total-value">{money(price)}</Text>
        </View>
      </View>

      <View className="flight-card__schedule">
        <View>
          <Text className="flight-card__time">{deal.depart_time}</Text>
          <Text className="flight-card__airport">{deal.origin_code}</Text>
        </View>
        <View className="flight-card__line">
          <Text>{deal.stops === 0 ? '直飞' : `${deal.stops}次中转`}</Text>
        </View>
        <View className="flight-card__arrival">
          <Text className="flight-card__time">{deal.arrive_time}</Text>
          <Text className="flight-card__airport">
            {deal.destination_code}
          </Text>
        </View>
      </View>

      <View className="flight-card__notice">
        <View className="flight-card__notice-icon">✓</View>
        <Text>
          {deal.tax !== null && deal.baggage_allowance
            ? '费用拆解来自当前平台报价，预订前请再次核验。'
            : '平台未返回的费用保持未知，不由模型补全。'}
        </Text>
      </View>

      <View className="flight-card__providers">
        <View className="flight-card__provider-head">
          <View className="flight-card__provider-dot" />
          <Text className="flight-card__provider-title">多平台报价</Text>
        </View>
        {deal.prices.map((item) => (
          <View className="flight-card__provider" key={item.id}>
            <Text>{item.name}</Text>
            <Text className={item.lowest ? 'is-lowest' : ''}>
              {money(item.price)}
            </Text>
          </View>
        ))}
      </View>

      <Button
        className="primary-button flight-card__action"
        onClick={() => onMonitor(deal)}
      >
        监控价格
      </Button>
    </View>
  )
}
