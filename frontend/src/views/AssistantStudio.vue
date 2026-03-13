<template>
  <div class="h-full grid grid-cols-1 xl:grid-cols-12 gap-6 pb-4">
    <!-- Left Sidebar -->
    <div class="xl:col-span-4 flex flex-col gap-6 h-full min-h-0">
      
      <!-- Conversations -->
      <div class="flex-1 min-h-0 flex flex-col bg-white/80 backdrop-blur-xl border border-white/60 rounded-[24px] p-5 shadow-sm">
        <div class="flex items-center justify-between mb-4 shrink-0">
          <div class="flex items-center gap-2">
            <MessageSquare class="w-5 h-5 text-indigo-500" />
            <h3 class="text-sm font-bold text-slate-800">会话列表</h3>
          </div>
          <button
            class="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-50 text-indigo-600 border border-indigo-100 hover:bg-indigo-100 transition-colors"
            @click="createConversation"
          >
            <Plus class="w-3.5 h-3.5" /> 新建
          </button>
        </div>
        
        <div class="flex-1 overflow-y-auto custom-scrollbar space-y-2 pr-2">
          <button
            v-for="item in conversations"
            :key="item.conversation_id"
            class="w-full text-left px-4 py-3 rounded-xl border transition-all duration-200 group relative"
            :class="item.conversation_id === currentConversationId ? 'border-indigo-300 bg-indigo-50/80 shadow-sm' : 'border-slate-100 bg-white hover:border-indigo-200 hover:shadow-sm'"
            @click="pickConversation(item.conversation_id)"
          >
            <div class="flex justify-between items-start mb-1">
              <p class="text-xs font-bold truncate pr-6" :class="item.conversation_id === currentConversationId ? 'text-indigo-700' : 'text-slate-700 group-hover:text-indigo-600'">
                {{ item.title || item.conversation_id }}
              </p>
            </div>
            <p class="text-[11px] text-slate-400 truncate flex items-center gap-1">
              <Bot class="w-3 h-3" /> {{ item.model || 'kimi-k2.5' }}
            </p>
            <button
              v-if="item.conversation_id === currentConversationId && authStore.isLoggedIn"
              class="absolute right-2 top-2 p-1.5 rounded-lg text-red-400 hover:text-red-600 hover:bg-red-50 transition-colors opacity-0 group-hover:opacity-100"
              @click.stop="removeConversation"
              title="删除会话"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </button>
          
          <div v-if="!conversations.length" class="h-full flex flex-col items-center justify-center text-slate-400 space-y-2 pb-8">
            <MessageSquare class="w-8 h-8 opacity-50" />
            <span class="text-xs">{{ authStore.isLoggedIn ? '暂无历史会话' : '访客模式不保存云端会话' }}</span>
          </div>
        </div>
      </div>

      <!-- Files -->
      <div class="flex-1 min-h-0 flex flex-col bg-white/80 backdrop-blur-xl border border-white/60 rounded-[24px] p-5 shadow-sm">
        <div class="flex items-center justify-between mb-4 shrink-0">
          <div class="flex items-center gap-2">
            <Paperclip class="w-5 h-5 text-indigo-500" />
            <h3 class="text-sm font-bold text-slate-800">文件上下文</h3>
          </div>
          <button class="text-slate-400 hover:text-indigo-500 transition-colors p-1" @click="refreshFiles" title="刷新文件">
            <RefreshCw class="w-4 h-4" />
          </button>
        </div>

        <div class="grid grid-cols-3 gap-2 mb-4 shrink-0 bg-slate-100/50 p-1 rounded-xl">
          <button
            v-for="item in purposeOptions"
            :key="item.value"
            class="flex items-center justify-center gap-1.5 px-2 py-1.5 text-xs font-medium rounded-lg transition-all duration-200"
            :class="filePurpose === item.value ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
            @click="filePurpose = item.value"
          >
            <component :is="item.icon" class="w-3.5 h-3.5" />
            {{ item.label }}
          </button>
        </div>

        <label class="block w-full mb-3 shrink-0 group" :class="fileApiUnavailable ? 'opacity-60 cursor-not-allowed' : ''">
          <input type="file" multiple class="hidden" @change="uploadFiles" />
          <div class="w-full flex flex-col items-center justify-center py-4 text-xs font-semibold rounded-xl border-2 border-dashed transition-colors"
               :class="uploading ? 'border-indigo-300 bg-indigo-50 text-indigo-600' : 'border-slate-200 bg-slate-50 text-slate-500 group-hover:border-indigo-300 group-hover:bg-indigo-50/50 group-hover:text-indigo-500 cursor-pointer'">
            <UploadCloud v-if="!uploading" class="w-6 h-6 mb-2 opacity-50 group-hover:opacity-100" />
            <RefreshCw v-else class="w-6 h-6 mb-2 animate-spin" />
            <span>{{ fileApiUnavailable ? '文件功能未启用' : (uploading ? '上传中...' : '点击或拖拽上传文件') }}</span>
          </div>
        </label>

        <div v-if="isGuestMode" class="mb-3 shrink-0 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
          访客模式支持文件上下文，但不保存云端会话历史。
        </div>
        <div v-if="fileApiUnavailable" class="mb-3 shrink-0 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
          {{ fileApiUnavailableReason || '文件接口暂不可用，请在后端配置 Moonshot 可用 key 后再使用上传。' }}
        </div>

        <div class="flex-1 overflow-y-auto custom-scrollbar space-y-2 pr-2">
          <label
            v-for="f in files"
            :key="f.id"
            class="flex items-center gap-3 p-3 rounded-xl border transition-all cursor-pointer group"
            :class="selectedFileIds.includes(f.id) ? 'border-indigo-300 bg-indigo-50/50' : 'border-slate-100 bg-white hover:border-slate-200'"
          >
            <div class="relative flex items-center justify-center shrink-0">
              <input
                v-if="f.purpose === 'file-extract'"
                type="checkbox"
                class="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500/30 transition-colors cursor-pointer"
                :checked="selectedFileIds.includes(f.id)"
                @change="toggleFile(f.id)"
              />
              <div v-else class="w-4 h-4 rounded-full border-2 border-slate-200 flex items-center justify-center">
                <div class="w-2 h-2 rounded-full bg-slate-300"></div>
              </div>
            </div>
            
            <div class="flex-1 min-w-0">
              <p class="text-xs font-semibold text-slate-700 truncate" :title="f.filename || f.id">{{ f.filename || f.id }}</p>
              <p class="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5">
                <span class="px-1.5 py-0.5 rounded bg-slate-100">{{ f.purpose }}</span>
                <span>{{ formatBytes(f.bytes) }}</span>
              </p>
            </div>
            
            <button class="p-1.5 shrink-0 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100" @click.prevent="removeFile(f.id)" title="删除文件">
              <Trash2 class="w-4 h-4" />
            </button>
          </label>
          
          <div v-if="!files.length && !fileApiUnavailable" class="text-xs text-slate-400 py-8 text-center flex flex-col items-center">
            <FileText class="w-8 h-8 opacity-20 mb-2" />
            暂无已上传文件
          </div>
        </div>
      </div>
    </div>

    <!-- Right Chat Panel -->
    <div class="xl:col-span-8 flex flex-col h-full bg-white/90 backdrop-blur-xl border border-white/60 rounded-[24px] shadow-sm overflow-hidden relative min-h-[600px] xl:min-h-0">
      <!-- Chat Header Settings -->
      <div class="shrink-0 border-b border-slate-100/80 bg-white/50 px-5 py-3.5 flex flex-wrap items-center justify-between gap-4 z-10">
        <div class="flex flex-wrap items-center gap-3">
          <div class="flex items-center gap-2 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100">
            <Bot class="w-4 h-4 text-slate-400" />
            <input v-model.trim="model" class="w-24 sm:w-28 text-xs font-medium bg-transparent border-none outline-none focus:ring-0 p-0 text-slate-700" placeholder="模型名称" />
          </div>
          
          <div class="flex items-center gap-2 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100" title="保留的历史消息条数">
            <MessageSquare class="w-4 h-4 text-slate-400" />
            <input v-model.number="maxHistoryMessages" type="number" min="4" max="100" class="w-10 text-xs font-medium bg-transparent border-none outline-none focus:ring-0 p-0 text-slate-700 text-center" />
            <span class="text-xs text-slate-400">条</span>
          </div>

          <label class="flex items-center gap-2 cursor-pointer group bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100">
            <div class="relative flex items-center justify-center">
              <input v-model="enableTools" type="checkbox" class="w-3.5 h-3.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500/30 cursor-pointer" />
            </div>
            <span class="text-xs font-medium text-slate-600 group-hover:text-slate-800 transition-colors">联网/工具</span>
          </label>
          
          <div v-if="enableTools" class="flex items-center gap-2 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100 transition-all">
            <Settings2 class="w-4 h-4 text-slate-400" />
            <span class="text-xs text-slate-500">轮次</span>
            <input
              v-model.number="maxToolRounds"
              type="number"
              min="1"
              max="10"
              class="w-8 text-xs font-medium bg-transparent border-none outline-none focus:ring-0 p-0 text-slate-700 text-center"
            />
          </div>
        </div>
        
        <div class="flex items-center gap-2" v-if="selectedFileIds.length > 0">
          <span class="flex items-center gap-1.5 px-3 py-1 bg-indigo-50 text-indigo-600 text-[11px] font-semibold rounded-full border border-indigo-100">
            <Paperclip class="w-3 h-3" />
            已挂载 {{ selectedFileIds.length }} 个文件
          </span>
        </div>
      </div>

      <div v-if="!canUseAssistant" class="flex-1 flex flex-col items-center justify-center text-slate-400 space-y-4">
        <div class="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-2">
          <User class="w-8 h-8 text-slate-300" />
        </div>
        <p class="text-sm font-medium">请先登录或开启访客模式后使用 AI 助手</p>
      </div>

      <template v-else>
        <!-- Messages Area -->
        <div ref="messagePanel" class="flex-1 overflow-y-auto custom-scrollbar p-5 space-y-6 bg-slate-50/30 scroll-smooth">
          <div v-if="enableTools && latestToolEvents.length" class="max-w-[90%] mx-auto mb-6 p-4 rounded-2xl border border-amber-200/60 bg-gradient-to-br from-amber-50 to-orange-50/30 text-xs text-amber-800 shadow-sm backdrop-blur-sm">
            <div class="flex items-center gap-2 font-bold mb-2 text-amber-900">
              <Wrench class="w-4 h-4" /> 本轮工具调用记录
            </div>
            <div class="flex flex-wrap gap-2">
              <span v-for="(item, idx) in latestToolEvents" :key="idx" class="px-2 py-1 bg-white/60 rounded-md border border-amber-100 font-mono text-[11px]">
                {{ item.tool || 'unknown' }} <span :class="item.status === 'error' ? 'text-red-500' : 'text-emerald-600'">({{ item.status || 'ok' }})</span>
              </span>
            </div>
          </div>
          
          <div
            v-for="msg in chatMessages"
            :key="msg.id"
            class="flex items-start gap-4"
            :class="msg.role === 'user' ? 'flex-row-reverse' : ''"
          >
            <!-- Avatar -->
            <div class="w-8 h-8 rounded-full flex items-center justify-center shrink-0 shadow-sm" :class="msg.role === 'user' ? 'bg-indigo-100 text-indigo-600' : 'bg-white border border-slate-200 text-emerald-600'">
              <User v-if="msg.role === 'user'" class="w-4 h-4" />
              <Bot v-else class="w-4 h-4" />
            </div>
            
            <!-- Message Bubble -->
            <div class="max-w-[80%] flex flex-col" :class="msg.role === 'user' ? 'items-end' : 'items-start'">
              <div class="w-full flex items-center justify-between mb-1 px-1 gap-3">
                <div class="text-[11px] text-slate-400">{{ msg.role === 'user' ? '我' : 'AI 助手' }}</div>
                <button
                  v-if="msg.role === 'assistant'"
                  class="inline-flex items-center gap-1 text-[11px] text-indigo-500 hover:text-indigo-600 transition-colors"
                  @click="saveMessageAsHtml(msg)"
                  title="保存为 HTML"
                >
                  <Download class="w-3.5 h-3.5" />
                  HTML
                </button>
              </div>
              <div
                class="rounded-2xl px-5 py-3.5 text-[13px] sm:text-sm leading-relaxed shadow-sm"
                :class="msg.role === 'user' ? 'bg-indigo-600 text-white rounded-tr-sm whitespace-pre-wrap' : 'bg-white border border-slate-100 text-slate-700 rounded-tl-sm'"
              >
                <div
                  v-if="msg.role === 'assistant' && !msg.content && msg.id === streamingAssistantId"
                  class="flex items-center gap-1.5 h-6"
                >
                  <span class="w-2 h-2 rounded-full bg-slate-300 animate-bounce" style="animation-delay: 0ms"></span>
                  <span class="w-2 h-2 rounded-full bg-slate-300 animate-bounce" style="animation-delay: 150ms"></span>
                  <span class="w-2 h-2 rounded-full bg-slate-300 animate-bounce" style="animation-delay: 300ms"></span>
                </div>
                <div v-else-if="msg.role === 'assistant'" class="assistant-render" v-html="renderAssistantMessage(msg.content)"></div>
                <template v-else>{{ msg.content }}</template>
              </div>
            </div>
          </div>
          
          <div v-if="!chatMessages.length && !sending" class="h-full flex flex-col items-center justify-center text-slate-400 space-y-4 pt-10 pb-20">
            <div class="w-16 h-16 bg-white shadow-sm border border-slate-100 rounded-full flex items-center justify-center">
              <Bot class="w-8 h-8 text-indigo-300" />
            </div>
            <div class="text-center space-y-2">
              <p class="text-sm font-medium text-slate-600">今天想聊点什么？</p>
              <p class="text-xs">勾选 <code class="px-1 py-0.5 bg-slate-100 rounded text-slate-500">文档(file-extract)</code> 格式的文件后将自动注入上下文</p>
            </div>
          </div>
          
          <!-- Typing indicator -->
          <div v-if="sending && !streamingAssistantId" class="flex items-start gap-4 animate-pulse">
            <div class="w-8 h-8 rounded-full flex items-center justify-center shrink-0 shadow-sm bg-white border border-slate-200 text-emerald-600">
              <Bot class="w-4 h-4" />
            </div>
            <div class="flex flex-col items-start">
              <div class="text-[11px] text-slate-400 mb-1 px-1">AI 助手</div>
              <div class="rounded-2xl px-5 py-3.5 bg-white border border-slate-100 rounded-tl-sm flex items-center gap-1.5 h-12 shadow-sm">
                <span class="w-2 h-2 rounded-full bg-slate-300 animate-bounce" style="animation-delay: 0ms"></span>
                <span class="w-2 h-2 rounded-full bg-slate-300 animate-bounce" style="animation-delay: 150ms"></span>
                <span class="w-2 h-2 rounded-full bg-slate-300 animate-bounce" style="animation-delay: 300ms"></span>
              </div>
            </div>
          </div>
        </div>

        <!-- Input Area -->
        <div class="shrink-0 p-4 bg-white/80 backdrop-blur-md border-t border-slate-100/80 z-10">
          <div class="relative bg-white rounded-2xl border border-slate-200 shadow-sm focus-within:border-indigo-400 focus-within:ring-4 focus-within:ring-indigo-500/10 transition-all">
            <textarea
              v-model="inputText"
              rows="3"
              class="w-full px-5 py-4 pb-12 text-sm bg-transparent border-none outline-none resize-none custom-scrollbar rounded-2xl"
              placeholder="输入你的问题... (Enter 发送，Shift+Enter 换行)"
              @keydown.enter.exact.prevent="sendMessage"
            ></textarea>
            
            <div class="absolute right-3 bottom-3 flex items-center gap-2">
              <div v-if="inputText.trim() && !sending" class="text-[10px] text-slate-400 font-medium mr-1 hidden sm:block">
                按 Enter 发送
              </div>
              <button
                class="flex items-center justify-center w-8 h-8 sm:w-9 sm:h-9 rounded-xl transition-all"
                :class="sending || !inputText.trim() ? 'bg-slate-100 text-slate-400 cursor-not-allowed' : 'bg-indigo-600 text-white hover:bg-indigo-500 hover:shadow-md hover:-translate-y-0.5 active:translate-y-0'"
                :disabled="sending || !inputText.trim()"
                @click="sendMessage"
                title="发送消息"
              >
                <RefreshCw v-if="sending" class="w-4 h-4 animate-spin" />
                <Send v-else class="w-4 h-4 -ml-0.5" />
              </button>
            </div>
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
import {
  MessageSquare, Plus, Trash2, RefreshCw, UploadCloud,
  FileText, Image as ImageIcon, Video, Send, Bot, User,
  Settings2, Paperclip, Wrench, Download
} from 'lucide-vue-next'

