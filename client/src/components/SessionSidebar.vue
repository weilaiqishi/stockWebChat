<script setup lang="ts">
import { onMounted } from 'vue'
import { Plus, Trash2, MessageSquare } from 'lucide-vue-next'
import { useChatStore, type Session } from '@/stores/chatStore'

const chatStore = useChatStore()

const emit = defineEmits<{
  select: [sessionId: string]
}>()

onMounted(() => {
  chatStore.loadSessions()
})

function selectSession(session: Session) {
  chatStore.sessionId = session.id
  emit('select', session.id)
}

function newSession() {
  chatStore.sessionId = ''
  chatStore.clearMessages()
}

function formatTime(ts: number): string {
  const d = new Date(ts * 1000)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}
</script>

<template>
  <div class="w-56 bg-white border-r flex flex-col">
    <div class="p-3 border-b">
      <button
        class="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-sm border rounded-md hover:bg-gray-50 transition-colors"
        @click="newSession"
      >
        <Plus class="w-4 h-4" />
        新建对话
      </button>
    </div>
    <div class="flex-1 overflow-y-auto">
      <div v-if="chatStore.sessions.length === 0" class="p-4 text-center text-sm text-gray-400">
        暂无历史会话
      </div>
      <div
        v-for="s in chatStore.sessions"
        :key="s.id"
        class="px-3 py-2.5 cursor-pointer hover:bg-gray-50 transition-colors border-b border-gray-50 flex items-center gap-2 group"
        :class="{ 'bg-blue-50': chatStore.sessionId === s.id }"
        @click="selectSession(s)"
      >
        <MessageSquare class="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
        <div class="flex-1 min-w-0">
          <div class="text-xs font-medium truncate">{{ s.title }}</div>
          <div class="text-xs text-gray-400">{{ s.msg_count }} 条 · {{ formatTime(s.created_at) }}</div>
        </div>
        <button
          class="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-500 transition-all"
          @click.stop="chatStore.deleteSession(s.id)"
        >
          <Trash2 class="w-3 h-3" />
        </button>
      </div>
    </div>
  </div>
</template>
