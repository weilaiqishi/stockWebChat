<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { init, dispose, type Chart, type Period, type KLineData } from 'klinecharts'
import { genActionId } from '@/utils/actions'

const props = withDefaults(defineProps<{
  symbol: string
  period?: string
  title?: string
  height?: string
  startDate?: string  // YYYY-MM-DD, LLM 根据用户问题传入
  endDate?: string
}>(), {
  period: '1d',
  title: '',
  height: '400px',
})

const log = (msg: string, ...args: any[]) => console.log(`[StockChart] ${msg}`, ...args)
const logId = ref('')

const PERIODS = [
  { key: '1d', label: '日K' },
  { key: '1w', label: '周K' },
  { key: '1M', label: '月K' },
  { key: '1Y', label: '年K' },
] as const

const PAGE_SIZE = 500

const activePeriod = ref(props.period)
const chartRef = ref<HTMLDivElement | null>(null)
const isLoading = ref(true)
const error = ref('')
const dataEmpty = ref(false)

let chart: Chart | null = null
let resizeObserver: ResizeObserver | null = null

function toKLPeriod(p: string): Period {
  switch (p) {
    case '1d': return { type: 'day', span: 1 }
    case '1w': return { type: 'week', span: 1 }
    case '1M': return { type: 'month', span: 1 }
    case '1Y': return { type: 'year', span: 1 }
    default: return { type: 'day', span: 1 }
  }
}

// ---------------------------------------------------------------------------
// Chart init
// ---------------------------------------------------------------------------

function initChart() {
  if (!chartRef.value) {
    log('initChart 跳过: chartRef 为空')
    return
  }
  const el = chartRef.value
  log('initChart 开始', { width: el.clientWidth, height: el.clientHeight })

  chart = init(el, {
    locale: 'zh-CN',
    styles: {
      grid: {
        show: true,
        horizontal: { show: true, color: '#f0f0f0', style: 'dashed', dashedValue: [2, 2], size: 1 },
        vertical: { show: true, color: '#f0f0f0', style: 'dashed', dashedValue: [2, 2], size: 1 },
      },
      candle: {
        type: 'candle_solid',
        bar: {
          compareRule: 'current_open',
          upColor: '#ef4444',
          downColor: '#22c55e',
          upBorderColor: '#ef4444',
          downBorderColor: '#22c55e',
          upWickColor: '#ef4444',
          downWickColor: '#22c55e',
          noChangeColor: '#888888',
          noChangeBorderColor: '#888888',
          noChangeWickColor: '#888888',
        },
        priceMark: { show: false },
        tooltip: { showRule: 'follow_cross' },
      },
      indicator: {
        ohlc: {
          compareRule: 'current_open',
          upColor: '#ef4444',
          downColor: '#22c55e',
          noChangeColor: '#888888',
        },
        bars: [{
          style: 'fill',
          borderSize: 0,
          upColor: '#ef4444',
          downColor: '#22c55e',
          noChangeColor: '#888888',
        }],
      },
      xAxis: {
        show: true,
        axisLine: { show: true, color: '#e0e0e0', size: 1 },
        tickText: { show: true, color: '#999', size: 11, weight: 'normal' },
        tickLine: { show: true, color: '#e0e0e0', size: 1, length: 3 },
      },
      yAxis: {
        show: true,
        axisLine: { show: true, color: '#e0e0e0', size: 1 },
        tickText: { show: true, color: '#999', size: 11, weight: 'normal' },
        tickLine: { show: true, color: '#e0e0e0', size: 1, length: 3 },
      },
      crosshair: {
        show: true,
        horizontal: {
          show: true,
          line: { show: true, style: 'dashed', dashedValue: [4, 2], size: 1, color: '#888888' },
          text: { show: true, color: '#FFFFFF', size: 11, backgroundColor: '#686D76' },
        },
        vertical: {
          show: true,
          line: { show: true, style: 'dashed', dashedValue: [4, 2], size: 1, color: '#888888' },
          text: { show: true, color: '#FFFFFF', size: 11, backgroundColor: '#686D76' },
        },
      },
      separator: { size: 1, color: '#e0e0e0' },
    },
  })

  if (!chart) {
    log('initChart 失败: 返回 null')
    return
  }
  log('initChart 完成')

  // Data loader — KLineChart handles pagination (init/forward/backward)
  logId.value = genActionId('stock.klines')

  chart.setDataLoader({
    getBars: async ({ type, timestamp, symbol, period, callback }) => {
      log('getBars', { type, timestamp, symbol: symbol.ticker, period })

      if (type === 'init') {
        isLoading.value = true
        error.value = ''
        dataEmpty.value = false
      }

      try {
        const apiPeriod = period.type === 'day' ? '1d'
          : period.type === 'week' ? '1w'
          : period.type === 'month' ? '1M'
          : '1Y'

        const params = new URLSearchParams({
          symbol: symbol.ticker,
          period: apiPeriod,
          count: String(PAGE_SIZE),
        })

        if (type === 'forward' && timestamp != null) {
          params.set('end_time', String(timestamp - 1))
        } else if (type === 'backward' && timestamp != null) {
          params.set('start_time', String(timestamp))
        } else if (type === 'init') {
          if (props.startDate) params.set('start_date', props.startDate)
          if (props.endDate) params.set('end_date', props.endDate)
        }

        const url = `/api/stock/klines?${params}`
        log('getBars 请求', url)
        const res = await fetch(url, {
          headers: logId.value ? { 'X-Action-Id': logId.value } : undefined,
        })
        if (!res.ok) {
          const err = await res.json()
          throw new Error(err.detail || '获取K线失败')
        }
        const json = await res.json()
        const rawList: any[] = json.data || []
        const list: KLineData[] = rawList.map(r => ({
          timestamp: r.timestamp,
          open: r.open,
          high: r.high,
          low: r.low,
          close: r.close,
          volume: r.volume,
        }))
        log('getBars 结果', { count: list.length })

        // more=boolean 表示两个方向都有/没有更多数据
        // more={forward,backward} 分别控制
        if (type === 'init' && (props.startDate || props.endDate)) {
          callback(list, { forward: false, backward: false })
        } else {
          callback(list, list.length >= PAGE_SIZE)
        }

        if (type === 'init') {
          dataEmpty.value = list.length === 0
        }
      } catch (e: any) {
        log('getBars 失败', e.message)
        callback([], false)
        if (type === 'init') {
          error.value = e.message || '请求失败'
          dataEmpty.value = true
        }
      } finally {
        if (type === 'init') {
          isLoading.value = false
        }
      }
    },
  })

  chart.setSymbol({ ticker: props.symbol, pricePrecision: 2, volumePrecision: 0 })
  chart.setPeriod(toKLPeriod(activePeriod.value))

  // Resize observer
  resizeObserver = new ResizeObserver(() => {
    chart?.resize()
  })
  resizeObserver.observe(el)
}

