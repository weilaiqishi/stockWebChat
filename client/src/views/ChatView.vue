<script setup lang="ts">
import { ref, nextTick, watch, onMounted } from 'vue'
import { Send, Loader2, FileText, Search, Sparkles } from 'lucide-vue-next'
import { useChatStore } from '@/stores/chatStore'
import { genActionId } from '@/utils/actions'
import { Button } from '@/components/ui/button'
import ChatMessage from '@/components/ChatMessage.vue'
import StockChart from '@/components/StockChart.vue'
import SessionSidebar from '@/components/SessionSidebar.vue'
import StrategyEditor from '@/components/StrategyEditor.vue'

const log = console.log

const chatStore = useChatStore()
const inputText = ref('')
const messagesEl = ref<HTMLElement | null>(null)
const strategyIds = ref<string[]>([])

// Modal state
const showSummary = ref(false)
const summaryText = ref('')
const summaryLoading = ref(false)

const showDeepAnalysis = ref(false)
const deepStockCode = ref('')
const deepAnalysisText = ref('')
const deepChartSpecs = ref<any[]>([])
const deepLoading = ref(false)

onMounted(() => {
  chatStore.loadSessions()
})

watch(() => chatStore.messages.length, async () => {
  await nextTick()
  scrollToBottom()
})

function scrollToBottom() {
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || chatStore.isStreaming) return
  inputText.value = ''
  await chatStore.sendMessage(text, strategyIds.value)
  await nextTick()
  scrollToBottom()
}

async function handleSummarize() {
  const actionId = genActionId('chat.summary')
  log(`[${actionId}] → handleSummarize`)
  summaryLoading.value = true
  summaryText.value = ''
  showSummary.value = true
  summaryText.value = await chatStore.summarizeConversation()
  summaryLoading.value = false
  log(`[${actionId}] ← handleSummarize done`)
}

async function handleDeepAnalysis() {
  const code = deepStockCode.value.trim()
  if (!code) return
  const actionId = genActionId('deep.analysis')
  log(`[${actionId}] → handleDeepAnalysis`, code)
  deepLoading.value = true
  deepAnalysisText.value = ''
  deepChartSpecs.value = []
  const result = await chatStore.deepAnalyzeStock(code, strategyIds.value)
  if (result) {
    deepAnalysisText.value = result.analysis
    deepChartSpecs.value = result.chartSpecs || []
  }
  deepLoading.value = false
  log(`[${actionId}] ← handleDeepAnalysis done, charts:`, deepChartSpecs.value.length)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}
</script>

