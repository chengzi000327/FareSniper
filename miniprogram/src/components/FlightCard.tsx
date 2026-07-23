import { Button, Text, View } from '@tarojs/components'

import type { DealCard } from '../types/api'
import './FlightCard.scss'

function money(value: number | null | undefined) {
  return value === null || value === undefined ? '待确认' : `¥${value}`
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
        <View>
          <Text className="flight-card__route">
            {deal.origin_city} → {deal.destination_city}
          </Text>
          <Text className="flight-card__meta">
            {deal.depart_date} · {deal.flight_no} {deal.airline}
          </Text>
        </View>
        <View className="flight-card__price">
          <Text className="flight-card__price-label">完整总价</Text>
          <Text className="flight-card__price-value">{money(price)}</Text>
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
            {deal.baggage_allowance || '以预订页为准'}
          </Text>
        </View>
      </View>

      <View className="flight-card__providers">
        <Text className="flight-card__provider-title">平台报价</Text>
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
        监控这个价格
      </Button>
    </View>
  )
}
