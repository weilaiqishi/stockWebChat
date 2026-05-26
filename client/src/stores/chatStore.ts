import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useConfigStore } from './configStore'
import { genActionId, type ActionName } from '@/utils/actions'

const log = (actionId: string, msg: string, ...args: any[]) => {
  const short = actionId.split('.').slice(0, 3).join('.')
  console.log(`[${short}] ${msg}`, ...args)
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  chartSpecs?: ChartSpec[]
  thinkingSteps?: ThinkingStep[]
  timestamp: number
}

export interface ChartSpec {
  symbol: string
  period?: string
  count?: number
  title?: string
  start_date?: string  // YYYY-MM-DD, 由 LLM 根据用户问题填入
  end_date?: string
}

export interface ThinkingStep {
  tool: string
  displayName: string
  args: Record<string, string>
  summary: string
}

export interface Session {
  id: string
  title: string
  msg_count: number
  created_at: number
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const sessions = ref<Session[]>([])
  const sessionId = ref<string>('')
  const isStreaming = ref(false)
  const currentThinking = ref<string>('')
  const thinkingSteps = ref<ThinkingStep[]>([])
  const error = ref('')

  function addMessage(msg: ChatMessage) {
    messages.value.push(msg)
  }

  function clearMessages() {
    messages.value = []
    thinkingSteps.value = []
    error.value = ''
  }

  async function loadSessions() {
    try {
      const res = await fetch('/api/chat/sessions')
      const data = await res.json()
      sessions.value = data.sessions || []
    } catch {
      sessions.value = []
    }
  }

  async function sendMessage(text: string, strategyIds: string[] = [], analysisDimensions: string[] = []) {
    const actionId = genActionId('chat.send')
    log(actionId, '→ sendMessage', text.slice(0, 60))

    error.value = ''
    isStreaming.value = true
    currentThinking.value = ''
    thinkingSteps.value = []

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      timestamp: Date.now(),
    }
    addMessage(userMsg)

    let assistantContent = ''
    let chartSpecs: ChartSpec[] = []
    const assistantMsg: ChatMessage = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
    }
    addMessage(assistantMsg)

    const cfg = useConfigStore()
    const body: Record<string, any> = {
      message: text,
      session_id: sessionId.value || undefined,
      strategy_ids: strategyIds.length > 0 ? strategyIds : undefined,
      analysis_dimensions: analysisDimensions.length > 0 ? analysisDimensions : undefined,
      action_id: actionId,
      ...cfg.getRequestBodyFields(),
    }

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Action-Id': actionId,
        },
        body: JSON.stringify(body),
      })

      if (!response.ok) {
        const err = await response.json()
        log(actionId, '✗ HTTP', response.status, err.detail)
        throw new Error(err.detail || '请求失败')
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let eventCount = 0

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6)
          try {
            const event = JSON.parse(data)
            eventCount++
            if (eventCount % 10 === 0) {
              log(actionId, '← SSE events', eventCount, 'last type:', event.type)
            }

            switch (event.type) {
              case 'thinking':
                currentThinking.value = event.message
                break
              case 'tool_start':
                currentThinking.value = `正在调用 ${event.display_name}...`
                thinkingSteps.value.push({
                  tool: event.tool,
                  displayName: event.display_name,
                  args: event.args || {},
                  summary: '执行中...',
                })
                break
              case 'tool_done':
                if (thinkingSteps.value.length > 0) {
                  thinkingSteps.value[thinkingSteps.value.length - 1].summary = event.summary
                }
                break
              case 'content_delta':
                assistantContent += event.text || ''
                assistantMsg.content = assistantContent
                break
              case 'done':
                assistantContent = event.content || ''
                chartSpecs = event.chart_specs || []
                if (event.session_id) sessionId.value = event.session_id
                assistantMsg.content = assistantContent
                assistantMsg.chartSpecs = chartSpecs
                assistantMsg.thinkingSteps = [...thinkingSteps.value]
                break
              case 'error':
                log(actionId, '✗ SSE error', event.message)
                error.value = event.message || '未知错误'
                break
            }
          } catch { /* skip malformed JSON */ }
        }
      }
      log(actionId, '← SSE done', eventCount, 'events, charts:', chartSpecs.length)
    } catch (e: any) {
      log(actionId, '✗ connection failed', e.message)
      error.value = e.message || '连接失败'
    } finally {
      isStreaming.value = false
      currentThinking.value = ''
    }
  }

  async function summarizeConversation() {
    const actionId = genActionId('chat.summary')
    log(actionId, '→ summarizeConversation')
    if (!sessionId.value) return '没有活跃的对话。'
    const cfg = useConfigStore()
    try {
      const res = await fetch('/api/chat/summarize', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Action-Id': actionId,
        },
        body: JSON.stringify({
          session_id: sessionId.value,
          ...cfg.getRequestBodyFields(),
        }),
      })
      const data = await res.json()
      log(actionId, '← summarize done')
      return data.summary || '总结生成失败。'
    } catch (e: any) {
      log(actionId, '✗ summarize failed', e.message)
      return '总结请求失败。'
    }
  }

  async function deepAnalyzeStock(stockCode: string, strategyIds: string[] = []) {
    const actionId = genActionId('deep.analysis')
    log(actionId, '→ deepAnalyzeStock', stockCode)

    error.value = ''
    isStreaming.value = true
    try {
      const cfg = useConfigStore()
      const res = await fetch('/api/chat/deep-analysis', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Action-Id': actionId,
        },
        body: JSON.stringify({
          stock_code: stockCode,
          session_id: sessionId.value || undefined,
          strategy_ids: strategyIds.length > 0 ? strategyIds : undefined,
          action_id: actionId,
          ...cfg.getRequestBodyFields(),
        }),
      })
      if (!res.ok) {
        const err = await res.json()
        log(actionId, '✗ HTTP', res.status, err.detail)
        throw new Error(err.detail || '请求失败')
      }
      const data = await res.json()
      log(actionId, '← deep analysis done', 'charts:', (data.chartSpecs || []).length)
      return {
        analysis: data.analysis || '',
        chartSpecs: data.chart_specs || [],
      }
    } catch (e: any) {
      log(actionId, '✗ deep analysis failed', e.message)
      error.value = e.message || '深度分析失败'
      return null
    } finally {
      isStreaming.value = false
    }
  }

  async function deleteSession(sid: string) {
    const actionId = genActionId('session.delete')
    log(actionId, '→ deleteSession', sid)
    try {
      await fetch(`/api/chat/sessions/${sid}`, {
        method: 'DELETE',
        headers: { 'X-Action-Id': actionId },
      })
      if (sessionId.value === sid) {
        sessionId.value = ''
        clearMessages()
      }
      await loadSessions()
      log(actionId, '← session deleted')
    } catch {
      log(actionId, '✗ delete failed')
    }
  }

  return {
    messages, sessions, sessionId, isStreaming, currentThinking, thinkingSteps, error,
    addMessage, clearMessages, loadSessions, sendMessage,
    summarizeConversation, deepAnalyzeStock, deleteSession,
  }
})
