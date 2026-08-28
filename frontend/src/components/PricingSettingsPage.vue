<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { api } from '../api'
import type {
  PricingActiveConfig,
  PricingDraft,
  PricingError,
  PricingHelper,
  PricingParameter,
  PricingPreviewResponse,
  PricingUnit,
} from '../types'

type EditableParameter = {
  name: string
  value: number | null
  valueText: string
  unit: PricingUnit | ''
  required: boolean
  removable: boolean
}
type EditableDraft = {
  parameters: EditableParameter[]
  helpers: PricingHelper[]
  formulas: { net_proceeds: string; profit_threshold: string }
}
type ApiError = Error & { status?: number; payload?: unknown }

const unitOptions: { value: PricingUnit; label: string }[] = [
  { value: 'eur', label: 'EUR · tiền' },
  { value: 'rate', label: 'Tỷ lệ · số thập phân' },
  { value: 'vnd_per_eur', label: 'VND / EUR' },
]
const customUnitOptions = unitOptions.filter((option) => option.value !== 'vnd_per_eur')
const unitLabel = (unit: string): string => unitOptions.find((option) => option.value === unit)?.label || unit

const emit = defineEmits<{ applied: []; 'dirty-change': [dirty: boolean] }>()

const active = ref<PricingActiveConfig | null>(null)
const draft = ref<EditableDraft>({ parameters: [], helpers: [], formulas: { net_proceeds: '', profit_threshold: '' } })
const revision = ref('')
const loading = ref(true)
const loadError = ref('')
const staleRevision = ref(false)
const hammerInput = ref('')
const costInput = ref('')
const previewResult = ref<PricingPreviewResponse | null>(null)
const previewErrors = ref<PricingError[]>([])
const applyErrors = ref<PricingError[]>([])
const formMessage = ref('')
const previewing = ref(false)
const applying = ref(false)
const previewApprovalKey = ref<string | null>(null)
const baselineDraftKey = ref('')
let previewSequence = 0

const hasConfig = computed(() => active.value !== null)
const hasUnsavedDraft = computed(() => Boolean(baselineDraftKey.value) && editableStateKey() !== baselineDraftKey.value)
const allErrors = computed(() => [...previewErrors.value, ...applyErrors.value])
const canApply = computed(() =>
  !previewing.value && !applying.value && !staleRevision.value &&
  Boolean(previewResult.value?.valid && previewResult.value.preview && previewApprovalKey.value === currentKey())
)

function editableParameter(parameter: PricingParameter): EditableParameter {
  return {
    name: parameter.name,
    value: parameter.value,
    valueText: String(parameter.value),
    unit: parameter.unit,
    required: parameter.required,
    removable: parameter.removable,
  }
}

function setActiveConfig(config: PricingActiveConfig): void {
  active.value = config
  revision.value = config.revision
  draft.value = {
    parameters: config.parameters.map(editableParameter),
    helpers: config.helpers.map((helper) => ({ ...helper })),
    formulas: { ...config.formulas },
  }
  baselineDraftKey.value = editableStateKey()
  previewResult.value = null
  previewErrors.value = []
  applyErrors.value = []
  formMessage.value = ''
  staleRevision.value = false
  previewApprovalKey.value = null
}

async function loadConfig(): Promise<void> {
  loading.value = true
  loadError.value = ''
  try {
    const response = await api.pricingConfig()
    setActiveConfig(response.active)
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : 'Không tải được cấu hình tính toán.'
  } finally {
    loading.value = false
  }
}

