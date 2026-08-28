<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { api, type MarketPagination } from './api'
import AppIcon from './components/AppIcon.vue'
import PricingSettingsPage from './components/PricingSettingsPage.vue'
import type { AuctionLot, Deal, Evaluation, LiquidityRow, Product, StatusPayload } from './types'

type Route = '/assessment' | '/tracking' | '/market' | '/settings'
const route = ref<Route>('/assessment')
const pricingDraftDirty = ref(false)
const trackingTab = ref<'deals' | 'saved'>('deals')
const marketTab = ref<'liquidity' | 'auctions'>('liquidity')
const status = ref<StatusPayload | null>(null)
const statusOpen = ref(false)
const statusButton = ref<HTMLButtonElement | null>(null)
const statusPanel = ref<HTMLElement | null>(null)
const detailPanel = ref<HTMLElement | null>(null)
const detailTitle = ref<HTMLElement | null>(null)
let detailReturn: HTMLElement | null = null
const loading = ref(false)
const areaError = ref('')
const toast = ref('')

const searchQuery = ref('')
const suggestions = ref<Product[]>([])
const selectedProduct = ref<Product | null>(null)
const searching = ref(false)
const searchError = ref('')
const activeSuggestionIndex = ref(-1)
const autocompleteDismissed = ref(false)
const askPrice = ref('')
const currency = ref('')
const condition = ref('')
const fieldError = ref('')
const evaluation = ref<Evaluation | null>(null)
const evaluating = ref(false)

const deals = ref<Deal[]>([])
const savedProducts = ref<Product[]>([])
const selectedDeal = ref<Deal | null>(null)
const selectedSaved = ref<Product | null>(null)
const trackingQuery = ref('')

const liquidityRows = ref<LiquidityRow[]>([])
const auctionLots = ref<AuctionLot[]>([])
const liquidityPagination = ref<MarketPagination | null>(null)
const auctionPagination = ref<MarketPagination | null>(null)
const selectedLiquidity = ref<LiquidityRow | null>(null)
const selectedAuction = ref<AuctionLot | null>(null)
const marketQuery = ref('')
const liquidityFilter = ref('all')
const auctionFilter = ref('all')
const marketPage = ref(1)
const pendingDetail = ref('')
const MARKET_PAGE_SIZE = 8

