export type FlightDeal = {
  id: string
  origin: string
  originCode: string
  destination: string
  destinationCode: string
  price: number
  originalPrice: number
  departDate: string
  airline: string
  departTime: string
  arriveTime: string
  signals: string[]
  confidence: 'high' | 'medium' | 'low'
  systemId: string
  gradientFrom: string
  gradientTo: string
  verdict: string
}

export type PreferenceMemory = {
  id: string
  field: string
  label: string
  value: string
  source: 'manual' | 'auto'
  updatedAt: string
  accentColor: string
  rotation: string
}