function toFiniteValue(value: string): number | null {
  if (!value.trim()) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function updateParameterValue(parameter: EditableParameter, event: Event): void {
  const text = (event.target as HTMLInputElement).value
  parameter.valueText = text
  parameter.value = toFiniteValue(text)
}

function addParameter(): void {
  draft.value.parameters.push({ name: '', value: null, valueText: '', unit: '', required: false, removable: true })
}

function removeParameter(index: number): void {
  const parameter = draft.value.parameters[index]
  if (!parameter || !parameter.removable) return
  if (typeof window !== 'undefined' && !window.confirm(`Xoá tham số "${parameter.name || 'chưa đặt tên'}" khỏi bản nháp? Nếu công thức đang dùng, Preview sẽ báo lỗi tham chiếu.`)) return
  draft.value.parameters.splice(index, 1)
}

function addHelper(): void {
  draft.value.helpers.push({ name: '', expression: '' })
}

function removeHelper(index: number): void {
  const helper = draft.value.helpers[index]
  if (!helper) return
  if (typeof window !== 'undefined' && !window.confirm(`Xoá helper "${helper.name || 'chưa đặt tên'}" khỏi bản nháp? Nếu công thức đang dùng, Preview sẽ báo lỗi tham chiếu.`)) return
  draft.value.helpers.splice(index, 1)
}

function buildDraft(): { draft: PricingDraft; errors: PricingError[] } {
  const errors: PricingError[] = []
  const parameters: PricingDraft['parameters'] = []
  draft.value.parameters.forEach((parameter, index) => {
    const field = `parameters[${index}]`
    if (!parameter.name.trim()) errors.push({ field: `${field}.name`, code: 'missing_name', message: 'Tên tham số không được để trống.' })
    if (!parameter.unit) errors.push({ field: `${field}.unit`, code: 'missing_unit', message: 'Chọn đơn vị cho tham số.' })
    if (parameter.value === null || !Number.isFinite(parameter.value)) {
      errors.push({ field: `${field}.value`, code: 'invalid_number', message: 'Nhập một số hữu hạn, không để trống.' })
    }
    if (parameter.name.trim() && parameter.unit && parameter.value !== null && Number.isFinite(parameter.value)) {
      parameters.push({ name: parameter.name.trim(), value: parameter.value, unit: parameter.unit })
    }
  })
  draft.value.helpers.forEach((helper, index) => {
    if (!helper.name.trim()) errors.push({ field: `helpers[${index}].name`, code: 'missing_name', message: 'Tên helper không được để trống.' })
    if (!helper.expression.trim()) errors.push({ field: `helpers[${index}].expression`, code: 'missing_expression', message: 'Nhập biểu thức cho helper.' })
  })
  if (!draft.value.formulas.net_proceeds.trim()) errors.push({ field: 'formulas.net_proceeds', code: 'missing_expression', message: 'Công thức bắt buộc không được để trống.' })
  if (!draft.value.formulas.profit_threshold.trim()) errors.push({ field: 'formulas.profit_threshold', code: 'missing_expression', message: 'Công thức bắt buộc không được để trống.' })
  return {
    draft: {
      parameters,
      helpers: draft.value.helpers.map((helper) => ({ name: helper.name.trim(), expression: helper.expression.trim() })),
      formulas: {
        net_proceeds: draft.value.formulas.net_proceeds.trim(),
        profit_threshold: draft.value.formulas.profit_threshold.trim(),
      },
    },
    errors,
  }
}

function inputValue(text: string, field: string, errors: PricingError[]): number | null {
  const value = toFiniteValue(text)
  if (value === null) errors.push({ field: `inputs.${field}`, code: 'invalid_number', message: 'Nhập một số hữu hạn để chạy thử.' })
  return value
}

function currentKey(): string {
  const built = buildDraft()
  return JSON.stringify({ draft: built.draft, hammer_eur: hammerInput.value, cost_eur: costInput.value, revision: revision.value })
}

function editableStateKey(): string {
  return JSON.stringify({
    parameters: draft.value.parameters.map(({ name, valueText, unit }) => ({ name, valueText, unit })),
    helpers: draft.value.helpers,
    formulas: draft.value.formulas,
  })
}

function structuredErrors(error: ApiError): PricingError[] {
  const payload = error.payload
  if (!payload || typeof payload !== 'object') return []
  const errors = (payload as { errors?: unknown }).errors
  if (!Array.isArray(errors)) return []
  return errors.filter((item): item is PricingError => {
    if (!item || typeof item !== 'object') return false
    const value = item as Record<string, unknown>
    return typeof value.field === 'string' && typeof value.code === 'string' && typeof value.message === 'string'
  })
}

async function preview(): Promise<void> {
  const sequence = ++previewSequence
  previewResult.value = null
  previewErrors.value = []
  applyErrors.value = []
  formMessage.value = ''
  previewApprovalKey.value = null
  const built = buildDraft()
  const inputErrors: PricingError[] = []
  const hammer = inputValue(hammerInput.value, 'hammer_eur', inputErrors)
  const cost = inputValue(costInput.value, 'cost_eur', inputErrors)
  if (built.errors.length || inputErrors.length || hammer === null || cost === null) {
    previewErrors.value = [...built.errors, ...inputErrors]
    return
  }
  previewing.value = true
  try {
    const result = await api.previewPricingConfig({ draft: built.draft, inputs: { hammer_eur: hammer, cost_eur: cost } })
    if (sequence !== previewSequence) return
    previewResult.value = result
    if (result.active_revision !== revision.value) {
      staleRevision.value = true
      previewErrors.value = [{ field: 'revision', code: 'stale_revision', message: 'Cấu hình đã thay đổi. Hãy tải lại trước khi áp dụng.' }]
    } else {
      previewErrors.value = result.errors
      if (result.valid && result.preview) previewApprovalKey.value = currentKey()
    }
  } catch (error) {
    if (sequence !== previewSequence) return
    previewErrors.value = structuredErrors(error as ApiError)
    if (!previewErrors.value.length) formMessage.value = error instanceof Error ? error.message : 'Không thể chạy thử cấu hình.'
  } finally {
    if (sequence === previewSequence) previewing.value = false
  }
}

async function apply(): Promise<void> {
  applyErrors.value = []
  formMessage.value = ''
  if (staleRevision.value) {
    formMessage.value = 'Cấu hình đã có phiên bản mới. Hãy tải lại rồi xem lại thay đổi trước khi áp dụng.'
    return
  }
  const built = buildDraft()
  if (built.errors.length) {
    applyErrors.value = built.errors
    return
  }
  if (!canApply.value) {
    formMessage.value = 'Hãy chạy Preview thành công cho đúng bản nháp và dữ liệu mẫu trước khi áp dụng.'
    return
  }
  applying.value = true
  try {
    const response = await api.applyPricingConfig({ expected_revision: revision.value, draft: built.draft })
    setActiveConfig(response.active)
    await nextTick()
    formMessage.value = 'Đã áp dụng cấu hình tính toán mới.'
    emit('applied')
  } catch (error) {
    const typedErrors = structuredErrors(error as ApiError)
    if ((error as ApiError).status === 409) {
      staleRevision.value = true
      formMessage.value = 'Cấu hình đã có phiên bản mới. Hãy tải lại rồi xem lại thay đổi.'
    } else if (typedErrors.length) {
      applyErrors.value = typedErrors
    } else {
      formMessage.value = error instanceof Error ? error.message : 'Không thể áp dụng cấu hình.'
    }
  } finally {
    applying.value = false
  }
}

function reload(): void {
  void loadConfig()
}

function outputByName(name: string) {
  return previewResult.value?.preview?.active_outputs.find((output) => output.name === name)
}

function guardBeforeUnload(event: BeforeUnloadEvent): void {
  if (!hasUnsavedDraft.value) return
  event.preventDefault()
  event.returnValue = ''
}

watch([draft, hammerInput, costInput], () => {
  previewSequence += 1
  previewResult.value = null
  previewErrors.value = []
  applyErrors.value = []
  formMessage.value = ''
  previewApprovalKey.value = null
}, { deep: true })

watch(hasUnsavedDraft, (dirty) => {
  emit('dirty-change', dirty)
}, { immediate: true })

onMounted(() => {
  void loadConfig()
  window.addEventListener('beforeunload', guardBeforeUnload)
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', guardBeforeUnload)
  emit('dirty-change', false)
})
</script>

<template>
  <section class="page settings-page">
    <header class="page-header">
      <div class="page-header-content">
        <p class="eyebrow">04 / Vận hành pricing</p>
        <h1>Cấu hình tính toán</h1>
        <p>Điều chỉnh tham số và công thức pricing, chạy thử với dữ liệu mẫu rồi mới áp dụng cấu hình mới.</p>
      </div>
      <div v-if="active" class="route-context-badge" aria-label="Phiên bản cấu hình hiện tại">
        <span class="context-flow">REVISION / {{ active.revision }}</span>
        <span class="context-tag">{{ active.source === 'env-derived' ? 'ENV-DERIVED / CHƯA LƯU' : 'PROFILE ACTIVE' }}</span>
      </div>
    </header>

    <div v-if="loading" class="form-card settings-state" role="status">Đang tải cấu hình tính toán…</div>
    <div v-else-if="loadError" class="banner negative" role="alert">
      {{ loadError }}
      <button class="secondary" type="button" @click="reload">Thử lại</button>
    </div>

    <template v-else-if="hasConfig">
      <div v-if="staleRevision" class="banner warning" role="alert">
        Cấu hình active đã đổi trong lúc bạn đang sửa. Bản nháp này chưa được áp dụng.
        <button class="secondary" type="button" @click="reload">Tải cấu hình mới</button>
      </div>
      <div v-if="formMessage" class="banner" :class="{ positive: formMessage.startsWith('Đã áp dụng') }" role="status">{{ formMessage }}</div>

      <section class="form-card settings-card" aria-labelledby="parameters-title">
        <div class="form-card-header">
          <div class="step-indicator">1</div>
          <div>
            <h2 id="parameters-title" class="card-title">Tham số</h2>
            <p class="card-subtitle">Mỗi giá trị phải có đúng đơn vị. Tỷ lệ dùng dạng thập phân, ví dụ 0,05 = 5%.</p>
          </div>
        </div>
        <div class="settings-rows">
          <div v-for="(parameter, index) in draft.parameters" :key="`parameter-${index}`" class="settings-row">
            <label class="input-label">
              <span>Tên tham số <span v-if="parameter.required" class="required-mark" aria-label="bắt buộc">*</span></span>
              <input v-model="parameter.name" :aria-label="`Tên tham số ${index + 1}`" :readonly="parameter.required" :class="{ readonly: parameter.required }" />
            </label>
            <label class="input-label">
              <span>Giá trị</span>
              <input
                :value="parameter.valueText"
                inputmode="decimal"
                :aria-label="`Giá trị ${parameter.name || index + 1}`"
                @input="updateParameterValue(parameter, $event)"
              />
            </label>
            <label class="input-label">
              <span>Đơn vị</span>
              <select v-model="parameter.unit" :aria-label="`Đơn vị ${parameter.name || index + 1}`" :disabled="parameter.required">
                <option value="" disabled>Chọn đơn vị</option>
                <option v-for="option in (parameter.removable ? customUnitOptions : unitOptions)" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </label>
            <button v-if="parameter.removable" class="icon-action" type="button" :aria-label="`Xoá tham số ${parameter.name || index + 1}`" @click="removeParameter(index)">×</button>
            <span v-else class="required-copy">Bắt buộc</span>
          </div>
        </div>
        <button class="secondary add-button" type="button" @click="addParameter">+ Thêm tham số</button>
        <p class="settings-hint">Tham số tiền dùng EUR; tỷ lệ dùng số thập phân (ví dụ 0,1 = 10%); tỷ giá VND / EUR chỉ thuộc cấu hình FX bắt buộc. Tên biến dùng snake_case.</p>
      </section>

      <section class="form-card settings-card" aria-labelledby="helpers-title">
        <div class="form-card-header">
          <div class="step-indicator">2</div>
          <div>
            <h2 id="helpers-title" class="card-title">Helper formulas</h2>
            <p class="card-subtitle">Helper có thể dùng tham số, input hệ thống hoặc helper khác; backend sẽ kiểm tra DAG, đơn vị và điều kiện nghịch đảo.</p>
          </div>
        </div>
        <div v-if="!draft.helpers.length" class="settings-empty">Chưa có helper. Bạn có thể thêm helper để chia nhỏ công thức.</div>
        <div v-for="(helper, index) in draft.helpers" :key="`helper-${index}`" class="helper-row">
          <label class="input-label">
            <span>Tên helper</span>
            <input v-model="helper.name" :aria-label="`Tên helper ${index + 1}`" />
          </label>
          <label class="input-label expression-field">
            <span>Biểu thức</span>
            <input v-model="helper.expression" class="formula-input" :aria-label="`Biểu thức helper ${index + 1}`" />
          </label>
          <button class="icon-action" type="button" :aria-label="`Xoá helper ${helper.name || index + 1}`" @click="removeHelper(index)">×</button>
        </div>
        <button class="secondary add-button" type="button" @click="addHelper">+ Thêm helper</button>
      </section>

      <section class="form-card settings-card" aria-labelledby="formulas-title">
        <div class="form-card-header">
          <div class="step-indicator">3</div>
          <div>
            <h2 id="formulas-title" class="card-title">Công thức bắt buộc</h2>
            <p class="card-subtitle">Chỉ hỗ trợ +, -, *, /, ngoặc, min() và max(). Backend sẽ kiểm tra đơn vị và điều kiện giá nghịch đảo.</p>
          </div>
        </div>
        <div class="formula-list">
          <label class="input-label">
            <span>net_proceeds <code>→ EUR</code></span>
            <textarea v-model="draft.formulas.net_proceeds" rows="2" spellcheck="false" aria-label="Công thức net proceeds" />
          </label>
          <label class="input-label">
            <span>profit_threshold <code>→ EUR</code></span>
            <textarea v-model="draft.formulas.profit_threshold" rows="2" spellcheck="false" aria-label="Công thức profit threshold" />
          </label>
        </div>
        <div class="allowed-variables">
          <span class="settings-hint">Biến hệ thống được phép:</span>
          <code v-for="variable in active?.input_variables" :key="variable.name" :title="`${variable.source || 'system'} · ${unitLabel(variable.unit)}`">{{ variable.name }}</code>
        </div>
      </section>

      <section class="form-card settings-card" aria-labelledby="preview-title">
        <div class="form-card-header">
          <div class="step-indicator">4</div>
          <div>
            <h2 id="preview-title" class="card-title">Chạy thử trước khi áp dụng</h2>
            <p class="card-subtitle">Nhập dữ liệu mẫu hữu hạn. Giá trị hiển thị bên dưới do backend trả về.</p>
          </div>
        </div>
        <p v-if="hasUnsavedDraft" class="settings-hint" role="status">Bản nháp chưa áp dụng. Nếu rời trang, trình duyệt sẽ hỏi trước khi đóng hoặc tải lại.</p>
        <div class="sample-grid">
          <label class="input-label">
            <span>hammer_eur</span>
            <input v-model="hammerInput" inputmode="decimal" placeholder="Ví dụ: 1200" />
          </label>
          <label class="input-label">
            <span>cost_eur</span>
            <input v-model="costInput" inputmode="decimal" placeholder="Ví dụ: 800" />
          </label>
        </div>
        <div class="settings-actions">
          <button class="secondary" type="button" :disabled="previewing || applying" @click="preview">{{ previewing ? 'Đang chạy thử…' : 'Preview' }}</button>
          <button class="primary" type="button" :disabled="!canApply" @click="apply">{{ applying ? 'Đang áp dụng…' : 'Apply cấu hình' }}</button>
        </div>
        <div v-if="allErrors.length" class="settings-errors" role="alert">
          <p v-for="error in allErrors" :key="`${error.field}-${error.code}-${error.message}`" class="inline-error"><code>{{ error.code }}</code> · {{ error.field }}: {{ error.message }}</p>
        </div>
        <div v-if="previewResult?.preview" class="preview-results" aria-live="polite">
          <div class="preview-result-heading">
            <span>Kết quả preview</span>
            <span>Kết quả active</span>
          </div>
          <div v-for="output in previewResult.preview.outputs" :key="output.name" class="preview-row">
            <span><strong>{{ output.label }}</strong><code>{{ output.name }}</code></span>
            <strong>{{ output.formatted }}</strong>
            <strong>{{ outputByName(output.name)?.formatted || 'Không đủ dữ liệu' }}</strong>
          </div>
        </div>
      </section>
    </template>
  </section>
</template>

<style scoped>
.settings-page {
  max-width: 1080px;
}

.settings-state {
  color: var(--muted);
}

.settings-page .banner .secondary {
  min-height: 36px;
  margin: 10px 0 0;
  padding-block: 5px;
}

.settings-card {
  padding: 26px 30px;
}

.settings-rows {
  display: grid;
  gap: 12px;
}

.settings-row,
.helper-row {
  display: grid;
  grid-template-columns: minmax(150px, 1fr) minmax(130px, 0.7fr) minmax(150px, 0.9fr) auto;
  gap: 12px;
  align-items: end;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--rule-subtle);
}