type Theme = 'light' | 'dark'
const theme = ref<Theme>(
  typeof document !== 'undefined' && document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
)
const clockNow = ref(new Date())
const clockTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'múi giờ trình duyệt'
const clockHourMinuteFormatter = new Intl.DateTimeFormat('vi-VN', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
const clockSecondsFormatter = new Intl.DateTimeFormat('vi-VN', { second: '2-digit', hourCycle: 'h23' })
const clockDateFormatter = new Intl.DateTimeFormat('vi-VN', { weekday: 'short', day: '2-digit', month: '2-digit' })
let searchTimer: number | undefined
let searchSequence = 0
let clockTimer: number | undefined

const freshness = computed(() => status.value?.data_freshness)
const canEvaluate = computed(() =>
  Boolean(selectedProduct.value && askPrice.value && currency.value && condition.value && freshness.value?.status !== 'no_data' && !evaluating.value)
)
const filteredDeals = computed(() =>
  deals.value.filter((deal) => `${deal.product.canonical_name} ${deal.product.reference}`.toLowerCase().includes(trackingQuery.value.toLowerCase()))
)
const filteredSaved = computed(() =>
  savedProducts.value.filter((product) => `${product.canonical_name} ${product.reference}`.toLowerCase().includes(trackingQuery.value.toLowerCase()))
)
const marketPagination = computed(() => (marketTab.value === 'liquidity' ? liquidityPagination.value : auctionPagination.value))
const marketPageCount = computed(() => Math.max(1, marketPagination.value?.total_pages || 1))
const marketHasFilters = computed(() => Boolean(marketQuery.value.trim()) || (marketTab.value === 'liquidity' ? liquidityFilter.value !== 'all' : auctionFilter.value !== 'all'))
const marketTotalLabel = computed(() => marketPagination.value ? `${marketPagination.value.total} mục` : 'Không đủ dữ liệu')
const autocompleteOpen = computed(() => !autocompleteDismissed.value && Boolean(searching.value || suggestions.value.length || searchError.value || (searchQuery.value && !selectedProduct.value && !searching.value)))
const detailOpen = computed(() => Boolean(selectedDeal.value || selectedSaved.value || selectedLiquidity.value || selectedAuction.value))
const coverageSummary = computed(() => {
  const coverage = status.value?.coverage
  if (!coverage || !Number.isFinite(coverage.lots) || !Number.isFinite(coverage.live_lots)) return 'Không đủ dữ liệu'
  return `${coverage.lots} lô đã kết thúc · ${coverage.live_lots} lô đang theo dõi`
})
const activeSuggestionId = computed(() => {
  if (!autocompleteOpen.value) return undefined
  const product = suggestions.value[activeSuggestionIndex.value]
  return product ? `product-suggestion-${product.product_id}` : undefined
})
const localHourMinute = computed(() => clockHourMinuteFormatter.format(clockNow.value))
const localSeconds = computed(() => clockSecondsFormatter.format(clockNow.value))
const localDate = computed(() => clockDateFormatter.format(clockNow.value))
const clockDatetime = computed(() => clockNow.value.toISOString())
const clockAriaLabel = computed(() => `Giờ địa phương ${localHourMinute.value}:${localSeconds.value}, ${localDate.value}, múi giờ ${clockTimeZone}`)
const themeLabel = computed(() => (theme.value === 'dark' ? 'Sáng' : 'Tối'))
const themeAriaLabel = computed(() => (theme.value === 'dark' ? 'Chuyển sang chế độ sáng' : 'Chuyển sang chế độ tối'))
const statusAriaLabel = computed(() => `Trạng thái dữ liệu: ${freshnessLabel(freshness.value?.status)}`)

const askPriceVnd = computed(() => {
  if (!evaluation.value) return null
  if (evaluation.value.input.currency.toLowerCase() === 'vnd') {
    return evaluation.value.input.ask_price
  }
  const maxBuy = evaluation.value.decision.max_buy_price_vnd
  const gap = evaluation.value.decision.price_gap_vnd
  if (maxBuy === null || gap === null) return null
  return maxBuy - gap
})

const pinPositionPercent = computed(() => {
  if (!evaluation.value || !evaluation.value.decision.max_buy_price_vnd || askPriceVnd.value === null) return null
  const maxBuy = evaluation.value.decision.max_buy_price_vnd
  const ask = askPriceVnd.value
  if (ask <= 0) return 0
  const ratio = ask / maxBuy
  if (ratio <= 1) {
    return Math.max(4, Math.min(50, ratio * 50))
  }
  return Math.max(50, Math.min(96, 50 + (ratio - 1) * 46))
})

function asRoute(path: string): Route {
  return path === '/tracking' || path === '/market' || path === '/settings' ? path : '/assessment'
}

function parsePage(value: string | null): number {
  const page = Number(value)
  return Number.isInteger(page) && page > 0 ? page : 1
}

function syncLocation(): void {
  route.value = asRoute(window.location.pathname)
  const query = new URLSearchParams(window.location.search)
  if (route.value === '/tracking') trackingTab.value = query.get('tab') === 'saved' ? 'saved' : 'deals'
  if (route.value === '/market') marketTab.value = query.get('tab') === 'auctions' ? 'auctions' : 'liquidity'
  trackingQuery.value = route.value === '/tracking' ? query.get('q') || '' : trackingQuery.value
  if (route.value === '/market') {
    marketQuery.value = query.get('q') || ''
    marketPage.value = parsePage(query.get('page'))
    if (marketTab.value === 'liquidity') liquidityFilter.value = query.get('filter') || 'all'
    else auctionFilter.value = query.get('filter') || 'all'
  }
  pendingDetail.value = query.get('detail') || ''
  if (route.value === '/assessment' && query.get('query')) {
    searchQuery.value = query.get('query') || ''
    scheduleSearch()
  }
  if (route.value === '/assessment' && query.get('product')) {
    void api
      .product(query.get('product') || '')
      .then(({ product }) => chooseProduct(product))
      .catch(() => {
        searchError.value = 'Không tải được sản phẩm đã chọn.'
      })
  }
  void loadRoute()
}

function confirmLeaveSettings(nextRoute: Route): boolean {
  if (route.value !== '/settings' || nextRoute === '/settings' || !pricingDraftDirty.value) return true
  if (typeof window !== 'undefined' && !window.confirm('Bản nháp cấu hình chưa áp dụng. Rời trang sẽ bỏ các thay đổi này, bạn vẫn muốn tiếp tục?')) return false
  pricingDraftDirty.value = false
  return true
}

function navigate(path: string): void {
  const nextRoute = asRoute(path.split('?')[0])
  if (!confirmLeaveSettings(nextRoute)) return
  window.history.pushState({}, '', path)
  syncLocation()
}

function handlePopState(): void {
  const nextRoute = asRoute(window.location.pathname)
  if (!confirmLeaveSettings(nextRoute)) {
    window.history.pushState({}, '', '/settings')
    return
  }
  syncLocation()
}

function setTab(tab: string): void {
  if (route.value === '/tracking') {
    trackingTab.value = tab === 'saved' ? 'saved' : 'deals'
    navigate(`/tracking?tab=${trackingTab.value}`)
  } else {
    marketTab.value = tab === 'auctions' ? 'auctions' : 'liquidity'
    marketPage.value = 1
    updateMarketUrl('push', 1)
    syncLocation()
  }
}

function handleTabKey(event: KeyboardEvent, group: 'tracking' | 'market'): void {
  const values = group === 'tracking' ? ['deals', 'saved'] : ['liquidity', 'auctions']
  const current = group === 'tracking' ? trackingTab.value : marketTab.value
  const currentIndex = values.indexOf(current)
  let nextIndex = currentIndex
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') nextIndex = (currentIndex + 1) % values.length
  if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') nextIndex = (currentIndex - 1 + values.length) % values.length
  if (nextIndex === currentIndex) return
  event.preventDefault()
  setTab(values[nextIndex])
  void nextTick(() => document.querySelector<HTMLElement>(`[data-tab-group="${group}"][data-tab-index="${nextIndex}"]`)?.focus())
}

function notify(message: string): void {
  toast.value = message
  window.setTimeout(() => {
    if (toast.value === message) toast.value = ''
  }, 2400)
}

function toggleStatus(): void {
  statusOpen.value = !statusOpen.value
  if (statusOpen.value) void nextTick(() => statusPanel.value?.focus())
}

function toggleTheme(): void {
  const nextTheme: Theme = theme.value === 'dark' ? 'light' : 'dark'
  theme.value = nextTheme
  if (typeof document !== 'undefined') {
    document.documentElement.dataset.theme = nextTheme
    document.documentElement.style.colorScheme = nextTheme
  }
  try {
    window.localStorage.setItem('cuti-theme', nextTheme)
  } catch {
    /* storage can be unavailable */
  }
}

function captureDetail(event: Event, key: string): void {
  detailReturn = event.currentTarget as HTMLElement
  const query = new URLSearchParams(window.location.search)
  query.set('detail', key)
  window.history.pushState({}, '', `${window.location.pathname}?${query}`)
  window.setTimeout(() => detailTitle.value?.focus(), 0)
}

function handleSearchKey(event: KeyboardEvent): void {
  if (event.key === 'ArrowDown' && suggestions.value.length) {
    event.preventDefault()
    autocompleteDismissed.value = false
    activeSuggestionIndex.value = (activeSuggestionIndex.value + 1) % suggestions.value.length
    void nextTick(() => document.getElementById(activeSuggestionId.value || '')?.scrollIntoView({ block: 'nearest' }))
  } else if (event.key === 'ArrowUp' && suggestions.value.length) {
    event.preventDefault()
    autocompleteDismissed.value = false
    activeSuggestionIndex.value = activeSuggestionIndex.value <= 0 ? suggestions.value.length - 1 : activeSuggestionIndex.value - 1
    void nextTick(() => document.getElementById(activeSuggestionId.value || '')?.scrollIntoView({ block: 'nearest' }))
  } else if (event.key === 'Enter' && autocompleteOpen.value && activeSuggestionIndex.value >= 0) {
    event.preventDefault()
    const product = suggestions.value[activeSuggestionIndex.value]
    if (product) chooseProduct(product)
  } else if (event.key === 'Escape' && autocompleteOpen.value) {
    event.preventDefault()
    activeSuggestionIndex.value = -1
    autocompleteDismissed.value = true
  }
}

function restoreDetail(): void {
  const split = pendingDetail.value.indexOf(':')
  const kind = pendingDetail.value.slice(0, split)
  const id = pendingDetail.value.slice(split + 1)
  if (kind === 'deal') selectedDeal.value = deals.value.find((item) => item.id === Number(id)) || null
  if (kind === 'saved') selectedSaved.value = savedProducts.value.find((item) => item.product_id === id) || null
  if (kind === 'liquidity') selectedLiquidity.value = liquidityRows.value.find((item) => `${item.brand}|${item.form}` === id) || null
  if (kind === 'auction') selectedAuction.value = auctionLots.value.find((item) => item.lot_id === id) || null
  if (selectedDeal.value || selectedSaved.value || selectedLiquidity.value || selectedAuction.value) {
    window.setTimeout(() => detailTitle.value?.focus(), 0)
  }
}

function updateTrackingUrl(): void {
  const query = new URLSearchParams(window.location.search)
  trackingQuery.value ? query.set('q', trackingQuery.value) : query.delete('q')
  query.delete('detail')
  window.history.replaceState({}, '', `/tracking?${query}`)
}

function updateMarketUrl(mode: 'push' | 'replace', page = marketPage.value): void {
  const query = new URLSearchParams(window.location.search)
  query.set('tab', marketTab.value)
  query.set('page', String(page))
  marketQuery.value ? query.set('q', marketQuery.value) : query.delete('q')
  const filter = marketTab.value === 'liquidity' ? liquidityFilter.value : auctionFilter.value
  filter !== 'all' ? query.set('filter', filter) : query.delete('filter')
  const target = `/market?${query}`
  if (mode === 'push') window.history.pushState({}, '', target)
  else window.history.replaceState({}, '', target)
}

function applyMarket(): void {
  marketPage.value = 1
  updateMarketUrl('push', 1)
  void loadMarket()
}

function clearMarketFilters(): void {
  marketQuery.value = ''
  if (marketTab.value === 'liquidity') liquidityFilter.value = 'all'
  else auctionFilter.value = 'all'
  marketPage.value = 1
  updateMarketUrl('replace', 1)
  void loadMarket()
}

function setMarketPage(page: number): void {
  const nextPage = Math.min(Math.max(page, 1), marketPageCount.value)
  if (nextPage === marketPage.value) return
  marketPage.value = nextPage
  updateMarketUrl('push', nextPage)
  void loadMarket()
}

function clampMarketPage(): void {
  const clampedPage = Math.min(Math.max(marketPage.value, 1), marketPageCount.value)
  const urlPage = new URLSearchParams(window.location.search).get('page')
  if (clampedPage !== marketPage.value || urlPage !== String(clampedPage)) {
    marketPage.value = clampedPage
    updateMarketUrl('replace', clampedPage)
  }
}

async function loadStatus(): Promise<void> {
  try {
    status.value = await api.status()
  } catch {
    status.value = null
    areaError.value = 'Không tải được trạng thái dữ liệu. Hãy thử lại.'
  }
}

function onPricingApplied(): void {
  // A new pricing profile changes only the current in-memory assessment result.
  // Saved deal snapshots remain immutable and are loaded from their stored context.
  evaluation.value = null
  void loadStatus()
}

function onPricingDraftDirty(dirty: boolean): void {
  pricingDraftDirty.value = dirty
}

async function loadRoute(): Promise<void> {
  loading.value = true
  areaError.value = ''
  closeDetail()
  try {
    if (route.value === '/tracking') {
      if (trackingTab.value === 'deals') deals.value = (await api.deals()).deals
      else savedProducts.value = (await api.saved()).products
    } else if (route.value === '/market') {
      await loadMarket()
    }
    restoreDetail()
  } catch (error) {
    if (route.value === '/tracking') {
      deals.value = []
      savedProducts.value = []
    } else if (route.value === '/market') {
      liquidityRows.value = []
      auctionLots.value = []
    }
    areaError.value = error instanceof Error ? error.message : 'Không tải được dữ liệu.'
  } finally {
    loading.value = false
  }
}

async function loadMarket(): Promise<void> {
  const filter = marketTab.value === 'liquidity' ? liquidityFilter.value : auctionFilter.value
  const params = {
    [marketTab.value === 'liquidity' ? 'brand' : 'q']: marketQuery.value || undefined,
    status: filter !== 'all' ? filter : undefined,
    page: marketPage.value,
    page_size: MARKET_PAGE_SIZE,
  }
  if (marketTab.value === 'liquidity') {
    const result = await api.liquidity(params)
    liquidityRows.value = result.groups
    liquidityPagination.value = result.pagination
    marketPage.value = result.pagination.page
  } else {
    const result = await api.auctions(params)
    auctionLots.value = result.lots
    auctionPagination.value = result.pagination
    marketPage.value = result.pagination.page
  }
  clampMarketPage()
}

function scheduleSearch(): void {
  window.clearTimeout(searchTimer)
  selectedProduct.value = null
  evaluation.value = null
  searchError.value = ''
  activeSuggestionIndex.value = -1
  autocompleteDismissed.value = false
  if (!searchQuery.value.trim()) {
    suggestions.value = []
    return
  }
  searchTimer = window.setTimeout(() => void searchProducts(), 180)
}

async function searchProducts(): Promise<void> {
  const sequence = ++searchSequence
  searching.value = true
  try {
    const result = await api.search(searchQuery.value)
    if (sequence === searchSequence) {
      suggestions.value = result.products
      activeSuggestionIndex.value = -1
    }
  } catch {
    if (sequence === searchSequence) {
      suggestions.value = []
      activeSuggestionIndex.value = -1
      searchError.value = 'Tìm kiếm đang không khả dụng. Hãy thử lại.'
    }
  } finally {
    if (sequence === searchSequence) searching.value = false
  }
}

function chooseProduct(product: Product): void {
  selectedProduct.value = product
  searchQuery.value = product.canonical_name
  suggestions.value = []
  activeSuggestionIndex.value = -1
  searchError.value = ''
  evaluation.value = null
}

function invalidateResult(): void {
  evaluation.value = null
}

async function runEvaluation(): Promise<void> {
  fieldError.value = ''
  if (!selectedProduct.value) {
    fieldError.value = 'Hãy chọn một sản phẩm trong danh sách đề xuất.'
    return
  }
  const amount = Number(askPrice.value)
  if (!Number.isFinite(amount) || amount <= 0 || !currency.value || !condition.value) {
    fieldError.value = 'Nhập đủ giá chào, tiền tệ và tình trạng hợp lệ.'
    return
  }
  evaluating.value = true
  try {
    evaluation.value = await api.evaluate({
      product_id: selectedProduct.value.product_id,
      ask_price: amount,
      currency: currency.value,
      condition: condition.value,
    })
  } catch (error) {
    fieldError.value = error instanceof Error ? error.message : 'Không thể thẩm định.'
  } finally {
    evaluating.value = false
  }
}

async function saveCurrentProduct(): Promise<void> {
  if (!selectedProduct.value) return
  try {
    await api.save(selectedProduct.value.product_id)
    notify('Đã lưu mẫu. Kết quả thẩm định chưa được lưu.')
  } catch (error) {
    fieldError.value = error instanceof Error ? error.message : 'Không thể lưu mẫu.'
  }
}

async function saveCurrentDeal(): Promise<void> {
  if (!selectedProduct.value || !evaluation.value) return
  try {
    const result = await api.createDeal({
      product_id: selectedProduct.value.product_id,
      ask_price: Number(askPrice.value),
      currency: currency.value,
      condition: condition.value,
      snapshot: evaluation.value,
    })
    notify(result.created ? 'Đã lưu thương vụ ở trạng thái Đang cân nhắc.' : 'Thương vụ này đã được lưu trước đó.')
  } catch (error) {
    fieldError.value = error instanceof Error ? error.message : 'Không thể lưu thương vụ.'
  }
}

async function unsave(product: Product): Promise<void> {
  await api.unsave(product.product_id)
  savedProducts.value = savedProducts.value.filter((item) => item.product_id !== product.product_id)
  selectedSaved.value = null
  notify('Đã bỏ lưu mẫu.')
}

async function changeDealStatus(deal: Deal, state: string): Promise<void> {
  try {
    const updated = (await api.updateDeal(deal.id, state)).deal
    deals.value = deals.value.map((item) => (item.id === updated.id ? updated : item))
    selectedDeal.value = updated
    notify(`Đã chuyển sang ${dealStatus(state)}.`)
  } catch (error) {
    areaError.value = error instanceof Error ? error.message : 'Không cập nhật được trạng thái.'
  }
}

function assessProduct(product: Product): void {
  selectedProduct.value = product
  searchQuery.value = product.canonical_name
  navigate(`/assessment?product=${encodeURIComponent(product.product_id)}`)
}

function assessLot(lot: AuctionLot): void {
  navigate(`/assessment?query=${encodeURIComponent(lot.title)}`)
}

function closeDetail(): void {
  const target = detailReturn
  selectedDeal.value = null
  selectedSaved.value = null
  selectedLiquidity.value = null
  selectedAuction.value = null
  detailReturn = null
  void nextTick(() => target?.focus())
}

function trapDetailFocus(event: KeyboardEvent): void {
  if (event.key !== 'Tab' || !detailPanel.value) return
  const focusable = Array.from(detailPanel.value.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'))
  if (!focusable.length) return
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

function userCloseDetail(): void {
  if (new URLSearchParams(window.location.search).has('detail')) window.history.back()
  else closeDetail()
}

function money(value: number | null, code = 'VND'): string {
  if (value === null) return 'Không đủ dữ liệu'
  return new Intl.NumberFormat('vi-VN', {
    style: 'currency',
    currency: code.toUpperCase(),
    maximumFractionDigits: code.toLowerCase() === 'vnd' ? 0 : 2,
  }).format(value)
}

function percent(value: number | null): string {
  return value === null ? 'Không đủ dữ liệu' : new Intl.NumberFormat('vi-VN', { style: 'percent', maximumFractionDigits: 1 }).format(value)
}

function number(value: number | null): string {
  return value === null ? 'Không đủ dữ liệu' : new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 }).format(value)
}

function dateTime(value: string | null): string {
  return value ? new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeStyle: 'short', timeZone: 'Asia/Ho_Chi_Minh' }).format(new Date(value)) : 'Không có'
}

