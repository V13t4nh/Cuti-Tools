import type {
  AuctionLot,
  Deal,
  Evaluation,
  Freshness,
  LiquidityRow,
  PricingConfigResponse,
  PricingDraft,
  PricingPreviewResponse,
  Product,
  StatusPayload,
} from './types'

export type MarketPagination = { page: number; page_size: number; total: number; total_pages: number }
export type MarketQuery = { brand?: string; q?: string; status?: string; page: number; page_size: number }

function marketQuery(params: MarketQuery): string {
  const query = new URLSearchParams()
  if (params.brand) query.set('brand', params.brand)
  if (params.q) query.set('q', params.q)
  if (params.status) query.set('status', params.status)
  query.set('page', String(params.page))
  query.set('page_size', String(params.page_size))
  return `?${query}`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...init })
  const payload = await response.json() as T & { error?: { message?: string } }
  if (!response.ok) {
    const error = new Error(payload.error?.message || 'Không thể tải dữ liệu') as Error & {
      status?: number
      payload?: unknown
    }
    error.status = response.status
    error.payload = payload
    throw error
  }
  return payload
}
export const api = {
  status: () => request<StatusPayload>('/api/status'),
  search: (query: string) => request<{ products: Product[] }>(`/api/products/search?q=${encodeURIComponent(query)}`),
  product: (id: string) => request<{ product: Product }>(`/api/products/${encodeURIComponent(id)}`),
  evaluate: (body: object) => request<Evaluation>('/api/evaluate', { method: 'POST', body: JSON.stringify(body) }),
  saved: () => request<{ products: Product[] }>('/api/saved-products'),
  save: (productId: string) => request<{ created: boolean }>('/api/saved-products', { method: 'POST', body: JSON.stringify({ product_id: productId }) }),
  unsave: (productId: string) => request<{ removed: boolean }>(`/api/saved-products/${encodeURIComponent(productId)}`, { method: 'DELETE' }),
  deals: () => request<{ deals: Deal[] }>('/api/deals'),
  createDeal: (body: object) => request<{ deal: Deal; created: boolean }>('/api/deals', { method: 'POST', body: JSON.stringify(body) }),
  updateDeal: (id: number, status: string) => request<{ deal: Deal }>(`/api/deals/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  liquidity: (params: MarketQuery) => request<{ groups: LiquidityRow[]; data_freshness: Freshness; state: string; pagination: MarketPagination }>(`/api/liquidity${marketQuery(params)}`),
  liquidityDetail: (brand: string, form: string) => request<{ segment: LiquidityRow }>(`/api/liquidity/${encodeURIComponent(brand)}/${encodeURIComponent(form)}`),
  auctions: (params: MarketQuery) => request<{ lots: AuctionLot[]; data_freshness: Freshness; state: string; pagination: MarketPagination }>(`/api/auction-lots${marketQuery(params)}`),
  auction: (id: string) => request<{ lot: AuctionLot }>(`/api/auction-lots/${encodeURIComponent(id)}`),
  pricingConfig: () => request<PricingConfigResponse>('/api/pricing-config'),
  previewPricingConfig: (body: { draft: PricingDraft; inputs: { hammer_eur: number; cost_eur: number } }) =>
    request<PricingPreviewResponse>('/api/pricing-config/preview', { method: 'POST', body: JSON.stringify(body) }),
  applyPricingConfig: (body: { expected_revision: string; draft: PricingDraft }) =>
    request<PricingConfigResponse>('/api/pricing-config', { method: 'PUT', body: JSON.stringify(body) }),
}
