import type {
  AlertItem,
  DealCard,
  MemoryResponse,
  RecommendationCard,
  SearchResponse,
} from '../types/api'

export const MOCK_DEALS: DealCard[] = [
  {
    id: 'mock-cz6718',
    flight_no: 'CZ6718',
    platform: '飞猪',
    origin_city: '北京',
    origin_code: 'BJS',
    destination_city: '三亚',
    destination_code: 'SYX',
    depart_date: '2026-08-12',
    airline: '南方航空',
    depart_time: '08:30',
    arrive_time: '12:35',
    stops: 0,
    base_price: 560,
    tax: 100,
    baggage_allowance: '20KG',
    total_price: 660,
    currency: 'CNY',
    prices: [
      {
        id: 'fliggy',
        name: '飞猪',
        price: 660,
        currency: 'CNY',
        lowest: true,
        data_freshness: 'fresh',
      },
      {
        id: 'ctrip',
        name: '携程',
        price: 690,
        currency: 'CNY',
        lowest: false,
        data_freshness: 'stale',
      },
    ],
    data_freshness: 'fresh',
  },
  {
    id: 'mock-hu7579',
    flight_no: 'HU7579',
    platform: '携程',
    origin_city: '北京',
    origin_code: 'BJS',
    destination_city: '三亚',
    destination_code: 'SYX',
    depart_date: '2026-08-12',
    airline: '海南航空',
    depart_time: '21:05',
    arrive_time: '01:10',
    stops: 0,
    base_price: 610,
    tax: 100,
    baggage_allowance: '20KG',
    total_price: 710,
    currency: 'CNY',
    prices: [
      {
        id: 'ctrip',
        name: '携程',
        price: 710,
        currency: 'CNY',
        lowest: true,
        data_freshness: 'stale',
      },
    ],
    data_freshness: 'stale',
  },
]

export const MOCK_SEARCH: SearchResponse = {
  session_id: 'mini_mock_session',
  deals: MOCK_DEALS,
  recommendation: {
    text: '飞猪当前完整总价最低；如果你不想坐夜航，建议优先关注 CZ6718。',
  },
}

export const MOCK_RECOMMENDATIONS: RecommendationCard[] = [
  {
    id: 'syx',
    title: '北京 → 三亚',
    reason: '直飞选择多，近期价格进入可关注区间',
    tags: ['海岛', '直飞'],
    query_hint: '下个月北京去三亚，直飞，带20KG行李',
    preview_deal: MOCK_DEALS[0],
  },
  {
    id: 'xmn',
    title: '上海 → 厦门',
    reason: '周末往返价格波动明显，适合设置提醒',
    tags: ['周末', '短途'],
    query_hint: '下个周末上海去厦门，预算800',
    preview_deal: null,
  },
]

export const MOCK_ALERTS: AlertItem[] = [
  {
    id: 'alert_mock',
    origin: 'BJS',
    destination: 'SYX',
    depart_date: '2026-08-12',
    target_price: 620,
    current_price: 660,
    latest_price: 660,
    latest_provider: '飞猪',
    latest_quote_at: new Date().toISOString(),
    currency: 'CNY',
    notification_status: 'subscribed',
    status: 'active',
  },
]

export const MOCK_MEMORY: MemoryResponse = {
  memories: [
    { field: 'budget', value: 800, source: 'user' },
    {
      field: 'constraints',
      value: ['direct_only', 'checked_baggage'],
      source: 'learned',
    },
  ],
  query_history: [
    {
      id: 'q1',
      query_text: '下个月北京去三亚，直飞，带20KG行李',
      created_at: new Date().toISOString(),
    },
  ],
}
