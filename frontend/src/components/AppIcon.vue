<script setup lang="ts">
type IconName =
  | 'assessment'
  | 'tracking'
  | 'market'
  | 'settings'
  | 'previous'
  | 'next'
  | 'close'
  | 'back'
  | 'external'
  | 'transfer'
  | 'clock'
  | 'sun'
  | 'moon'
  | 'cuti-mark'
  | 'search'
  | 'check'
  | 'arrow-right'

defineProps<{
  name: IconName
}>()
</script>

<template>
  <svg
    class="app-icon"
    viewBox="0 0 24 24"
    width="24"
    height="24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <template v-if="name === 'cuti-mark'">
      <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.6" />
      <path d="M15 9l-6 6" stroke="var(--cobalt)" stroke-width="2.2" />
      <circle cx="9" cy="9" r="1.5" fill="currentColor" />
      <circle cx="15" cy="15" r="1.5" fill="var(--cobalt)" />
    </template>
    <template v-else-if="name === 'assessment'">
      <circle cx="12" cy="12" r="6" />
      <path d="M12 2v4M12 18v4M2 12h4M18 12h4" />
    </template>
    <template v-else-if="name === 'tracking'">
      <path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6z" />
      <path d="M8 10h8M8 14h5" />
    </template>
    <template v-else-if="name === 'market'">
      <path d="M3 20h18M4 16l5-6 4 3 7-8" />
    </template>
    <template v-else-if="name === 'settings'">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-1.7 1.7-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V20h-2.4v-.2a1.7 1.7 0 0 0-1.03-1.56 1.7 1.7 0 0 0-1.88.34l-.06.06-1.7-1.7.06-.06A1.7 1.7 0 0 0 8.46 15a1.7 1.7 0 0 0-1.56-1.03H6v-2.4h.9a1.7 1.7 0 0 0 1.56-1.03 1.7 1.7 0 0 0-.34-1.88l-.06-.06 1.7-1.7.06.06a1.7 1.7 0 0 0 1.88.34A1.7 1.7 0 0 0 12.73 5.7V5h2.4v.7a1.7 1.7 0 0 0 1.03 1.56 1.7 1.7 0 0 0 1.88-.34l.06-.06 1.7 1.7-.06.06A1.7 1.7 0 0 0 19.4 10c.17.4.55.67 1.03.67H21v2.4h-.57c-.48 0-.86.27-1.03.67Z" />
    </template>
    <template v-else-if="name === 'previous'">
      <path d="m15 18-6-6 6-6" />
    </template>
    <template v-else-if="name === 'next'">
      <path d="m9 18 6-6-6-6" />
    </template>
    <template v-else-if="name === 'close'">
      <path d="m18 6-12 12M6 6l12 12" />
    </template>
    <template v-else-if="name === 'back'">
      <path d="M19 12H5M12 19l-7-7 7-7" />
    </template>
    <template v-else-if="name === 'external'">
      <path d="M15 3h6v6M10 14L21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    </template>
    <template v-else-if="name === 'transfer'">
      <path d="M7 16V4m0 0L3 8m4-4l4 4m6 4v12m0 0l4-4m-4 4l-4-4" />
    </template>
    <template v-else-if="name === 'clock'">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </template>
    <template v-else-if="name === 'sun'">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
    </template>
    <template v-else-if="name === 'moon'">
      <path d="M12 3a9 9 0 1 0 9 9c0-.46-.04-.92-.1-1.36a5.389 5.389 0 0 1-4.4 2.26 5.403 5.403 0 0 1-3.14-9.8c-.44-.06-.9-.1-1.36-.1z" />
    </template>
    <template v-else-if="name === 'search'">
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-4.35-4.35" />
    </template>
    <template v-else-if="name === 'check'">
      <path d="m5 12 5 5L20 7" />
    </template>
    <template v-else-if="name === 'arrow-right'">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </template>
    <template v-else>
      <circle cx="12" cy="12" r="8" />
    </template>
  </svg>
</template>