// ---------------------------------------------------------------------------
// Period switching
// ---------------------------------------------------------------------------

function switchPeriod(period: string) {
  if (period === activePeriod.value) {
    log('switchPeriod 跳过: 相同周期', { period })
    return
  }
  log('switchPeriod 切换', { from: activePeriod.value, to: period })
  activePeriod.value = period
  chart?.setPeriod(toKLPeriod(period))
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

onMounted(() => {
  log('onMounted', { symbol: props.symbol, period: props.period, startDate: props.startDate, endDate: props.endDate })
  initChart()
  log('onMounted 完成')
})

onUnmounted(() => {
  log('onUnmounted')
  resizeObserver?.disconnect()
  if (chart) dispose(chart)
  chart = null
})

// React to symbol changes
watch(() => props.symbol, (newVal, oldVal) => {
  log('symbol 变化', { from: oldVal, to: newVal })
  if (chart) {
    isLoading.value = true
    error.value = ''
    dataEmpty.value = false
    chart.setSymbol({ ticker: newVal, pricePrecision: 2, volumePrecision: 0 })
  }
})
</script>

<template>
  <div class="bg-white rounded-lg border p-4 my-3">
    <div class="flex items-center justify-between mb-3">
      <div v-if="title" class="text-sm font-medium text-gray-700">{{ title }}</div>
      <div class="flex gap-1 bg-gray-100 rounded-lg p-0.5 ml-auto">
        <button
          v-for="p in PERIODS"
          :key="p.key"
          @click="switchPeriod(p.key)"
          class="px-2.5 py-1 text-xs rounded-md transition-colors"
          :class="activePeriod === p.key
            ? 'bg-white text-gray-900 shadow-sm font-medium'
            : 'text-gray-500 hover:text-gray-700'"
        >
          {{ p.label }}
        </button>
      </div>
    </div>

    <div class="relative" :style="{ width: '100%', height }">
      <div ref="chartRef" class="w-full h-full"></div>

      <div v-if="isLoading" class="absolute inset-0 z-10 flex items-center justify-center bg-white rounded-lg">
        <span class="text-sm text-gray-400">加载K线数据...</span>
      </div>

      <div v-else-if="error" class="absolute inset-0 z-10 flex items-center justify-center bg-white rounded-lg">
        <span class="text-sm text-red-500">{{ error }}</span>
      </div>

      <div v-else-if="dataEmpty" class="absolute inset-0 z-10 flex items-center justify-center bg-white rounded-lg">
        <span class="text-sm text-gray-400">暂无K线数据</span>
      </div>
    </div>
  </div>
</template>