const authStore = useAuthStore()
const message = useMessage()

const model = ref('kimi-k2.5')
const maxHistoryMessages = ref(20)
const enableTools = ref(false)
const maxToolRounds = ref(4)

const conversations = ref([])
const currentConversationId = ref('')
const chatMessages = ref([])
const inputText = ref('')
const sending = ref(false)
const streamingAssistantId = ref('')
const latestToolEvents = ref([])

const files = ref([])
const selectedFileIds = ref([])
const filePurpose = ref('file-extract')
const uploading = ref(false)
const fileApiUnavailable = ref(false)
const fileApiUnavailableReason = ref('')

const messagePanel = ref(null)

const purposeOptions = [
  { label: '文档', value: 'file-extract', icon: FileText },
  { label: '图片', value: 'image', icon: ImageIcon },
  { label: '视频', value: 'video', icon: Video }
]

const authHeaders = computed(() => {
  if (!authStore.token) return {}
  return { Authorization: `Bearer ${authStore.token}` }
})
const canUseAssistant = computed(() => authStore.isLoggedIn || authStore.isGuest)
const isGuestMode = computed(() => authStore.isGuest && !authStore.isLoggedIn)

const CODE_FENCE_RE = /```([a-zA-Z0-9_+-]*)\n?([\s\S]*?)```/g

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

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function renderInlineMarkdown(text) {
  const placeholders = []
  let html = escapeHtml(text || '')
  html = html.replace(/`([^`\n]+)`/g, (_, code) => {
    const token = `%%INLINE_CODE_${placeholders.length}%%`
    placeholders.push(`<code class="assistant-inline-code">${code}</code>`)
    return token
  })
  html = html.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
  html = html.replace(/%%INLINE_CODE_(\d+)%%/g, (_, idx) => placeholders[Number(idx)] || '')
  return html
}

function renderTextBlock(block) {
  const source = String(block || '')
  if (!source.trim()) return ''
  const lines = source.split('\n')
  if (lines.every((line) => /^\s*[-*+]\s+/.test(line))) {
    const items = lines
      .map((line) => line.replace(/^\s*[-*+]\s+/, '').trim())
      .filter(Boolean)
      .map((item) => `<li>${renderInlineMarkdown(item)}</li>`)
      .join('')
    return `<ul>${items}</ul>`
  }
  if (lines.every((line) => /^\s*\d+\.\s+/.test(line))) {
    const items = lines
      .map((line) => line.replace(/^\s*\d+\.\s+/, '').trim())
      .filter(Boolean)
      .map((item) => `<li>${renderInlineMarkdown(item)}</li>`)
      .join('')
    return `<ol>${items}</ol>`
  }
  if (lines.every((line) => /^\s*>\s?/.test(line))) {
    const content = lines
      .map((line) => line.replace(/^\s*>\s?/, ''))
      .map((line) => renderInlineMarkdown(line))
      .join('<br>')
    return `<blockquote>${content}</blockquote>`
  }
  if (lines.length === 1) {
    const single = lines[0]
    const heading = single.match(/^\s*(#{1,3})\s+(.+)$/)
    if (heading) {
      const level = Math.min(3, heading[1].length)
      return `<h${level}>${renderInlineMarkdown(heading[2].trim())}</h${level}>`
    }
  }
  return `<p>${lines.map((line) => renderInlineMarkdown(line)).join('<br>')}</p>`
}

function renderMarkdownText(text) {
  const normalized = String(text || '').replace(/\r\n/g, '\n')
  if (!normalized.trim()) return ''
  return normalized
    .split(/\n{2,}/)
    .map((block) => renderTextBlock(block))
    .join('')
}

function renderAssistantMessage(rawContent) {
  const source = String(rawContent || '').replace(/\r\n/g, '\n')
  if (!source.trim()) return '<p></p>'

  let html = ''
  let start = 0
  CODE_FENCE_RE.lastIndex = 0

  let match
  while ((match = CODE_FENCE_RE.exec(source)) !== null) {
    html += renderMarkdownText(source.slice(start, match.index))
    const language = escapeHtml((match[1] || 'code').trim() || 'code')
    const code = escapeHtml((match[2] || '').replace(/\n$/, ''))
    html += `<div class="assistant-code-block"><div class="assistant-code-head">${language}</div><pre><code>${code}</code></pre></div>`
    start = match.index + match[0].length
  }
  html += renderMarkdownText(source.slice(start))

  return html || '<p></p>'
}

function extractHtmlCodeOnly(rawContent) {
  const source = String(rawContent || '').replace(/\r\n/g, '\n')
  if (!source.trim()) return ''
  const htmlChunks = []
  const fenceRe = /```([a-zA-Z0-9_+-]*)\n?([\s\S]*?)```/g
  let match
  while ((match = fenceRe.exec(source)) !== null) {
    const lang = String(match[1] || '').trim().toLowerCase()
    const code = String(match[2] || '').replace(/\n$/, '')
    if (lang === 'html' || lang === 'htm') {
      htmlChunks.push(code)
    }
  }
  if (htmlChunks.length) return htmlChunks.join('\n\n')

  const htmlDoc = source.match(/<!doctype\s+html[\s\S]*<\/html>/i) || source.match(/<html[\s\S]*<\/html>/i)
  if (htmlDoc && htmlDoc[0]) return htmlDoc[0].trim()
  return ''
}

function saveMessageAsHtml(msg) {
  if (!msg?.content) {
    message.warning('没有可保存的内容')
    return
  }
  const htmlOnly = extractHtmlCodeOnly(msg.content)
  if (!htmlOnly) {
    message.warning('未检测到 HTML 代码块，请使用 ```html ... ``` 格式输出')
    return
  }
  const blob = new Blob([htmlOnly], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  const fallbackId = Date.now()
  link.href = url
  link.download = `assistant-${msg.id || fallbackId}.html`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  message.success('已保存为 HTML')
}

function extractErrorDetail(err) {
  return String(err?.response?.data?.detail || err?.message || '')
}

async function extractResponseDetail(response) {
  const contentType = String(response.headers.get('content-type') || '').toLowerCase()
  try {
    if (contentType.includes('application/json')) {
      const data = await response.json()
      return String(data?.detail || data?.message || '')
    }
    return String((await response.text()) || '')
  } catch {
    return ''
  }
}

function buildAssistantRequestPayload(text) {
  return {
    message: text,
    conversation_id: currentConversationId.value || undefined,
    model: model.value || undefined,
    max_history_messages: maxHistoryMessages.value,
    file_ids: selectedFileIds.value,
    enable_tools: enableTools.value,
    max_tool_rounds: enableTools.value ? Math.max(1, Math.min(10, Number(maxToolRounds.value || 4))) : 1
  }
}

function updateAssistantMessage(messageId, content) {
  const target = chatMessages.value.find((item) => item.id === messageId)
  if (target) {
    target.content = content
  }
}

function removeChatMessage(messageId) {
  chatMessages.value = chatMessages.value.filter((item) => item.id !== messageId)
}

function handleSseEventBlock(block, onEvent) {
  const lines = String(block || '').split('\n')
  let eventName = 'message'
  const dataLines = []

  for (const rawLine of lines) {
    const line = rawLine.replace(/\r$/, '')
    if (!line || line.startsWith(':')) continue
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim() || 'message'
      continue
    }
    if (line.startsWith('data:')) {
      let value = line.slice(5)
      if (value.startsWith(' ')) value = value.slice(1)
      dataLines.push(value)
    }
  }

  if (!dataLines.length) return

  const rawData = dataLines.join('\n')
  let payload = {}
  try {
    payload = JSON.parse(rawData)
  } catch {
    payload = { raw: rawData }
  }
  onEvent(eventName, payload)
}

function flushSseBuffer(buffer, onEvent, force = false) {
  const normalized = String(buffer || '').replace(/\r\n/g, '\n')
  const parts = normalized.split('\n\n')
  const limit = force ? parts.length : Math.max(parts.length - 1, 0)

  for (let index = 0; index < limit; index += 1) {
    const block = parts[index]
    if (!block.trim()) continue
    handleSseEventBlock(block, onEvent)
  }

  if (force) return ''
  return parts[parts.length - 1] || ''
}

function isFileApiUnavailableError(status, detail) {
  const text = String(detail || '').toLowerCase()
  if (status === 400) {
    return (
      text.includes('file api requires moonshot_api_key') ||
      text.includes('missing file api key') ||
      text.includes('unsupported file gateways') ||
      text.includes('do not support /v1/files') ||
      text.includes('please configure moonshot_api_key')
    )
  }
  return status === 503 && text.includes('no available channels for model')
}

function toFileApiUnavailableReason(detail) {
  const text = String(detail || '')
  if (!text) return '文件接口暂不可用，请配置 Moonshot 可用 key（或 MOONSHOT_API_KEY）。'
  if (/unsupported file gateways/i.test(text) || /no available channels for model/i.test(text)) {
    return '当前系统 key 网关不支持 /v1/files，请在系统配置中为提示词通道补充 Moonshot 可用 key。'
  }
  return text
}

function markFileApiUnavailable(detail = '') {
  fileApiUnavailable.value = true
  fileApiUnavailableReason.value = toFileApiUnavailableReason(detail)
  files.value = []
  selectedFileIds.value = []
}

async function scrollToBottom() {
  await nextTick()
  const el = messagePanel.value
  if (el) {
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
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
  if (!authStore.isLoggedIn) {
    createConversation()
    return
  }
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
  try {
    const res = await api.get('/api/assistant/files', { headers: authHeaders.value })
    files.value = Array.isArray(res.data?.data) ? res.data.data : []
    fileApiUnavailable.value = false
    fileApiUnavailableReason.value = ''
  } catch (err) {
    const status = err?.response?.status
    const detail = extractErrorDetail(err)
    if (isFileApiUnavailableError(status, detail)) {
      markFileApiUnavailable(detail)
      return
    }
    message.error(detail || '文件列表加载失败')
  }
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
  if (fileApiUnavailable.value) {
    message.warning(fileApiUnavailableReason.value || '文件功能未启用')
    return
  }
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
  if (fileApiUnavailable.value) {
    message.warning(fileApiUnavailableReason.value || '文件功能未启用')
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
    const status = err?.response?.status
    const detail = extractErrorDetail(err)
    if (isFileApiUnavailableError(status, detail)) {
      markFileApiUnavailable(detail)
      message.warning(fileApiUnavailableReason.value || '文件接口暂不可用')
      return
    }
    message.error(detail || '文件上传失败')
  } finally {
    uploading.value = false
  }
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || sending.value) return
  if (!canUseAssistant.value) {
    message.error('请先登录或开启访客模式')
    return
  }

  const localId = `local-${Date.now()}`
  const assistantId = `assistant-pending-${Date.now()}`
  chatMessages.value.push({ id: localId, role: 'user', content: text, created_at: Date.now() / 1000 })
  chatMessages.value.push({ id: assistantId, role: 'assistant', content: '', created_at: Date.now() / 1000 })
  streamingAssistantId.value = assistantId
  inputText.value = ''
  sending.value = true
  latestToolEvents.value = []
  await scrollToBottom()

  try {
    const response = await fetch('/api/assistant/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...authHeaders.value
      },
      body: JSON.stringify(buildAssistantRequestPayload(text))
    })

    if (!response.ok) {
      throw new Error((await extractResponseDetail(response)) || '发送失败')
    }
    if (!response.body) {
      throw new Error('浏览器未返回可读流')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let streamedText = ''
    let sawDone = false
    let resolvedConversationId = currentConversationId.value

    const handleStreamEvent = (eventName, payload) => {
      if (eventName === 'meta') {
        if (payload?.conversation_id) {
          resolvedConversationId = payload.conversation_id
          currentConversationId.value = payload.conversation_id
        }
        latestToolEvents.value = Array.isArray(payload?.tool_events) ? payload.tool_events : []
        return
      }

      if (eventName === 'delta') {
        const textDelta = String(payload?.text || '')
        if (!textDelta) return
        streamedText += textDelta
        updateAssistantMessage(assistantId, streamedText)
        return
      }

      if (eventName === 'done') {
        sawDone = true
        if (payload?.conversation_id) {
          resolvedConversationId = payload.conversation_id
          currentConversationId.value = payload.conversation_id
        }
        latestToolEvents.value = Array.isArray(payload?.tool_events) ? payload.tool_events : latestToolEvents.value
        const finalMessage = String(payload?.message || streamedText || '').trim()
        updateAssistantMessage(assistantId, finalMessage)
        streamedText = finalMessage
        return
      }

      if (eventName === 'error') {
        throw new Error(String(payload?.detail || '发送失败'))
      }
    }

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      buffer = flushSseBuffer(buffer, handleStreamEvent)
    }

    buffer += decoder.decode()
    flushSseBuffer(buffer, handleStreamEvent, true)

    if (!sawDone) {
      throw new Error('流式输出未正常结束')
    }

    if (resolvedConversationId) {
      currentConversationId.value = resolvedConversationId
    }

    if (authStore.isLoggedIn && resolvedConversationId) {
      await loadMessages(resolvedConversationId)
      await refreshConversations()
    } else if (!streamedText.trim()) {
      removeChatMessage(assistantId)
    }
  } catch (err) {
    removeChatMessage(assistantId)
    if (!currentConversationId.value && !authStore.isLoggedIn) {
      chatMessages.value = chatMessages.value.filter((item) => item.id !== localId)
    }
    message.error(extractErrorDetail(err) || '发送失败')
  } finally {
    streamingAssistantId.value = ''
    sending.value = false
    await scrollToBottom()
  }
}

async function initializeAssistant() {
  if (!canUseAssistant.value) return
  if (!authStore.isLoggedIn) {
    conversations.value = []
    latestToolEvents.value = []
    try {
      await refreshFiles()
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || ''
      message.error(detail || '文件列表加载失败')
    }
    return
  }
  const [convResult, fileResult] = await Promise.allSettled([refreshConversations(), refreshFiles()])
  if (convResult.status === 'rejected') throw convResult.reason
  if (fileResult.status === 'rejected') {
    const detail = fileResult.reason?.response?.data?.detail || fileResult.reason?.message || ''
    message.error(detail || '文件列表加载失败')
  }
}

watch(
  () => [authStore.isLoggedIn, authStore.isGuest],
  async ([loggedIn, isGuest]) => {
    if (!loggedIn && !isGuest) {
      conversations.value = []
      files.value = []
      latestToolEvents.value = []
      fileApiUnavailable.value = false
      fileApiUnavailableReason.value = ''
      createConversation()
      return
    }
    try {
      await initializeAssistant()
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || ''
      message.error(detail || '初始化助手失败')
    }
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
  try {
    await initializeAssistant()
  } catch (err) {
    const detail = err?.response?.data?.detail || err?.message || ''
    message.error(detail || '初始化助手失败')
  }
})
</script>

<style scoped>
:deep(.assistant-render h1),
:deep(.assistant-render h2),
:deep(.assistant-render h3) {
  margin: 0 0 0.5rem;
  color: #0f172a;
  font-weight: 700;
}

:deep(.assistant-render h1) {
  font-size: 1.05rem;
}

:deep(.assistant-render h2) {
  font-size: 1rem;
}

:deep(.assistant-render h3) {
  font-size: 0.95rem;
}

:deep(.assistant-render p) {
  margin: 0 0 0.65rem;
  line-height: 1.75;
}

:deep(.assistant-render p:last-child) {
  margin-bottom: 0;
}

:deep(.assistant-render ul),
:deep(.assistant-render ol) {
  margin: 0 0 0.65rem 1.25rem;
  padding: 0;
}

:deep(.assistant-render li) {
  margin: 0.35rem 0;
  line-height: 1.75;
}

:deep(.assistant-render blockquote) {
  margin: 0 0 0.65rem;
  padding: 0.55rem 0.75rem;
  border-left: 3px solid #94a3b8;
  background: #f8fafc;
  color: #334155;
}

:deep(.assistant-render .assistant-inline-code) {
  display: inline-block;
  padding: 0 0.3rem;
  border-radius: 0.35rem;
  background: #eef2ff;
  color: #4338ca;
  font-size: 0.88em;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
}

:deep(.assistant-render .assistant-code-block) {
  margin: 0 0 0.75rem;
  border: 1px solid #dbeafe;
  border-radius: 0.7rem;
  overflow: hidden;
}

:deep(.assistant-render .assistant-code-head) {
  padding: 0.35rem 0.65rem;
  font-size: 0.72rem;
  color: #1e3a8a;
  text-transform: lowercase;
  background: #eff6ff;
  border-bottom: 1px solid #dbeafe;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
}

:deep(.assistant-render pre) {
  margin: 0;
  padding: 0.75rem;
  overflow-x: auto;
  background: #0f172a;
  color: #e2e8f0;
  line-height: 1.6;
}

:deep(.assistant-render pre code) {
  font-size: 0.82rem;
  white-space: pre;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
}
</style>
