<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useConfigStore } from '@/stores/configStore'
import { Settings, MessageSquare, Loader2 } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const configStore = useConfigStore()

onMounted(async () => {
  await configStore.checkStatus()
})

watch(() => configStore.isReady, (ready) => {
  if (!ready && route.path !== '/settings') {
    router.push('/settings')
  }
})
</script>

<template>
  <div class="h-screen bg-gray-50 flex flex-col">
    <!-- Header -->
    <header class="bg-white border-b sticky top-0 z-50">
      <div class="container mx-auto px-4 h-14 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <MessageSquare class="w-5 h-5 text-primary" />
          <h1 class="text-lg font-bold">Agent 策略问股</h1>
        </div>
        <div class="flex items-center gap-2">
          <button
            class="p-2 rounded-md hover:bg-gray-100 transition-colors"
            :class="{ 'bg-blue-50 text-primary': route.path === '/settings' }"
            @click="router.push('/settings')"
            title="系统配置"
          >
            <Settings class="w-5 h-5" />
          </button>
        </div>
      </div>
    </header>

    <!-- Loading -->
    <div v-if="configStore.loading" class="flex-1 flex items-center justify-center">
      <Loader2 class="w-6 h-6 animate-spin text-gray-400" />
      <span class="ml-2 text-gray-500">加载中...</span>
    </div>

    <!-- Main Content -->
    <main v-else class="flex-1 flex flex-col">
      <router-view />
    </main>
  </div>
</template>
