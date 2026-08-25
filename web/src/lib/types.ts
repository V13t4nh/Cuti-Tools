export type Verdict = "green" | "yellow" | "red" | "insufficient_data";

export interface DealEvaluation {
  verdict: Verdict;
  max_buy_cost_vnd: number | null;
  sample_size: number;
  sell_through_rate: number | null;
  median_days_to_close: number | null;
  heart_to_hammer_rate: number | null;
  net_p25_eur: number | null;
  net_median_eur: number | null;
  net_p75_eur: number | null;
  reason: string;
  threshold_eur: number;
}

export interface ComparisonChart {
  hammer_prices_eur: number[];
  input_hammer_eur: number | null;
  cycle_position: number | null;
  heart_acceleration_rate: number | null;
}

export interface ComparableLot {
  lot_id: string;
  title: string;
  brand: string;
  hammer_eur: number | null;
  hammer_vnd: number | null;
  hearts: number;
  bids_count: number | null;
  ended_at: string;
  score: number;
  url: string;
}

export interface EvaluateResponse {
  decision: DealEvaluation;
  chart: ComparisonChart;
  comparables: ComparableLot[];
  eur_vnd_rate: number;
}

export interface StatusResponse {
  lots_count: number;
  live_watch_count: number;
  eur_vnd_rate: number;
  match_threshold: number;
  min_comparables: number;
}

export interface BrandLiquidity {
  brand: string;
  form: string;
  lots: number;
  sold: number;
  sell_through: number;
  median_days_to_close: number | null;
  speed: number;
  heart_to_hammer: number;
  index: number;
  latest_qoq_change: number | null;
  stop_buying: boolean;
  status: string;
}

export interface LiveLot {
  lot_id: string;
  title: string;
  bidding_end_at: string;
  url: string;
}
