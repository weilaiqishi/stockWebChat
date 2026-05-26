<script setup lang="ts">
import { ref } from 'vue'

export interface ChipDef {
  id: string
  label: string
}

const chips: ChipDef[] = [
  { id: 'quote', label: '📊 行情' },
  { id: 'news', label: '📰 公告' },
  { id: 'technical', label: '📈 技术' },
  { id: 'sector', label: '🏭 板块' },
]

const selected = ref<string[]>([])

const emit = defineEmits<{
  change: [ids: string[]]
}>()

function toggle(id: string) {
  const idx = selected.value.indexOf(id)
  if (idx >= 0) {
    selected.value.splice(idx, 1)
  } else {
    selected.value.push(id)
  }
  emit('change', [...selected.value])
}
</script>

<template>
  <div class="flex flex-wrap gap-1.5">
    <button
      v-for="chip in chips"
      :key="chip.id"
      class="px-2 py-0.5 text-xs rounded-full border transition-colors"
      :class="selected.includes(chip.id)
        ? 'bg-primary text-primary-foreground border-primary'
        : 'bg-white text-gray-600 border-gray-200 hover:border-gray-400'"
      @click="toggle(chip.id)"
    >
      {{ chip.label }}
    </button>
  </div>
</template>