.helper-row {
  grid-template-columns: minmax(150px, 0.7fr) minmax(220px, 1.6fr) auto;
}

.input-label .readonly,
.input-label input:read-only {
  color: var(--muted);
  background: var(--surface-muted);
}

.required-mark {
  color: var(--signal);
}

.required-copy {
  padding: 0 4px 13px;
  color: var(--subtle);
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.72rem;
  white-space: nowrap;
}

.icon-action {
  width: 42px;
  height: 42px;
  border: 1px solid var(--rule);
  border-radius: 7px;
  color: var(--muted);
  background: var(--surface);
  font-size: 1.4rem;
  line-height: 1;
  cursor: pointer;
}

.icon-action:hover {
  border-color: var(--signal);
  color: var(--signal);
  background: var(--surface-negative);
}

.add-button {
  margin-top: 18px;
}

.settings-hint {
  margin: 14px 0 0;
  color: var(--muted);
  font-size: 0.8rem;
}

.settings-empty {
  padding: 14px 16px;
  border: 1px dashed var(--rule-strong);
  border-radius: 7px;
  color: var(--muted);
  font-size: 0.85rem;
}

.formula-list {
  display: grid;
  gap: 16px;
}

textarea {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid var(--rule);
  border-radius: 7px;
  color: var(--ink);
  background: var(--surface);
  font: 0.92rem/1.5 'IBM Plex Mono', monospace;
  resize: vertical;
}

