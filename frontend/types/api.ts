export interface DealCardDto {
  flight_no: string;
  platform: string;
  price: number;
  base_price: number;
  tax: number;
  baggage_fee: number;
  origin: string;
  destination: string;
  depart_date: string;
  signals?: string[];
  recommend_score?: number | null;
  booking_url?: string | null;
}

export interface DiscoveryCardContent {
  flightNo: string;
  platform: string;
  price: number;
  basePrice: number;
  tax: number;
  baggageFee: number;
  origin: string;
  destination: string;
  departDate: string;
  signals: string[];
  recommendScore: number | null;
  bookingUrl: string | null;
}
