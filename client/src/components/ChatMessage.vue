<script setup lang="ts">
import { ref } from 'vue'
import { marked } from 'marked'
import { ChevronDown, ChevronRight, Wrench } from 'lucide-vue-next'
import StockChart from './StockChart.vue'
import type { ChartSpec, ThinkingStep } from '@/stores/chatStore'

const props = defineProps<{
  content: string
  chartSpecs?: ChartSpec[]
  thinkingSteps?: ThinkingStep[]
  role: 'user' | 'assistant' | 'system'
}>()

const showThinking = ref(false)

function renderMarkdown(text: string): string {
  if (!text) return ''
  return marked.parse(text, { breaks: true }) as string
}
</script>

<template>
  <div :class="['flex gap-3 mb-4', role === 'user' ? 'justify-end' : 'justify-start']">
    <!-- User message -->
    <div v-if="role === 'user'" class="max-w-[90%] sm:max-w-[80%] bg-primary text-primary-foreground rounded-lg px-3 sm:px-4 py-2.5">
      <p class="text-sm whitespace-pre-wrap">{{ content }}</p>
    </div>

    <!-- Assistant message -->
    <div v-else class="max-w-[95%] sm:max-w-[85%]">
      <!-- Thinking steps -->
      <div v-if="thinkingSteps && thinkingSteps.length > 0" class="mb-2">
        <button
          class="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 transition-colors"
          @click="showThinking = !showThinking"
        >
          <component :is="showThinking ? ChevronDown : ChevronRight" class="w-3 h-3" />
          <Wrench class="w-3 h-3" />
          <span>思考过程 ({{ thinkingSteps.length }} 步)</span>
        </button>
        <div v-if="showThinking" class="mt-1 space-y-1">
          <div
            v-for="(step, i) in thinkingSteps"
            :key="i"
            class="text-xs text-gray-500 bg-gray-50 rounded px-2 py-1"
          >
            <span class="font-medium">{{ step.displayName }}</span>
            <span v-if="step.summary" class="ml-1">— {{ step.summary }}</span>
          </div>
        </div>
      </div>

      <!-- Content -->
      <div
        v-if="content"
        class="bg-white border rounded-lg px-4 py-3 markdown-body text-sm"
        v-html="renderMarkdown(content)"
      ></div>

      <!-- Charts -->
      <StockChart
        v-for="(spec, i) in chartSpecs"
        :key="i"
        :symbol="spec.symbol"
        :period="spec.period || '1d'"
        :title="spec.title"
        :start-date="spec.start_date"
        :end-date="spec.end_date"
      />
    </div>
  </div>
</template>
