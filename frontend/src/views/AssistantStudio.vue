<template>
  <div class="h-full grid grid-cols-1 xl:grid-cols-12 gap-6">
    <div class="xl:col-span-4 space-y-6">
      <div class="bg-white/80 backdrop-blur-xl border border-white/60 rounded-[24px] p-5 shadow-sm">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-bold text-slate-800">会话列表</h3>
          <button
            class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-50 text-indigo-600 border border-indigo-100 hover:bg-indigo-100 transition-colors"
            @click="createConversation"
          >
            新建
          </button>
        </div>
        <div class="space-y-2 max-h-[260px] overflow-y-auto custom-scrollbar">
          <button
            v-for="item in conversations"
            :key="item.conversation_id"
            class="w-full text-left px-3 py-2 rounded-lg border transition-colors"
            :class="item.conversation_id === currentConversationId ? 'border-indigo-300 bg-indigo-50 text-indigo-700' : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'"
            @click="pickConversation(item.conversation_id)"
          >
            <p class="text-xs font-semibold truncate">{{ item.title || item.conversation_id }}</p>
            <p class="text-[11px] text-slate-400 mt-1 truncate">{{ item.model || 'kimi-k2.5' }}</p>
          </button>
          <div v-if="!conversations.length" class="text-xs text-slate-400 py-4 text-center">
            暂无会话
          </div>
        </div>
        <div class="flex justify-end mt-3">
          <button
            class="text-xs text-red-500 hover:text-red-600 disabled:opacity-40"
            :disabled="!currentConversationId"
            @click="removeConversation"
          >
            删除当前会话
          </button>
        </div>
      </div>

      <div class="bg-white/80 backdrop-blur-xl border border-white/60 rounded-[24px] p-5 shadow-sm">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-bold text-slate-800">文件上下文</h3>
          <button class="text-xs text-slate-500 hover:text-slate-700" @click="refreshFiles">刷新</button>
        </div>

        <div class="grid grid-cols-3 gap-2 mb-3">
          <button
            v-for="item in purposeOptions"
            :key="item.value"
            class="px-2 py-1.5 text-xs rounded-lg border transition-colors"
            :class="filePurpose === item.value ? 'bg-indigo-50 text-indigo-600 border-indigo-200' : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'"
            @click="filePurpose = item.value"
          >
            {{ item.label }}
          </button>
        </div>

        <label class="block w-full mb-3">
          <input type="file" multiple class="hidden" @change="uploadFiles" />
          <span class="block w-full text-center px-3 py-2.5 text-xs font-semibold rounded-lg border border-dashed border-slate-300 text-slate-600 hover:border-indigo-300 hover:text-indigo-600 cursor-pointer transition-colors">
            {{ uploading ? '上传中...' : '上传文件到 Kimi' }}
          </span>
        </label>

        <div class="space-y-2 max-h-[260px] overflow-y-auto custom-scrollbar">
          <label
            v-for="f in files"
            :key="f.id"
            class="flex items-start gap-2 p-2 rounded-lg border border-slate-200 bg-white"
          >
            <input
              v-if="f.purpose === 'file-extract'"
              type="checkbox"
              class="mt-0.5"
              :checked="selectedFileIds.includes(f.id)"
              @change="toggleFile(f.id)"
            />
            <span v-else class="mt-0.5 w-3.5 h-3.5 rounded-full bg-slate-200"></span>
            <div class="flex-1 min-w-0">
              <p class="text-xs font-semibold text-slate-700 truncate">{{ f.filename || f.id }}</p>
              <p class="text-[11px] text-slate-400 truncate">{{ f.purpose }} · {{ formatBytes(f.bytes) }}</p>
            </div>
            <button class="text-[11px] text-red-500 hover:text-red-600" @click.prevent="removeFile(f.id)">删</button>
          </label>
          <div v-if="!files.length" class="text-xs text-slate-400 py-4 text-center">
            暂无已上传文件
          </div>
        </div>
      </div>
    </div>

    <div class="xl:col-span-8 bg-white/80 backdrop-blur-xl border border-white/60 rounded-[24px] shadow-sm p-5 flex flex-col min-h-[70vh]">
      <div class="flex flex-wrap items-center gap-3 mb-4">
        <div class="flex items-center gap-2">
          <label class="text-xs text-slate-500">模型</label>
          <input v-model.trim="model" class="px-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white" />
        </div>
        <div class="flex items-center gap-2">
          <label class="text-xs text-slate-500">上下文条数</label>
          <input v-model.number="maxHistoryMessages" type="number" min="4" max="100" class="w-20 px-2 py-1.5 text-xs rounded-lg border border-slate-200 bg-white" />
        </div>
        <div class="text-xs text-slate-400">
          已选文件: {{ selectedFileIds.length }}
        </div>
      </div>

      <div v-if="!authStore.isLoggedIn" class="flex-1 flex items-center justify-center text-slate-500 text-sm">
        请先登录后使用 AI 助手
      </div>

      <template v-else>
        <div ref="messagePanel" class="flex-1 overflow-y-auto custom-scrollbar space-y-3 pr-2">
          <div
            v-for="msg in chatMessages"
            :key="msg.id"
            class="max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 whitespace-pre-wrap"
            :class="msg.role === 'user' ? 'ml-auto bg-indigo-600 text-white' : 'bg-slate-100 text-slate-700'"
          >
            {{ msg.content }}
          </div>
          <div v-if="!chatMessages.length && !sending" class="text-xs text-slate-400 text-center py-10">
            输入内容开始对话。勾选 `file-extract` 文件后将自动注入上下文。
          </div>
        </div>

        <div class="mt-4 border-t border-slate-100 pt-4">
          <textarea
            v-model="inputText"
            rows="4"
            class="w-full px-4 py-3 text-sm rounded-xl border border-slate-200 bg-white focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/10"
            placeholder="输入你的问题..."
            @keydown.enter.exact.prevent="sendMessage"
          ></textarea>
          <div class="mt-3 flex items-center justify-between">
            <p class="text-xs text-slate-400">Enter 发送，Shift+Enter 换行</p>
            <button
              class="px-4 py-2 text-sm font-semibold rounded-xl bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50"
              :disabled="sending || !inputText.trim()"
              @click="sendMessage"
            >
              {{ sending ? '发送中...' : '发送' }}
            </button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const message = useMessage()