function dateOnly(value: string): string {
  return new Intl.DateTimeFormat('vi-VN', { dateStyle: 'short', timeZone: 'Asia/Ho_Chi_Minh' }).format(new Date(`${value}T12:00:00+07:00`))
}

function freshnessLabel(value?: string): string {
  return ({ fresh: 'Dữ liệu mới', stale: 'Dữ liệu đã cũ', no_data: 'Không có dữ liệu' } as Record<string, string>)[value || ''] || 'Không rõ dữ liệu'
}

function verdict(value: string): string {
  return ({ green: 'Có thể mua', yellow: 'Cần thương lượng', red: 'Không nên mua', insufficient_data: 'Không đủ dữ liệu' } as Record<string, string>)[value] || 'Không đủ dữ liệu'
}

function reason(value: string): string {
  return (
    {
      'p25 net profit exceeds the required threshold': 'Kịch bản thận trọng vẫn vượt ngưỡng lợi nhuận.',
      'median net profit exceeds the required threshold': 'Kịch bản trung vị vượt ngưỡng nhưng kịch bản thận trọng chưa đạt.',
      'median net profit does not exceed the required threshold': 'Kịch bản trung vị không vượt ngưỡng lợi nhuận.',
    } as Record<string, string>
  )[value] || 'Không rõ dữ liệu'
}

