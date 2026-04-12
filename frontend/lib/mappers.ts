import type { DealCardDto } from './api'
import type { DiscoveryCardContentProps } from '@/components/discovery-card-content'

export function dealToCardProps(deal: DealCardDto): DiscoveryCardContentProps {
  return {
    from: deal.origin_city,
    to: deal.destination_city,
    date: deal.depart_date,
    basePrice: deal.price,
    tax: deal.tax,
    baggageFee: deal.baggage_fee,
    hasBaggage: deal.has_baggage,
    platform: deal.platform,
    recommendScore: deal.recommend_score || undefined,
    prices: deal.prices,
  }
}
