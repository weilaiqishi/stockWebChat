import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const STORAGE_KEY = 'stock_web_chat_config'

export interface AppConfig {
  deepseek_api_key: string
  deepseek_model: string
  deepseek_base_url: string
  zhihu_access_secret: string
  feishu_app_id: string
  feishu_app_secret: string
  feishu_bitable_id: string
}

const DEFAULTS: AppConfig = {
  deepseek_api_key: '',
  deepseek_model: 'deepseek-v4-flash',
  deepseek_base_url: 'https://api.deepseek.com',
  zhihu_access_secret: '',
  feishu_app_id: '',
  feishu_app_secret: '',
  feishu_bitable_id: '',
}

function loadFromStorage(): AppConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return { ...DEFAULTS, ...JSON.parse(raw) }
  } catch { /* ignore */ }
  return { ...DEFAULTS }
}

function saveToStorage(config: AppConfig) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
  } catch { /* ignore */ }
}

export const useConfigStore = defineStore('config', () => {
  const configured = ref(false)
  const loading = ref(true)
  const config = ref<AppConfig>(loadFromStorage())

  // If localStorage has a valid api_key, we're configured
  if (config.value.deepseek_api_key) {
    configured.value = true
  }

  async function checkStatus() {
    try {
      const res = await fetch('/api/config/status')
      if (res.ok) {
        const data = await res.json()
        configured.value = data.configured || !!config.value.deepseek_api_key
      }
      // If fetch fails, keep localStorage-based configured value
    } catch {
      // backend unreachable — trust localStorage
    } finally {
      loading.value = false
    }
  }

  async function loadConfig() {
    // Prefer local storage config
    const stored = loadFromStorage()
    if (stored.deepseek_api_key) {
      config.value = stored
      configured.value = true
      loading.value = false
      return
    }
    // Fall back to backend
    try {
      const res = await fetch('/api/config')
      config.value = { ...DEFAULTS, ...await res.json() }
    } catch {
      config.value = { ...DEFAULTS }
    } finally {
      loading.value = false
    }
  }

  function setConfig(cfg: Partial<AppConfig>) {
    config.value = { ...config.value, ...cfg }
    saveToStorage(config.value)
    if (config.value.deepseek_api_key) {
      configured.value = true
    }
  }

  /** Return config fields for sending in API request bodies. */
  function getRequestBodyFields() {
    return {
      deepseek_api_key: config.value.deepseek_api_key || undefined,
      deepseek_model: config.value.deepseek_model !== DEFAULTS.deepseek_model
        ? config.value.deepseek_model : undefined,
      deepseek_base_url: config.value.deepseek_base_url !== DEFAULTS.deepseek_base_url
        ? config.value.deepseek_base_url : undefined,
      zhihu_access_secret: config.value.zhihu_access_secret || undefined,
    }
  }

  /** Sync local config to backend (best-effort, may fail on Render). */
  async function syncToBackend() {
    try {
      await fetch('/api/config/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config.value),
      })
    } catch { /* backend persistence is optional */ }
  }

  const isReady = computed(() => !loading.value && configured.value)

  return {
    configured, loading, config, isReady,
    checkStatus, loadConfig, setConfig, getRequestBodyFields, syncToBackend,
  }
})