function conditionLabel(value: string): string {
  return ({ naked: 'Chỉ đồng hồ', box: 'Có hộp', papers: 'Có giấy', fullset: 'Đủ bộ' } as Record<string, string>)[value] || 'Không rõ dữ liệu'
}

function dealStatus(value: string): string {
  return ({ considering: 'Đang cân nhắc', purchased: 'Đã mua', skipped: 'Đã bỏ qua' } as Record<string, string>)[value] || 'Không rõ dữ liệu'
}

function trend(value: string | null, stop = false): string {
  if (stop) return 'Dừng mua'
  return ({ improving: 'Cải thiện', stable: 'Ổn định', declining: 'Suy giảm' } as Record<string, string>)[value || ''] || 'Không đủ dữ liệu'
}

function formLabel(value: string): string {
  return ({ round: 'Tròn', rectangular: 'Chữ nhật', square: 'Vuông', tonneau: 'Tonneau', other: 'Khác', unknown: 'Không rõ' } as Record<string, string>)[value] || value
}

function coverStateLabel(state: AuctionLot['cover']['state']): string {
  return (
    {
      missing: 'Không có ảnh',
      queued: 'Ảnh đang chờ',
      uploading: 'Đang lưu ảnh',
      ready: 'Ảnh không khả dụng',
      retryable_error: 'Lỗi tải ảnh',
      permanent_error: 'Ảnh không khả dụng',
    } as Record<AuctionLot['cover']['state'], string>
  )[state]
}

function snapshotDecision(deal: Deal): Record<string, unknown> {
  const snapshot = deal.snapshot as { decision?: Record<string, unknown> }
  return snapshot.decision || {}
}

function handleKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    if (statusOpen.value) {
      statusOpen.value = false
      void nextTick(() => statusButton.value?.focus())
    } else {
      userCloseDetail()
    }
  } else if (selectedDeal.value || selectedSaved.value || selectedLiquidity.value || selectedAuction.value) {
    trapDetailFocus(event)
  }
}

onMounted(() => {
  window.addEventListener('popstate', handlePopState)
  window.addEventListener('keydown', handleKey)
  clockNow.value = new Date()
  clockTimer = window.setInterval(() => {
    clockNow.value = new Date()
  }, 1000)
  void loadStatus()
  syncLocation()
})

onUnmounted(() => {
  window.removeEventListener('popstate', handlePopState)
  window.removeEventListener('keydown', handleKey)
  window.clearTimeout(searchTimer)
  if (clockTimer !== undefined) window.clearInterval(clockTimer)
})
</script>

