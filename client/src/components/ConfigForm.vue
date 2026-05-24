<script setup lang="ts">
import { ref } from 'vue'
import { useConfigStore } from '@/stores/configStore'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Save, FileJson, CheckCircle, XCircle, Loader2 } from 'lucide-vue-next'

const emit = defineEmits<{
  saved: []
}>()

const configStore = useConfigStore()

const form = ref({
  deepseek_api_key: '',
  deepseek_model: 'deepseek-v4-flash',
  deepseek_base_url: 'https://api.deepseek.com',
  zhihu_access_secret: '',
  feishu_app_id: '',
  feishu_app_secret: '',
  feishu_bitable_id: '',
})

const jsonMode = ref(false)
const jsonText = ref('')
const saving = ref(false)
const result = ref<{ success: boolean; message: string } | null>(null)

async function loadConfig() {
  // Prefer local storage if available
  const stored = configStore.config
  if (stored.deepseek_api_key) {
    Object.assign(form.value, stored)
    syncJson()
    return
  }
  try {
    const res = await fetch('/api/config')
    const data = await res.json()
    Object.assign(form.value, data)
    // Unmask for editing — load from server may show masked, so use original if available
    form.value.deepseek_api_key = ''
    form.value.zhihu_access_secret = ''
    form.value.feishu_app_secret = ''
    syncJson()
  } catch { /* ignore */ }
}

function syncJson() {
  jsonText.value = JSON.stringify(form.value, null, 2)
}

function applyJson() {
  try {
    const parsed = JSON.parse(jsonText.value)
    Object.assign(form.value, parsed)
  } catch { /* invalid JSON */ }
}

async function save() {
  saving.value = true
  result.value = null

  const payload = jsonMode.value ? JSON.parse(jsonText.value) : { ...form.value }

  try {
    const res = await fetch('/api/config/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (res.ok) {
      const data = await res.json()
      configStore.setConfig(payload)
      result.value = {
        success: true,
        message: data.bitable_id
          ? `配置已保存，飞书表格: ${data.bitable_id}`
          : '配置已保存',
      }
      emit('saved')
    } else {
      const err = await res.json()
      const errMsgs = typeof err.detail === 'object'
        ? Object.entries(err.detail).map(([k, v]) => `${k}: ${v}`).join('; ')
        : (err.detail || '保存失败')
      result.value = { success: false, message: errMsgs }
    }
  } catch (e: any) {
    result.value = { success: false, message: e.message || '请求失败' }
  } finally {
    saving.value = false
  }
}

loadConfig()
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <div v-if="result" :class="[
      'mb-4 p-3 rounded-md flex items-start gap-2 text-sm',
      result.success ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'
    ]">
      <component :is="result.success ? CheckCircle : XCircle" class="w-4 h-4 mt-0.5 flex-shrink-0" />
      {{ result.message }}
    </div>

    <!-- Toggle: Form / JSON -->
    <div class="flex items-center gap-2 mb-4">
      <Button variant="ghost" size="sm" @click="jsonMode = !jsonMode; jsonMode ? syncJson() : applyJson()">
        <FileJson class="w-4 h-4 mr-1" />
        {{ jsonMode ? '表单编辑' : 'JSON 编辑' }}
      </Button>
    </div>

    <!-- Form mode -->
    <div v-if="!jsonMode" class="space-y-4">
      <fieldset class="border rounded-lg p-4">
        <legend class="text-sm font-semibold px-1">DeepSeek (必填)</legend>
        <div class="space-y-3">
          <div>
            <label class="text-xs text-gray-500">API Key *</label>
            <Input v-model="form.deepseek_api_key" type="password" placeholder="sk-..." />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="text-xs text-gray-500">Model</label>
              <Input v-model="form.deepseek_model" placeholder="deepseek-v4-flash" />
            </div>
            <div>
              <label class="text-xs text-gray-500">Base URL</label>
              <Input v-model="form.deepseek_base_url" placeholder="https://api.deepseek.com" />
            </div>
          </div>
        </div>
      </fieldset>

      <fieldset class="border rounded-lg p-4">
        <legend class="text-sm font-semibold px-1">知乎搜索 (可选)</legend>
        <div>
          <label class="text-xs text-gray-500">Access Secret</label>
          <Input v-model="form.zhihu_access_secret" type="password" placeholder="知乎开放平台 Access Secret" />
          <p class="text-xs text-gray-400 mt-1">填了才能用知乎站内搜索和全网搜索工具。获取: developer.zhihu.com/profile</p>
        </div>
      </fieldset>

      <fieldset class="border rounded-lg p-4">
        <legend class="text-sm font-semibold px-1">飞书多维表格 (可选)</legend>
        <p class="text-xs text-gray-400 mb-3">填了启用: 对话历史持久化 + 策略CRUD + 深度分析报告存储。保存时自动校验并建表。</p>
        <div class="space-y-3">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="text-xs text-gray-500">App ID</label>
              <Input v-model="form.feishu_app_id" placeholder="cli_..." />
            </div>
            <div>
              <label class="text-xs text-gray-500">App Secret</label>
              <Input v-model="form.feishu_app_secret" type="password" placeholder="..." />
            </div>
          </div>
          <div>
            <label class="text-xs text-gray-500">Bitable ID (留空自动创建)</label>
            <Input v-model="form.feishu_bitable_id" placeholder="留空则自动创建" />
          </div>
        </div>
      </fieldset>
    </div>

    <!-- JSON mode -->
    <div v-else>
      <textarea
        v-model="jsonText"
        class="w-full h-80 font-mono text-sm border rounded-lg p-4 bg-gray-900 text-green-400 focus:outline-none focus:ring-2 focus:ring-primary"
        spellcheck="false"
      ></textarea>
    </div>

    <!-- Save button -->
    <div class="mt-6">
      <Button class="w-full" :disabled="saving" @click="save">
        <Loader2 v-if="saving" class="w-4 h-4 mr-2 animate-spin" />
        <Save v-else class="w-4 h-4 mr-2" />
        {{ saving ? '正在验证并保存...' : '保存配置' }}
      </Button>
    </div>
  </div>
</template>