<template>
  <div class="flex-1 flex h-[calc(100vh-3.5rem)]">
    <!-- Sidebar -->
    <SessionSidebar @select="chatStore.loadSessions()" />

    <!-- Chat area -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- Action bar -->
      <div class="px-4 py-2 border-b bg-white flex items-center gap-2 flex-shrink-0">
        <Button variant="outline" size="sm" @click="showSummary = true; handleSummarize()">
          <FileText class="w-3.5 h-3.5 mr-1" />
          总结对话
        </Button>
        <Button variant="outline" size="sm" @click="showDeepAnalysis = true">
          <Search class="w-3.5 h-3.5 mr-1" />
          深度分析
        </Button>
        <div class="flex-1"></div>
        <!-- Strategy selector -->
        <StrategyEditor @change="(ids) => strategyIds = ids" />
      </div>

      <!-- Messages -->

        <div ref="messagesEl" class="messages-panel">
          <div v-if="chatStore.messages.length === 0" class="flex items-center justify-center h-full">
            <div class="text-center text-gray-400">
              <Sparkles class="w-10 h-10 mx-auto mb-3 text-gray-300" />
              <p class="text-lg font-medium mb-1">Agent 策略问股</p>
              <p class="text-sm">输入股票代码或问题开始多轮对话分析</p>
              <p class="text-xs mt-2 text-gray-300">支持: K线分析 · 趋势判断 · 知乎舆情 · 全网搜索</p>
            </div>
          </div>

          <ChatMessage v-for="msg in chatStore.messages" :key="msg.id" :content="msg.content"
            :chart-specs="msg.chartSpecs" :thinking-steps="msg.thinkingSteps" :role="msg.role" />

          <!-- Streaming indicator -->
          <div v-if="chatStore.isStreaming && chatStore.currentThinking"
            class="flex items-center gap-2 text-sm text-gray-500 px-3">
            <Loader2 class="w-3.5 h-3.5 animate-spin" />
            {{ chatStore.currentThinking }}
          </div>

          <!-- Error -->
          <div v-if="chatStore.error" class="bg-red-50 border border-red-200 text-red-800 rounded-lg p-3 text-sm">
            {{ chatStore.error }}
          </div>
        </div>

      <!-- Input -->
      <div class="px-4 py-3 border-t bg-white flex-shrink-0">
        <div class="flex gap-2">
          <textarea v-model="inputText"
            class="flex-1 border rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
            rows="2" placeholder="输入股票代码或问题，如: 分析招商银行最近的走势..." :disabled="chatStore.isStreaming"
            @keydown="handleKeydown"></textarea>
          <Button class="self-end" :disabled="!inputText.trim() || chatStore.isStreaming" @click="handleSend">
            <Loader2 v-if="chatStore.isStreaming" class="w-4 h-4 animate-spin" />
            <Send v-else class="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>

    <!-- Summary Modal -->
    <Teleport to="body">
      <div v-if="showSummary" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
        @click.self="showSummary = false">
        <div class="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto p-6">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-bold flex items-center gap-2">
              <FileText class="w-5 h-5" /> 对话总结
            </h3>
            <button class="text-gray-400 hover:text-gray-600 text-xl leading-none"
              @click="showSummary = false">&times;</button>
          </div>
          <div v-if="summaryLoading" class="flex items-center gap-2 text-gray-500 py-8 justify-center">
            <Loader2 class="w-5 h-5 animate-spin" /> 正在生成总结...
          </div>
          <div v-else class="text-sm whitespace-pre-wrap leading-relaxed">{{ summaryText }}</div>
        </div>
      </div>
    </Teleport>

    <!-- Deep Analysis Modal -->
    <Teleport to="body">
      <div v-if="showDeepAnalysis" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
        @click.self="showDeepAnalysis = false">
        <div class="bg-white rounded-xl shadow-xl max-w-2xl w-full mx-4 max-h-[85vh] overflow-y-auto p-6">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-bold flex items-center gap-2">
              <Search class="w-5 h-5" /> 深度分析
            </h3>
            <button class="text-gray-400 hover:text-gray-600 text-xl leading-none"
              @click="showDeepAnalysis = false">&times;</button>
          </div>
          <div class="flex gap-2 mb-4">
            <input v-model="deepStockCode"
              class="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              placeholder="输入股票代码，如 600519.SH" @keydown.enter="handleDeepAnalysis" />
            <Button :disabled="!deepStockCode.trim() || deepLoading" @click="handleDeepAnalysis">
              <Loader2 v-if="deepLoading" class="w-4 h-4 mr-1 animate-spin" />
              分析
            </Button>
          </div>
          <div v-if="deepLoading" class="flex items-center gap-2 text-gray-500 py-8 justify-center">
            <Loader2 class="w-5 h-5 animate-spin" /> 正在深度分析...
          </div>
          <div v-else-if="deepAnalysisText" class="text-sm markdown-body" v-html="deepAnalysisText"></div>
          <div v-if="deepChartSpecs.length > 0" class="mt-4">
            <StockChart v-for="(spec, i) in deepChartSpecs" :key="i" :symbol="spec.symbol" :period="spec.period || '1d'"
              :title="spec.title" :start-date="spec.start_date" :end-date="spec.end_date" />
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.messages-panel {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 1rem;
}
.messages-panel > * + * {
  margin-top: 0.5rem;
}
</style>