<template>
  <div class="app-shell">
    <header class="topbar" :inert="detailOpen">
      <button class="brand" @click="navigate('/assessment')">
        <AppIcon name="cuti-mark" class="brand-icon" />
        <span class="brand-title">CUTI</span>
        <span class="brand-subtitle">Decision Terminal</span>
      </button>

      <nav class="topnav" aria-label="Điều hướng chính">
        <button
          :class="{ active: route === '/assessment' }"
          :aria-current="route === '/assessment' ? 'page' : undefined"
          @click="navigate('/assessment')"
        >
          <AppIcon name="assessment" />
          <span>Thẩm định</span>
        </button>
        <button
          :class="{ active: route === '/tracking' }"
          :aria-current="route === '/tracking' ? 'page' : undefined"
          @click="navigate('/tracking')"
        >
          <AppIcon name="tracking" />
          <span>Theo dõi</span>
        </button>
        <button
          :class="{ active: route === '/market' }"
          :aria-current="route === '/market' ? 'page' : undefined"
          @click="navigate('/market')"
        >
          <AppIcon name="market" />
          <span>Thị trường</span>
        </button>
        <button
          :class="{ active: route === '/settings' }"
          :aria-current="route === '/settings' ? 'page' : undefined"
          @click="navigate('/settings')"
        >
          <AppIcon name="settings" />
          <span>Cấu hình tính toán</span>
        </button>
      </nav>

      <div class="topbar-actions">
        <time class="local-clock" :datetime="clockDatetime" :aria-label="clockAriaLabel" :title="clockAriaLabel">
          <AppIcon name="clock" />
          <span class="clock-copy">
            <span class="clock-time">
              <span>{{ localHourMinute }}</span>
              <span class="clock-seconds">:{{ localSeconds }}</span>
            </span>
            <span class="clock-date">{{ localDate }}</span>
          </span>
        </time>

        <button
          class="theme-toggle"
          type="button"
          :aria-label="themeAriaLabel"
          :title="themeAriaLabel"
          :aria-pressed="theme === 'dark'"
          @click="toggleTheme"
        >
          <AppIcon :name="theme === 'dark' ? 'sun' : 'moon'" />
          <span class="theme-toggle-label">{{ themeLabel }}</span>
        </button>

        <div class="status-wrap">
          <button
            ref="statusButton"
            class="status-button"
            :data-state="freshness?.status"
            aria-haspopup="dialog"
            :aria-expanded="statusOpen"
            :aria-label="statusAriaLabel"
            :title="statusAriaLabel"
            @click="toggleStatus"
          >
            <span class="status-dot" />
            <span class="status-label">{{ freshnessLabel(freshness?.status) }}</span>
          </button>

          <Transition name="popover">
            <section
              v-if="statusOpen"
              ref="statusPanel"
              tabindex="-1"
              class="popover"
              role="dialog"
              aria-label="Trạng thái dữ liệu"
            >
              <div class="detail-heading">
                <h2>Trạng thái dữ liệu</h2>
                <button aria-label="Đóng" @click="statusOpen = false"><AppIcon name="close" /></button>
              </div>
              <dl>
                <dt>Cập nhật gần nhất</dt>
                <dd>{{ dateTime(freshness?.last_updated_at || null) }}</dd>
                <dt>Ngưỡng dữ liệu cũ</dt>
                <dd>{{ freshness?.stale_after_hours ?? 'Không có' }} giờ</dd>
                <dt>Độ phủ</dt>
                <dd>{{ coverageSummary }}</dd>
              </dl>
              <div v-for="source in status?.sources" :key="source.name" class="source-row">
                <span>{{ source.name }}</span>
                <strong>{{ freshnessLabel(source.status) }}</strong>
              </div>
            </section>
          </Transition>
        </div>
      </div>
    </header>

    <main :inert="detailOpen">
      <Transition name="route" mode="out-in">
        <!-- Route 1: Assessment -->
        <section v-if="route === '/assessment'" key="assessment" class="page assessment-page">
          <header class="page-header">
            <div class="page-header-content">
              <p class="eyebrow">01 / Quyết định mua</p>
              <h1>Thẩm định</h1>
              <p>Xác nhận đúng sản phẩm, nhập thông tin thương vụ và nhận phân tích ranh giới mua theo thời gian thực.</p>
            </div>
            <div class="route-context-badge" aria-hidden="true">
              <span class="context-flow">INPUT → EVIDENCE → DECISION</span>
              <span class="context-tag">THE CUT / BUY BOUNDARY</span>
            </div>
          </header>

          <div v-if="freshness?.status === 'stale'" class="banner warning">
            Dữ liệu đã cũ từ {{ dateTime(freshness.last_updated_at) }}. Bạn vẫn có thể tiếp tục thẩm định.
          </div>
          <div v-if="freshness?.status === 'no_data'" class="banner negative">
            Chưa có dữ liệu thị trường. Thẩm định tạm thời bị chặn; bạn vẫn có thể lưu mẫu.
          </div>

          <!-- Step 1: Product search -->
          <div class="form-card search-card">
            <div class="form-card-header">
              <div class="step-indicator">1</div>
              <div>
                <h2 class="card-title">Sản phẩm chuẩn</h2>
                <p class="card-subtitle">Tìm kiếm và chọn sản phẩm theo tên, model hoặc mã reference</p>
              </div>
            </div>

            <div class="searchbox" :class="{ confirmed: selectedProduct, searching: searching }">
              <div class="search-input-wrap">
                <AppIcon name="search" class="search-leading-icon" />
                <input
                  id="product-search"
                  v-model="searchQuery"
                  autocomplete="off"
                  role="combobox"
                  aria-autocomplete="list"
                  aria-controls="product-suggestions"
                  aria-label="Tìm sản phẩm chuẩn"
                  :aria-expanded="autocompleteOpen"
                  :aria-activedescendant="activeSuggestionId"
                  placeholder="Nhập tên thương hiệu, model hoặc reference..."
                  @input="scheduleSearch"
                  @keydown="handleSearchKey"
                />
                <div v-if="searching" class="search-spinner" aria-label="Đang tìm kiếm" />
                <span v-else-if="selectedProduct" class="confirmed-label">
                  <AppIcon name="check" /> Đã xác nhận
                </span>
              </div>

              <Transition name="popover">
                <div
                  v-if="autocompleteOpen"
                  id="product-suggestions"
                  class="autocomplete"
                  role="listbox"
                  aria-label="Gợi ý sản phẩm"
                >
                  <div v-if="searching" class="autocomplete-state loading">
                    <div class="inline-spinner" />
                    <span>Đang tìm kiếm trong danh mục chuẩn…</span>
                  </div>
                  <div v-else-if="searchError" class="autocomplete-state error">
                    <p class="inline-error">{{ searchError }}</p>
                  </div>
                  <div v-else-if="!suggestions.length" class="autocomplete-state empty">
                    <span>Không tìm thấy sản phẩm nào khớp với <strong>"{{ searchQuery }}"</strong></span>
                  </div>
                  <template v-else>
                    <div class="autocomplete-header">
                      <span>GỢI Ý DANH MỤC CHUẨN ({{ suggestions.length }})</span>
                    </div>
                    <button
                      v-for="(product, index) in suggestions"
                      :key="product.product_id"
                      :id="`product-suggestion-${product.product_id}`"
                      class="autocomplete-item"
                      role="option"
                      tabindex="-1"
                      :aria-selected="activeSuggestionIndex === index"
                      @mouseenter="activeSuggestionIndex = index"
                      @click="chooseProduct(product)"
                    >
                      <div class="autocomplete-item-main">
                        <div class="autocomplete-item-title">
                          <strong>{{ product.canonical_name }}</strong>
                          <span class="autocomplete-brand-tag">{{ product.brand }}</span>
                        </div>
                      </div>
                      <code class="autocomplete-ref">{{ product.reference }}</code>
                    </button>
                  </template>
                </div>
              </Transition>

              <div v-if="selectedProduct" class="selected-product">
                <div>
                  <strong>{{ selectedProduct.canonical_name }}</strong>
                  <code>{{ selectedProduct.reference }}</code>
                </div>
                <button class="secondary" @click="saveCurrentProduct">Lưu mẫu</button>
              </div>
            </div>
          </div>

          <!-- Step 2: Deal info form -->
          <form class="form-card deal-card" @submit.prevent="runEvaluation">
            <div class="form-card-header">
              <div class="step-indicator">2</div>
              <div>
                <h2 class="card-title">Thông tin thương vụ</h2>
                <p class="card-subtitle">Nhập giá chào, loại tiền tệ và tình trạng thực tế từ người bán</p>
              </div>
            </div>

            <div class="form-grid">
              <label class="input-label">
                <span>Giá người bán chào</span>
                <input
                  v-model="askPrice"
                  inputmode="decimal"
                  placeholder="Ví dụ: 30000000"
                  @input="invalidateResult"
                />
              </label>

              <label class="input-label">
                <span>Tiền tệ</span>
                <select v-model="currency" @change="invalidateResult">
                  <option value="" disabled>Chọn tiền tệ</option>
                  <option value="vnd">VND</option>
                  <option value="eur">EUR</option>
                </select>
              </label>

              <label class="input-label">
                <span>Tình trạng</span>
                <select v-model="condition" @change="invalidateResult">
                  <option value="" disabled>Chọn tình trạng</option>
                  <option value="naked">Chỉ đồng hồ</option>
                  <option value="box">Có hộp</option>
                  <option value="papers">Có giấy</option>
                  <option value="fullset">Đủ bộ</option>
                </select>
              </label>
            </div>

            <p v-if="fieldError" class="inline-error" role="alert">{{ fieldError }}</p>

            <button class="primary" type="submit" :disabled="!canEvaluate">
              {{ evaluating ? 'Đang thẩm định…' : 'Thẩm định cơ hội' }}
            </button>
          </form>

          <!-- Result section -->
          <Transition name="result">
            <section
              v-if="evaluation"
              class="result-region decision-field"
              :class="{ 'signal-red': evaluation.decision.price_gap_vnd !== null && evaluation.decision.price_gap_vnd < 0 }"
              aria-live="polite"
            >
              <div class="result-top">
                <div class="verdict-group">
                  <span class="unsaved">Chưa lưu</span>
                  <span class="verdict-label">Kết luận thẩm định</span>
                  <h2>{{ verdict(evaluation.decision.verdict) }}</h2>
                </div>
                <button class="primary" @click="saveCurrentDeal">Lưu thương vụ</button>
              </div>

              <div v-if="evaluation.state === 'insufficient_data'" class="insufficient">
                <h3>Không đủ dữ liệu</h3>
                <p>Hiện có {{ evaluation.decision.sample_size }} giao dịch bán được. Không hiển thị số suy diễn.</p>
              </div>

              <template v-else>
                <!-- Visual Range Bar for decision clarity -->
                <div v-if="evaluation.decision.max_buy_price_vnd !== null && pinPositionPercent !== null" class="range-viz-container">
                  <div class="range-viz-header">
                    <span class="range-viz-title">Biên độ quyết định (The Cut Boundary)</span>
                    <span
                      class="range-status-pill"
                      :class="evaluation.decision.verdict"
                    >
                      {{
                        evaluation.decision.verdict === 'green'
                          ? 'Trong vùng an toàn'
                          : evaluation.decision.verdict === 'yellow'
                          ? 'Vùng cần thương lượng'
                          : 'Vượt trần rủi ro'
                      }}
                    </span>
                  </div>
                  <div class="range-track-wrapper">
                    <div class="range-track" aria-hidden="true">
                      <div class="range-zone safe" title="Vùng an toàn (Có thể mua)" />
                      <div class="range-zone negotiate" title="Vùng thương lượng (Cần đàm phán)" />
                      <div class="range-zone danger" title="Vùng rủi ro (Không nên mua)" />
                    </div>
                    <div
                      class="range-pin"
                      :class="evaluation.decision.verdict"
                      :style="{ left: pinPositionPercent + '%' }"
                      title="Vị trí giá chào"
                    >
                      <div class="pin-head" />
                      <div class="pin-line" />
                    </div>
                  </div>
                  <div class="range-legend">
                    <span class="legend-item safe">● Vùng an toàn</span>
                    <span class="legend-item negotiate">● Vùng thương lượng</span>
                    <span class="legend-item danger">● Vùng rủi ro</span>
                  </div>
                </div>

                <div class="decision-grid">
                  <div>
                    <span>Mức mua tối đa</span>
                    <strong>{{ money(evaluation.decision.max_buy_price_vnd) }}</strong>
                  </div>
                  <div>
                    <span>Khoảng cách với giá chào</span>
                    <strong>{{ money(evaluation.decision.price_gap_vnd) }}</strong>
                  </div>
                </div>
              </template>

              <details>
                <summary>Bằng chứng chi tiết</summary>
                <div class="metrics">
                  <div>
                    <span>Cỡ mẫu</span>
                    <strong>{{ evaluation.decision.sample_size }} / {{ evaluation.decision.attempt_count }} lô</strong>
                  </div>
                  <div>
                    <span>Sell-through</span>
                    <strong>{{ percent(evaluation.decision.sell_through_rate) }}</strong>
                  </div>
                  <div>
                    <span>Trung vị ngày bán</span>
                    <strong>{{ number(evaluation.decision.median_days_to_close) }}</strong>
                  </div>
                  <div>
                    <span>Heart-to-hammer</span>
                    <strong>{{ percent(evaluation.decision.heart_to_hammer_rate) }}</strong>
                  </div>
                </div>
                <div class="records">
                  <a
                    v-for="item in evaluation.evidence"
                    :key="item.lot_id"
                    :href="item.url"
                    target="_blank"
                    rel="noreferrer"
                  >
                    <strong>{{ item.title }}</strong>
                    <span>{{ money(item.hammer_eur, 'EUR') }} · {{ item.ended_at }}</span>
                    <AppIcon name="external" />
                  </a>
                </div>
              </details>
            </section>
          </Transition>
        </section>

        <!-- Route 2: Tracking -->
        <section v-else-if="route === '/tracking'" key="tracking" class="page list-page tracking-page">
          <header class="page-header">
            <div class="page-header-content">
              <p class="eyebrow">02 / Nội dung đã lưu</p>
              <h1>Theo dõi</h1>
              <p>Đối chiếu các quyết định đã lưu với bối cảnh dữ liệu thị trường hiện tại.</p>
            </div>
            <div class="route-context-badge" aria-hidden="true">
              <span class="context-flow">SAVED SNAPSHOT ↔ CURRENT SIGNAL</span>
              <span class="context-tag">DECISION MEMORY / LIVE CONTEXT</span>
            </div>
          </header>

          <div class="tabs" role="tablist" aria-label="Nội dung theo dõi">
            <button
              id="tracking-tab-deals"
              role="tab"
              :aria-selected="trackingTab === 'deals'"
              aria-controls="tracking-panel"
              :tabindex="trackingTab === 'deals' ? 0 : -1"
              data-tab-group="tracking"
              data-tab-index="0"
              :class="{ active: trackingTab === 'deals' }"
              @keydown="handleTabKey($event, 'tracking')"
              @click="setTab('deals')"
            >
              Thương vụ
            </button>
            <button
              id="tracking-tab-saved"
              role="tab"
              :aria-selected="trackingTab === 'saved'"
              aria-controls="tracking-panel"
              :tabindex="trackingTab === 'saved' ? 0 : -1"
              data-tab-group="tracking"
              data-tab-index="1"
              :class="{ active: trackingTab === 'saved' }"
              @keydown="handleTabKey($event, 'tracking')"
              @click="setTab('saved')"
            >
              Mẫu đã lưu
            </button>
          </div>

          <div class="toolbar">
            <label>
              <span>Tìm trong danh sách</span>
              <input v-model="trackingQuery" placeholder="Tên hoặc reference" @input="updateTrackingUrl" />
            </label>
            <button v-if="trackingQuery" class="secondary" @click="trackingQuery = ''; updateTrackingUrl()">
              Xóa tìm kiếm
            </button>
          </div>

          <div v-if="loading" class="area-state" role="status" aria-live="polite">
            <span class="inline-spinner" aria-hidden="true" />
            <span>Đang tải dữ liệu theo dõi…</span>
          </div>
          <div v-if="areaError" class="banner negative area-error" role="alert">
            <span>{{ areaError }}</span>
            <button class="secondary" type="button" @click="loadRoute">Thử lại</button>
          </div>

          <Transition name="tab" mode="out-in">
            <div :key="trackingTab" id="tracking-panel" class="records list-records" role="tabpanel" :aria-labelledby="trackingTab === 'deals' ? 'tracking-tab-deals' : 'tracking-tab-saved'" tabindex="-1">
              <template v-if="trackingTab === 'deals'">
                <button
                  v-for="deal in filteredDeals"
                  :key="deal.id"
                  @click="captureDetail($event, `deal:${deal.id}`); selectedDeal = deal"
                >
                  <div>
                    <strong>{{ deal.product.canonical_name }}</strong>
                    <code>{{ deal.product.reference }}</code>
                  </div>
                  <span>{{ money(deal.ask_price, deal.currency) }}</span>
                  <em>{{ dealStatus(deal.status) }}</em>
                </button>
              </template>

              <template v-else>
                <button
                  v-for="product in filteredSaved"
                  :key="product.product_id"
                  @click="captureDetail($event, `saved:${product.product_id}`); selectedSaved = product"
                >
                  <div>
                    <strong>{{ product.canonical_name }}</strong>
                    <code>{{ product.reference }}</code>
                  </div>
                  <span>{{ product.brand }}</span>
                  <em>Mở hồ sơ</em>
                </button>
              </template>

              <div v-if="!loading && !areaError && trackingTab === 'deals' && !filteredDeals.length" class="empty">
                {{ trackingQuery ? 'Không có thương vụ phù hợp.' : 'Chưa có thương vụ. Chỉ thương vụ bạn chủ động lưu mới xuất hiện ở đây.' }}
              </div>
              <div v-if="!loading && !areaError && trackingTab === 'saved' && !filteredSaved.length" class="empty">
                {{ trackingQuery ? 'Không có mẫu phù hợp.' : 'Chưa có mẫu đã lưu.' }}
              </div>
            </div>
          </Transition>
        </section>

        <!-- Route 3: Market -->
        <section v-else-if="route === '/market'" key="market" class="page list-page market-page">
          <header class="page-header">
            <div class="page-header-content">
              <p class="eyebrow">03 / Bối cảnh thị trường</p>
              <h1>Thị trường</h1>
              <p>Đọc tín hiệu thanh khoản và các phiên đấu giá đang diễn ra theo từng trang.</p>
            </div>
            <div class="route-context-badge" aria-hidden="true">
              <span class="context-flow">MARKET FIELD / LIVE SIGNALS</span>
              <span class="context-tag">8 RECORDS PER VIEW</span>
            </div>
          </header>

          <div class="tabs" role="tablist" aria-label="Nội dung thị trường">
            <button
              id="market-tab-liquidity"
              role="tab"
              :aria-selected="marketTab === 'liquidity'"
              aria-controls="market-panel"
              :tabindex="marketTab === 'liquidity' ? 0 : -1"
              data-tab-group="market"
              data-tab-index="0"
              :class="{ active: marketTab === 'liquidity' }"
              @keydown="handleTabKey($event, 'market')"
              @click="setTab('liquidity')"
            >
              Thanh khoản
            </button>
            <button
              id="market-tab-auctions"
              role="tab"
              :aria-selected="marketTab === 'auctions'"
              aria-controls="market-panel"
              :tabindex="marketTab === 'auctions' ? 0 : -1"
              data-tab-group="market"
              data-tab-index="1"
              :class="{ active: marketTab === 'auctions' }"
              @keydown="handleTabKey($event, 'market')"
              @click="setTab('auctions')"
            >
              Phiên đấu giá
            </button>
          </div>

          <div class="toolbar market-toolbar">
            <label>
              <span>{{ marketTab === 'liquidity' ? 'Tìm theo thương hiệu' : 'Tìm tên, reference hoặc mã lô' }}</span>
              <input v-model="marketQuery" @keyup.enter="applyMarket" />
            </label>

            <div v-if="marketTab === 'liquidity'" class="filter-row">
              <button
                v-for="item in [
                  ['all', 'Tất cả'],
                  ['improving', 'Cải thiện'],
                  ['stable', 'Ổn định'],
                  ['declining', 'Suy giảm'],
                  ['stop_buying', 'Dừng mua'],
                ]"
                :key="item[0]"
                :class="{ active: liquidityFilter === item[0] }"
                @click="liquidityFilter = item[0]; applyMarket()"
              >
                {{ item[1] }}
              </button>
            </div>

            <div v-else class="filter-row">
              <button
                v-for="item in [
                  ['all', 'Tất cả'],
                  ['open', 'Đang mở'],
                  ['waiting', 'Chờ kết quả'],
                ]"
                :key="item[0]"
                :class="{ active: auctionFilter === item[0] }"
                @click="auctionFilter = item[0]; applyMarket()"
              >
                {{ item[1] }}
              </button>
            </div>

            <button class="secondary" @click="applyMarket">Áp dụng</button>
          </div>

          <div v-if="loading" class="area-state" role="status" aria-live="polite">
            <span class="inline-spinner" aria-hidden="true" />
            <span>Đang tải dữ liệu thị trường…</span>
          </div>
          <div v-if="areaError" class="banner negative area-error" role="alert">
            <span>{{ areaError }}</span>
            <button class="secondary" type="button" @click="loadRoute">Thử lại</button>
          </div>

          <div class="record-heading" aria-hidden="true">
            <span>{{ marketTab === 'liquidity' ? 'Phân khúc / hình thức' : 'Tên lô / mã tham chiếu' }}</span>
            <span>{{ marketTab === 'liquidity' ? 'Chỉ số thanh khoản' : 'Thời điểm kết thúc' }}</span>
            <span>Tín hiệu</span>
          </div>

          <Transition name="tab" mode="out-in">
            <div :key="marketTab" id="market-panel" class="records list-records" role="tabpanel" :aria-labelledby="marketTab === 'liquidity' ? 'market-tab-liquidity' : 'market-tab-auctions'" tabindex="-1">
              <template v-if="marketTab === 'liquidity'">
                <button
                  v-for="row in liquidityRows"
                  :key="`${row.brand}:${row.form}`"
                  @click="captureDetail($event, `liquidity:${row.brand}|${row.form}`); selectedLiquidity = row"
                >
                  <div>
                    <strong>{{ row.brand }}</strong>
                    <code>{{ formLabel(row.form) }}</code>
                  </div>
                  <span><small class="mobile-record-label">Chỉ số thanh khoản</small>{{ row.index === null ? 'Không đủ dữ liệu' : number(row.index) }}</span>
                  <em><small class="mobile-record-label">Tín hiệu</small>{{ trend(row.status, row.stop_buying) }}</em>
                </button>
              </template>

              <template v-else>
                <button
                  class="auction-lot-card"
                  v-for="lot in auctionLots"
                  :key="lot.lot_id"
                  @click="captureDetail($event, `auction:${lot.lot_id}`); selectedAuction = lot"
                >
                  <div class="auction-lot-cover">
                    <img v-if="lot.cover.url" :src="lot.cover.url" :alt="`Ảnh bìa của lô ${lot.title}`" />
                    <span v-else class="auction-lot-cover-state" role="status">{{ coverStateLabel(lot.cover.state) }}</span>
                  </div>
                  <div class="auction-lot-summary">
                    <strong>{{ lot.title }}</strong>
                    <code>{{ lot.lot_id }}</code>
                  </div>
                  <span class="auction-lot-end"><small class="mobile-record-label">Thời điểm kết thúc</small>{{ dateTime(lot.bidding_end_at) }}</span>
                  <em><small class="mobile-record-label">Trạng thái</small>{{ lot.status === 'open' ? 'Đang mở' : 'Chờ kết quả' }}</em>
                </button>
              </template>

              <div v-if="!loading && !areaError && marketTab === 'liquidity' && !liquidityRows.length" class="empty">
                <template v-if="marketHasFilters">
                  <span>Không có phân khúc phù hợp với tìm kiếm và bộ lọc hiện tại.</span>
                  <button class="secondary" type="button" @click="clearMarketFilters">Xóa tìm kiếm và bộ lọc</button>
                </template>
                <span v-else>{{ freshness?.status === 'no_data' ? 'Chưa có dữ liệu thị trường.' : 'Chưa có phân khúc thanh khoản.' }}</span>
              </div>
              <div v-if="!loading && !areaError && marketTab === 'auctions' && !auctionLots.length" class="empty">
                <template v-if="marketHasFilters">
                  <span>Không có lô phù hợp với tìm kiếm và bộ lọc hiện tại.</span>
                  <button class="secondary" type="button" @click="clearMarketFilters">Xóa tìm kiếm và bộ lọc</button>
                </template>
                <span v-else>{{ freshness?.status === 'no_data' ? 'Chưa có dữ liệu thị trường.' : 'Chưa có phiên đấu giá.' }}</span>
              </div>
            </div>
          </Transition>

          <nav v-if="marketPageCount > 1" class="pagination" aria-label="Phân trang thị trường">
            <button
              class="page-button"
              :disabled="marketPage === 1"
              aria-label="Trang trước"
              @click="setMarketPage(marketPage - 1)"
            >
              <AppIcon name="previous" />
              <span>Trước</span>
            </button>
            <span class="page-summary" aria-live="polite">
              Trang {{ marketPage }} / {{ marketPageCount }} · {{ marketTotalLabel }}
            </span>
            <button
              class="page-button"
              :disabled="marketPage === marketPageCount"
              aria-label="Trang sau"
              @click="setMarketPage(marketPage + 1)"
            >
              <span>Sau</span>
              <AppIcon name="next" />
            </button>
          </nav>
        </section>
        <PricingSettingsPage v-else key="settings" @applied="onPricingApplied" @dirty-change="onPricingDraftDirty" />
      </Transition>
    </main>

    <!-- Side Detail Drawer -->
    <Transition name="panel">
      <aside
        v-if="selectedDeal || selectedSaved || selectedLiquidity || selectedAuction"
        ref="detailPanel"
        tabindex="-1"
        class="detail-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="detail-panel-title"
      >
        <div class="detail-heading">
          <button class="back-button" @click="userCloseDetail">
            <AppIcon name="back" />
            <span>Đóng</span>
          </button>
          <span>Chi tiết</span>
        </div>

        <template v-if="selectedDeal">
          <p class="eyebrow">Thương vụ #{{ selectedDeal.id }}</p>
          <h2 id="detail-panel-title" ref="detailTitle" tabindex="-1">{{ selectedDeal.product.canonical_name }}</h2>
          <code>{{ selectedDeal.product.reference }}</code>
          <dl>
            <dt>Trạng thái</dt>
            <dd>{{ dealStatus(selectedDeal.status) }}</dd>
            <dt>Giá chào lúc lưu</dt>
            <dd>{{ money(selectedDeal.ask_price, selectedDeal.currency) }}</dd>
            <dt>Tình trạng</dt>
            <dd>{{ conditionLabel(selectedDeal.condition) }}</dd>
            <dt>Kết luận lúc lưu</dt>
            <dd>{{ verdict(String(snapshotDecision(selectedDeal).verdict || 'insufficient_data')) }}</dd>
            <dt>Mức mua tối đa lúc lưu</dt>
            <dd>{{ money(typeof snapshotDecision(selectedDeal).max_buy_price_vnd === 'number' ? Number(snapshotDecision(selectedDeal).max_buy_price_vnd) : null) }}</dd>
            <dt>Dữ liệu thị trường hiện tại</dt>
            <dd>{{ freshnessLabel(freshness?.status) }} · {{ dateTime(freshness?.last_updated_at || null) }}</dd>
          </dl>
          <div v-if="selectedDeal.status === 'considering'" class="panel-actions">
            <button class="primary" @click="changeDealStatus(selectedDeal, 'purchased')">Đã mua</button>
            <button class="secondary" @click="changeDealStatus(selectedDeal, 'skipped')">Đã bỏ qua</button>
          </div>
        </template>

        <template v-else-if="selectedSaved">
          <p class="eyebrow">Mẫu đã lưu</p>
          <h2 id="detail-panel-title" ref="detailTitle" tabindex="-1">{{ selectedSaved.canonical_name }}</h2>
          <code>{{ selectedSaved.reference }}</code>
          <dl>
            <dt>Thương hiệu</dt>
            <dd>{{ selectedSaved.brand }}</dd>
            <dt>Dữ liệu thị trường mới nhất</dt>
            <dd>{{ freshnessLabel(freshness?.status) }} · {{ dateTime(freshness?.last_updated_at || null) }}</dd>
            <dt>Nguồn định danh</dt>
            <dd>{{ selectedSaved.provenance }}</dd>
          </dl>
          <div class="panel-actions">
            <button class="primary" @click="assessProduct(selectedSaved)">Bắt đầu thẩm định</button>
            <button class="secondary" @click="unsave(selectedSaved)">Bỏ lưu</button>
          </div>
        </template>

        <template v-else-if="selectedLiquidity">
          <p class="eyebrow">Phân khúc</p>
          <h2 id="detail-panel-title" ref="detailTitle" tabindex="-1">{{ selectedLiquidity.brand }} · {{ formLabel(selectedLiquidity.form) }}</h2>
          <dl>
            <dt>Trạng thái</dt>
            <dd>{{ trend(selectedLiquidity.status, selectedLiquidity.stop_buying) }}</dd>
            <dt>Liquidity Index</dt>
            <dd>{{ number(selectedLiquidity.index) }}</dd>
            <dt>Thay đổi quý gần nhất</dt>
            <dd>{{ percent(selectedLiquidity.latest_qoq_change) }}</dd>
            <dt>Sell-through</dt>
            <dd>{{ percent(selectedLiquidity.sell_through) }}</dd>
            <dt>Median days</dt>
            <dd>{{ number(selectedLiquidity.median_days_to_close) }}</dd>
            <dt>Heart-to-hammer</dt>
            <dd>{{ percent(selectedLiquidity.heart_to_hammer) }}</dd>
            <dt>Cỡ mẫu</dt>
            <dd>{{ selectedLiquidity.lots }} lô</dd>
            <dt>Khoảng dữ liệu</dt>
            <dd>{{ dateOnly(selectedLiquidity.window_start) }} – {{ dateOnly(selectedLiquidity.window_end) }}</dd>
          </dl>
          <p v-if="selectedLiquidity.data_state === 'insufficient_data'" class="banner warning">
            Không đủ cỡ mẫu để đưa ra tín hiệu.
          </p>
        </template>

        <template v-else-if="selectedAuction">
          <p class="eyebrow">Lô {{ selectedAuction.lot_id }}</p>
          <h2 id="detail-panel-title" ref="detailTitle" tabindex="-1">{{ selectedAuction.title }}</h2>
          <div class="auction-lot-cover auction-lot-cover--detail">
            <img v-if="selectedAuction.cover.url" :src="selectedAuction.cover.url" :alt="`Ảnh bìa của lô ${selectedAuction.title}`" />
            <span v-else class="auction-lot-cover-state" role="status">{{ coverStateLabel(selectedAuction.cover.state) }}</span>
          </div>
          <p>{{ selectedAuction.subtitle || 'Không có mô tả bổ sung' }}</p>
          <dl>
            <dt>Trạng thái</dt>
            <dd>{{ selectedAuction.status === 'open' ? 'Đang mở' : 'Chờ kết quả' }}</dd>
            <dt>Kết thúc dự kiến</dt>
            <dd>{{ dateTime(selectedAuction.bidding_end_at) }}</dd>
            <dt>Nguồn</dt>
            <dd>{{ selectedAuction.source }}</dd>
          </dl>
          <div class="panel-actions">
            <a class="primary" :href="selectedAuction.url" target="_blank" rel="noreferrer">
              Xem nguồn <AppIcon name="external" />
            </a>
            <button class="secondary" @click="assessLot(selectedAuction)">
              <AppIcon name="transfer" />
              <span>Đưa sang Thẩm định</span>
            </button>
          </div>
        </template>
      </aside>
    </Transition>

    <Transition name="toast">
      <div v-if="toast" class="toast" role="status">{{ toast }}</div>
    </Transition>

    <nav class="bottom-nav" aria-label="Điều hướng di động" :inert="detailOpen">
      <button
        :class="{ active: route === '/assessment' }"
        :aria-current="route === '/assessment' ? 'page' : undefined"
        @click="navigate('/assessment')"
      >
        <AppIcon name="assessment" />
        <span>Thẩm định</span>
      </button>
      <button
        :class="{ active: route === '/tracking' }"
        :aria-current="route === '/tracking' ? 'page' : undefined"
        @click="navigate('/tracking')"
      >
        <AppIcon name="tracking" />
        <span>Theo dõi</span>
      </button>
      <button
        :class="{ active: route === '/market' }"
        :aria-current="route === '/market' ? 'page' : undefined"
        @click="navigate('/market')"
      >
        <AppIcon name="market" />
        <span>Thị trường</span>
      </button>
      <button
        :class="{ active: route === '/settings' }"
        :aria-current="route === '/settings' ? 'page' : undefined"
        @click="navigate('/settings')"
      >
        <AppIcon name="settings" />
        <span>Cấu hình</span>
      </button>
    </nav>
  </div>
</template>