const model = ref('kimi-k2.5')
const maxHistoryMessages = ref(20)

const conversations = ref([])
const currentConversationId = ref('')
const chatMessages = ref([])
const inputText = ref('')
const sending = ref(false)

const files = ref([])
const selectedFileIds = ref([])
const filePurpose = ref('file-extract')
const uploading = ref(false)

const messagePanel = ref(null)

const purposeOptions = [
  { label: '抽取', value: 'file-extract' },
  { label: '图片', value: 'image' },
  { label: '视频', value: 'video' }
]

const authHeaders = computed(() => {
  if (!authStore.token) return {}
  return { Authorization: `Bearer ${authStore.token}` }
})

function formatBytes(bytes) {
  const n = Number(bytes || 0)
  if (!n) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let value = n
  let idx = 0
  while (value >= 1024 && idx < units.length - 1) {
    value /= 1024
    idx += 1
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[idx]}`
}

async function scrollToBottom() {
  await nextTick()
  const el = messagePanel.value
  if (el) {
    el.scrollTop = el.scrollHeight
  }
}

function createConversation() {
  currentConversationId.value = ''
  chatMessages.value = []
  inputText.value = ''
}

async function refreshConversations() {
  if (!authStore.isLoggedIn) return
  const res = await api.get('/api/assistant/conversations', { headers: authHeaders.value })
  conversations.value = Array.isArray(res.data?.data) ? res.data.data : []
}

async function loadMessages(conversationId) {
  if (!conversationId || !authStore.isLoggedIn) return
  const res = await api.get(`/api/assistant/conversations/${conversationId}/messages`, { headers: authHeaders.value })
  chatMessages.value = Array.isArray(res.data?.data) ? res.data.data : []
  await scrollToBottom()
}

async function pickConversation(conversationId) {
  currentConversationId.value = conversationId
  await loadMessages(conversationId)
}

async function removeConversation() {
  if (!currentConversationId.value) return
  try {
    await api.delete(`/api/assistant/conversations/${currentConversationId.value}`, { headers: authHeaders.value })
    message.success('会话已删除')
    createConversation()
    await refreshConversations()
  } catch (err) {
    message.error(err?.response?.data?.detail || '删除会话失败')
  }
}

async function refreshFiles() {
  if (!authStore.isLoggedIn) return
  const res = await api.get('/api/assistant/files', { headers: authHeaders.value })
  files.value = Array.isArray(res.data?.data) ? res.data.data : []
}

function toggleFile(fileId) {
  if (!fileId) return
  const idx = selectedFileIds.value.indexOf(fileId)
  if (idx >= 0) {
    selectedFileIds.value.splice(idx, 1)
  } else {
    selectedFileIds.value.push(fileId)
  }
}

async function removeFile(fileId) {
  if (!fileId) return
  try {
    await api.delete(`/api/assistant/files/${fileId}`, { headers: authHeaders.value })
    selectedFileIds.value = selectedFileIds.value.filter((id) => id !== fileId)
    await refreshFiles()
    message.success('文件已删除')
  } catch (err) {
    message.error(err?.response?.data?.detail || '删除文件失败')
  }
}

async function uploadFiles(event) {
  const picked = Array.from(event.target.files || [])
  event.target.value = ''
  if (!picked.length) return
  if (!authStore.isLoggedIn) {
    message.error('请先登录')
    return
  }

  uploading.value = true
  try {
    for (const file of picked) {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('purpose', filePurpose.value)
      await api.post('/api/assistant/files', formData, { headers: authHeaders.value })
    }
    await refreshFiles()
    message.success('文件上传成功')
  } catch (err) {
    message.error(err?.response?.data?.detail || '文件上传失败')
  } finally {
    uploading.value = false
  }
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || sending.value) return
  if (!authStore.isLoggedIn) {
    message.error('请先登录')
    return
  }

  const localId = `local-${Date.now()}`
  chatMessages.value.push({ id: localId, role: 'user', content: text, created_at: Date.now() / 1000 })
  inputText.value = ''
  sending.value = true
  await scrollToBottom()

  try {
    const res = await api.post(
      '/api/assistant/chat',
      {
        message: text,
        conversation_id: currentConversationId.value || undefined,
        model: model.value || undefined,
        max_history_messages: maxHistoryMessages.value,
        file_ids: selectedFileIds.value
      },
      { headers: authHeaders.value }
    )
    const conversationId = res.data?.conversation_id
    if (conversationId) {
      currentConversationId.value = conversationId
      await loadMessages(conversationId)
      await refreshConversations()
    }
  } catch (err) {
    message.error(err?.response?.data?.detail || '发送失败')
    chatMessages.value = chatMessages.value.filter((item) => item.id !== localId)
  } finally {
    sending.value = false
  }
}

async function initializeAssistant() {
  if (!authStore.isLoggedIn) return
  await Promise.all([refreshConversations(), refreshFiles()])
}

watch(
  () => authStore.isLoggedIn,
  async (loggedIn) => {
    if (!loggedIn) {
      conversations.value = []
      files.value = []
      createConversation()
      return
    }
    await initializeAssistant()
  }
)

watch(
  chatMessages,
  async () => {
    await scrollToBottom()
  },
  { deep: true }
)

onMounted(async () => {
  await initializeAssistant()
})
</script>
