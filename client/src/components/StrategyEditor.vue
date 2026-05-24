<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface Strategy {
  id: string
  name: string
  category: string
}

const strategies = ref<Strategy[]>([])
const selectedIds = ref<string[]>([])
const loading = ref(false)

const emit = defineEmits<{
  change: [ids: string[]]
}>()

onMounted(async () => {
  loading.value = true
  try {
    const res = await fetch('/api/strategies')
    const data = await res.json()
    strategies.value = data.strategies || []
  } catch { /* ignore */ }
  loading.value = false
})

function toggle(id: string) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) {
    selectedIds.value.splice(idx, 1)
  } else {
    selectedIds.value.push(id)
  }
  emit('change', [...selectedIds.value])
}

const categoryNames: Record<string, string> = {
  trend: '趋势',
  risk: '风险',
  pattern: '形态',
  framework: '框架',
}
</script>

<template>
  <div class="relative">
    <div v-if="loading" class="text-xs text-gray-400">加载策略...</div>
    <div v-else class="flex flex-wrap gap-1.5">
      <button
        v-for="s in strategies"
        :key="s.id"
        class="px-2 py-0.5 text-xs rounded-full border transition-colors"
        :class="selectedIds.includes(s.id)
          ? 'bg-primary text-primary-foreground border-primary'
          : 'bg-white text-gray-600 border-gray-200 hover:border-gray-400'"
        @click="toggle(s.id)"
      >
        {{ s.name }}
        <span class="ml-1 opacity-50">[{{ categoryNames[s.category] || s.category }}]</span>
      </button>
      <span v-if="strategies.length === 0" class="text-xs text-gray-400">暂无策略</span>
    </div>
  </div>
</template>
