/** Action registry — single source of truth for user action → API mapping */

export const ACTIONS = {
  'chat.send': {
    api: 'POST /api/chat/stream',
    description: '发送对话消息',
    internal: ['agent loop', 'tools'],
  },
  'chat.summary': {
    api: 'POST /api/chat/summarize',
    description: '总结对话',
  },
  'deep.analysis': {
    api: 'POST /api/chat/deep-analysis',
    description: '深度分析',
    internal: ['agent loop', 'tools'],
  },
  'stock.klines': {
    api: 'GET /api/stock/klines',
    description: '加载K线数据',
  },
  'session.list': {
    api: 'GET /api/chat/sessions',
    description: '加载会话列表',
  },
  'session.delete': {
    api: 'DELETE /api/chat/sessions/{id}',
    description: '删除会话',
  },
  'config.load': {
    api: 'GET /api/config',
    description: '加载配置',
  },
  'config.save': {
    api: 'POST /api/config',
    description: '保存配置',
  },
} as const

export type ActionName = keyof typeof ACTIONS

export function genActionId(action: ActionName): string {
  const ts = Date.now()
  const rand = Math.random().toString(36).slice(2, 6)
  return `${action}.${ts}.${rand}`
}