textarea:focus {
  border-color: var(--cobalt);
  box-shadow: 0 0 0 3px var(--cobalt-soft);
  outline: 0;
}

.allowed-variables {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 18px;
}

.allowed-variables code {
  padding: 4px 7px;
  border-radius: 4px;
  background: var(--surface-muted);
}

.sample-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.settings-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 22px;
}

.settings-errors {
  margin-top: 18px;
  padding: 10px 14px;
  border-left: 3px solid var(--signal);
  border-radius: 0 7px 7px 0;
  background: var(--surface-negative);
}

.settings-errors .inline-error {
  margin: 5px 0;
}

.preview-results {
  margin-top: 24px;
  overflow: hidden;
  border: 1px solid var(--rule);
  border-radius: 8px;
}

.preview-result-heading,
.preview-row {
  display: grid;
  grid-template-columns: minmax(190px, 1.4fr) minmax(130px, 1fr) minmax(130px, 1fr);
  gap: 14px;
  align-items: center;
  padding: 12px 14px;
}

.preview-result-heading {
  color: var(--muted);
  background: var(--surface-muted);
  font-size: 0.78rem;
  font-weight: 600;
}

.preview-result-heading span:first-child {
  grid-column: 2;
}

.preview-row {
  border-top: 1px solid var(--rule-subtle);
}

.preview-row span {
  display: grid;
  gap: 3px;
}

.preview-row strong:not(:first-child) {
  text-align: right;
}

@media (max-width: 767px) {
  .settings-card {
    padding: 20px 18px;
  }

  .settings-row,
  .helper-row,
  .sample-grid {
    grid-template-columns: 1fr;
  }

  .settings-row .icon-action,
  .helper-row .icon-action {
    width: 100%;
  }

  .required-copy {
    padding: 0;
  }

  .settings-actions {
    display: grid;
    grid-template-columns: 1fr;
  }

  .settings-actions button {
    width: 100%;
  }

  .preview-result-heading,
  .preview-row {
    grid-template-columns: minmax(0, 1fr) minmax(110px, 0.8fr);
  }

  .preview-result-heading span:first-child {
    grid-column: auto;
  }

  .preview-result-heading span:last-child {
    text-align: right;
  }

  .preview-row span {
    grid-column: 1 / -1;
  }

  .preview-row > strong {
    text-align: left !important;
  }
}
</style>
