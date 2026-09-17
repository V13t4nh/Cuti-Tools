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
export type MarketQuery = {
  brand?: string
  q?: string
  status?: string
  conditions?: string
  qualities?: string
  movements?: string
  materials?: string
  page: number
  page_size: number
}

function marketQuery(params: MarketQuery): string {
  const query = new URLSearchParams()
  if (params.brand) query.set('brand', params.brand)
  if (params.q) query.set('q', params.q)
  if (params.status) query.set('status', params.status)
  if (params.conditions) query.set('conditions', params.conditions)
  if (params.qualities) query.set('qualities', params.qualities)
  if (params.movements) query.set('movements', params.movements)
  if (params.materials) query.set('materials', params.materials)
  query.set('page', String(params.page))
  query.set('page_size', String(params.page_size))
  return `?${query}`
}

const AUTH_KEY = 'cuti_auth_token'

export function getStoredToken(): string {
  try {
    return localStorage.getItem(AUTH_KEY) || ''
  } catch {
    return ''
  }
}

export function setStoredToken(token: string): void {
  try {
    if (token) {
      localStorage.setItem(AUTH_KEY, token)
    } else {
      localStorage.removeItem(AUTH_KEY)
    }
  } catch {
    // ignore
  }
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')

export function mediaUrl(url: string | null | undefined): string | null {
  if (!url) return null
  const token = getStoredToken()
  const fullUrl = url.startsWith('/api/') && API_BASE ? `${API_BASE}${url}` : url
  if (!token || (!fullUrl.startsWith('/api/') && !fullUrl.includes('/api/'))) return fullUrl
  const separator = fullUrl.includes('?') ? '&' : '?'
  return `${fullUrl}${separator}token=${encodeURIComponent(token)}`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getStoredToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((init?.headers as Record<string, string>) || {}),
  }
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const response = await fetch(url, { ...init, headers })
  let payload: T & { error?: { message?: string } }
  try {
    payload = (await response.json()) as T & { error?: { message?: string } }
  } catch {
    if (!response.ok) {
      throw new Error(`Máy chủ trả về lỗi ${response.status}: ${response.statusText || 'Lỗi mạng'}`)
    }
    throw new Error('Dữ liệu máy chủ trả về không hợp lệ (không phải JSON)')
  }
  if (!response.ok) {
    if (response.status === 401 && path !== '/api/auth/login') {
      window.dispatchEvent(new CustomEvent('cuti:unauthorized'))
    }
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
  checkAuth: () => request<{ authenticated: boolean; required: boolean }>('/api/auth/check'),
  login: (secret: string) => request<{ ok: boolean; token: string }>('/api/auth/login', { method: 'POST', body: JSON.stringify({ secret }) }),
  logout: () => request<{ ok: boolean }>('/api/auth/logout', { method: 'POST' }),
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
  auctions: async (params: MarketQuery) => {
    const data = await request<{ lots: AuctionLot[]; data_freshness: Freshness; state: string; pagination: MarketPagination }>(`/api/auction-lots${marketQuery(params)}`)
    return {
      ...data,
      lots: data.lots.map(l => ({
        ...l,
        cover: { ...l.cover, url: mediaUrl(l.cover?.url) }
      }))
    }
  },
  auction: async (id: string) => {
    const data = await request<{ lot: AuctionLot }>(`/api/auction-lots/${encodeURIComponent(id)}`)
    return {
      ...data,
      lot: {
        ...data.lot,
        cover: { ...data.lot.cover, url: mediaUrl(data.lot.cover?.url) }
      }
    }
  },
  lotImages: async (lotId: string) => {
    const data = await request<{ lot_id: string; images: Array<{ idx: number; state: string; url: string | null; direct_url?: string | null }> }>(
      `/api/lots/${encodeURIComponent(lotId)}/images`
    )
    return {
      ...data,
      images: data.images.map(img => ({
        ...img,
        url: mediaUrl(img.url),
      }))
    }
  },
  pricingConfig: () => request<PricingConfigResponse>('/api/pricing-config'),
  previewPricingConfig: (body: { draft: PricingDraft; inputs: { hammer_eur: number; cost_eur: number } }) =>
    request<PricingPreviewResponse>('/api/pricing-config/preview', { method: 'POST', body: JSON.stringify(body) }),
  applyPricingConfig: (body: { expected_revision: string; draft: PricingDraft }) =>
    request<PricingConfigResponse>('/api/pricing-config', { method: 'PUT', body: JSON.stringify(body) }),
}
