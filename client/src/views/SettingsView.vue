<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useConfigStore } from '@/stores/configStore'
import ConfigForm from '@/components/ConfigForm.vue'

const router = useRouter()
const configStore = useConfigStore()

function onSaved() {
  configStore.configured = true
  setTimeout(() => router.push('/chat'), 800)
}
</script>

<template>
  <div class="flex-1 overflow-y-auto">
    <div class="container max-w-3xl mx-auto px-4 py-8">
      <div class="mb-6">
        <h1 class="text-2xl font-bold">系统配置</h1>
        <p class="text-sm text-gray-500 mt-1">
          首次使用需要配置 DeepSeek API Key。知乎搜索和飞书多维表格为可选项。
        </p>
      </div>

      <ConfigForm @saved="onSaved" />
    </div>
  </div>
</template>
