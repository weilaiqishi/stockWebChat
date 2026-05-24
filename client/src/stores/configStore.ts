import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useConfigStore = defineStore('config', () => {
  const configured = ref(false)
  const loading = ref(true)
  const config = ref<Record<string, string>>({})

  async function checkStatus() {
    try {
      const res = await fetch('/api/config/status')
      const data = await res.json()
      configured.value = data.configured
    } catch {
      configured.value = false
    } finally {
      loading.value = false
    }
  }

  async function loadConfig() {
    try {
      const res = await fetch('/api/config')
      config.value = await res.json()
    } catch {
      config.value = {}
    }
  }

  const isReady = computed(() => !loading.value && configured.value)

  return { configured, loading, config, checkStatus, loadConfig, isReady }
})
