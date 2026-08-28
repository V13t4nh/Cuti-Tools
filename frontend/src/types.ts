export type DataStatus = 'fresh' | 'stale' | 'no_data'
export type Product = { product_id: string; canonical_name: string; brand: string; reference: string; model_key: string; aliases: string[]; provenance: string }
export type Freshness = { status: DataStatus; last_updated_at: string | null; age_hours: number | null; stale_after_hours: number }
export type StatusPayload = { state: string; lots_count: number; live_watch_count: number; eur_vnd_rate?: number; pricing_revision?: string; data_freshness: Freshness; sources: { name: string; status: string; last_updated_at: string | null }[]; coverage: { lots: number; live_lots: number } }
export type Evaluation = { state: string; product: Product; input: { ask_price: number; currency: string; condition: string }; data_freshness: Freshness; decision: { verdict: string; max_buy_price_vnd: number | null; price_gap_vnd: number | null; sample_size: number; attempt_count: number; sell_through_rate: number | null; median_days_to_close: number | null; heart_to_hammer_rate: number | null; net_p25_eur: number | null; net_median_eur: number | null; net_p75_eur: number | null; reason: string; threshold_eur: number }; evidence: { lot_id: string; title: string; hammer_eur: number | null; ended_at: string; score: number; url: string }[] }
export type LiquidityRow = { brand: string; form: string; data_state: string; lots: number; sold: number | null; sell_through: number | null; median_days_to_close: number | null; speed: number | null; heart_to_hammer: number | null; index: number | null; latest_qoq_change: number | null; stop_buying: boolean; status: string | null; window_start: string; window_end: string }
export type AuctionLotCoverState = 'missing' | 'queued' | 'uploading' | 'ready' | 'retryable_error' | 'permanent_error'
export type AuctionLotCover = { state: AuctionLotCoverState; url: string | null }
export type AuctionLot = { lot_id: string; source: string; title: string; subtitle: string | null; url: string; bidding_end_at: string | null; status: string; cover: AuctionLotCover }
export type Deal = { id: number; product: Product; ask_price: number; currency: string; condition: string; status: string; snapshot: Record<string, unknown>; created_at: string; updated_at: string }

export type PricingUnit = 'eur' | 'rate' | 'vnd_per_eur'
export type PricingParameter = {
  name: string
  value: number
  unit: PricingUnit
  required: boolean
  removable: boolean
}
export type PricingHelper = { name: string; expression: string }
export type PricingFormulas = { net_proceeds: string; profit_threshold: string }
export type PricingInputVariable = { name: string; unit: string; source?: string }
export type PricingCapabilities = Record<string, unknown>
export type PricingActiveConfig = {
  revision: string
  source: 'file' | 'env-derived'
  updated_at: string | null
  parameters: PricingParameter[]
  helpers: PricingHelper[]
  formulas: PricingFormulas
  input_variables: PricingInputVariable[]
  capabilities: PricingCapabilities
}
export type PricingConfigResponse = { state: 'active'; active: PricingActiveConfig }
export type PricingDraftParameter = { name: string; value: number; unit: PricingUnit }
export type PricingDraft = {
  parameters: PricingDraftParameter[]
  helpers: PricingHelper[]
  formulas: PricingFormulas
}
export type PricingError = { field: string; code: string; message: string }
export type PricingOutput = { name: string; label: string; value: number; unit: string; formatted: string }
export type PricingPreview = { outputs: PricingOutput[]; active_outputs: PricingOutput[] }
export type PricingPreviewResponse = {
  valid: boolean
  active_revision: string
  draft: PricingDraft
  preview: PricingPreview | null
  errors: PricingError[]
}
