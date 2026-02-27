<template>
  <DigitalHumanPanel v-if="activeMode === 'digital_human'">
    <template #mode-selector>
      <div class="space-y-1.5 mb-4">
        <label class="typo-label pl-1">{{ localeStore.t('video.mode') }}</label>
        <div class="bg-slate-50 p-1 rounded-xl flex gap-1 border border-slate-100">
          <button
            v-for="modeItem in modeOptions"
            :key="modeItem.value"
            @click="setMode(modeItem.value)"
            class="flex-1 py-2 rounded-lg typo-button-compact transition-all"
            :class="activeMode === modeItem.value ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
          >
            {{ modeItem.label }}
          </button>
        </div>
      </div>
    </template>
  </DigitalHumanPanel>

  <div v-else class="h-[calc(100vh-140px)] grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch overflow-hidden">
      <!-- Left: Controls -->
      <div class="lg:col-span-4 flex flex-col h-full min-h-0 animate-slide-up">
        <div class="bg-white/80 backdrop-blur-xl border border-white/60 rounded-[24px] p-6 shadow-sm flex flex-col h-full overflow-y-auto custom-scrollbar hover:shadow-md transition-shadow duration-300 space-y-4">
          <div class="flex items-center justify-between border-b border-slate-100 pb-4">
            <h3 class="typo-section-title flex items-center gap-2">
              <span class="w-2 h-2 rounded-full bg-indigo-500"></span>
              {{ activeMode === 'text' ? localeStore.t('video.text_title') : localeStore.t('video.image_title') }}
            </h3>
            <span class="typo-badge text-indigo-500 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">Beta</span>
          </div>

          <div class="space-y-1.5">
            <label class="typo-label pl-1">{{ localeStore.t('video.mode') }}</label>
            <div class="bg-slate-50 p-1 rounded-xl flex gap-1 border border-slate-100">
              <button
                v-for="modeItem in modeOptions"
                :key="modeItem.value"
                @click="setMode(modeItem.value)"
                class="flex-1 py-2 rounded-lg typo-button-compact transition-all"
                :class="activeMode === modeItem.value ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
              >
                {{ modeItem.label }}
              </button>
            </div>
          </div>

          <div class="space-y-2">
            <label class="typo-label">{{ localeStore.t('video.model') }}</label>
            <n-select v-model:value="settings.model" :options="videoModelSelectOptions" :disabled="!videoModelOptions.length" size="small" />
            <p v-if="videoCostHint" class="text-xs text-slate-400">{{ videoCostHint }}</p>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div class="space-y-2">
              <label class="typo-label">{{ localeStore.t('video.ratio') }}</label>
              <select v-model="settings.aspectRatio" class="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg typo-input outline-none transition-colors">
                <option value="16:9">16:9</option>
                <option value="9:16">9:16</option>
              </select>
            </div>
            <div class="space-y-2">
              <label class="typo-label">{{ localeStore.t('video.duration') }}</label>
              <select v-model.number="settings.durationSeconds" class="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg typo-input outline-none transition-colors">
                <option :value="4">4s</option>
                <option :value="6">6s</option>
                <option :value="8">8s</option>
              </select>
            </div>
            <div class="space-y-2">
              <label class="typo-label">{{ localeStore.t('video.resolution') }}</label>
              <select v-model="settings.resolution" class="w-full px-3 py-2 bg-white border border-slate-200 rounded-lg typo-input outline-none transition-colors">
                <option value="720p">720p</option>
                <option value="1080p">1080p</option>
                <option value="4k">4k</option>
              </select>
            </div>
          </div>

          <div class="flex-1 min-h-0 flex flex-col space-y-2">
            <div class="flex justify-between items-center">
              <label class="typo-label">{{ localeStore.t('video.prompt') }}</label>
            </div>
            <div class="flex-1 flex flex-col bg-slate-50/50 border-2 border-slate-100 hover:border-indigo-200 focus-within:bg-white focus-within:border-indigo-500 focus-within:ring-4 focus-within:ring-indigo-500/10 rounded-xl transition-all shadow-inner overflow-hidden group/box">
              <textarea
                v-model="prompt"
                maxlength="2000"
                class="w-full flex-1 p-4 bg-transparent border-none outline-none resize-none typo-prompt font-sans placeholder-slate-400 min-h-[120px]"
                :placeholder="localeStore.t('video.prompt_placeholder')"
              ></textarea>

              <div v-if="requiresImage && imagePreviewUrl" class="px-4 pb-2 flex gap-2 overflow-x-auto custom-scrollbar">
                <div class="relative w-6 h-6 flex-shrink-0 rounded-md overflow-hidden border border-slate-200 group/img">
                  <img :src="imagePreviewUrl" class="w-full h-full object-cover" />
                  <button @click="clearImage" class="absolute -top-1 -right-1 w-4 h-4 bg-white/90 border border-slate-200 text-slate-500 rounded-full flex items-center justify-center text-[9px] hover:text-red-500">×</button>
                </div>
              </div>

              <div class="px-3 py-2 border-t border-slate-100/50 flex items-center justify-between bg-white/50">
                <div class="flex items-center gap-2">
                  <n-upload v-if="requiresImage && !imagePreviewUrl" :custom-request="handleImageUpload" :max="1" accept="image/jpeg,image/png,image/webp" :show-file-list="false">
                    <button class="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 border border-indigo-200 rounded-lg transition-all shadow-sm hover:shadow flex items-center gap-2 active:scale-95">
                      <span class="text-xs font-bold">{{ localeStore.t('video.upload_image') }}</span>
                    </button>
                  </n-upload>
                  <div v-if="requiresImage && imagePreviewUrl" class="flex items-center gap-2 animate-fade-in">
                    <div class="h-4 w-px bg-slate-200"></div>
                    <span class="text-xs text-slate-400 font-medium">1 / 1</span>
                  </div>
                </div>

                <div class="text-xs text-slate-300 font-mono group-focus-within/box:text-slate-400 transition-colors">
                  {{ prompt.length }} / 2000
                </div>
              </div>
            </div>
          </div>

          <button
            @click="submitTask"
            :disabled="!isValid || loading"
            class="w-full py-3 bg-gradient-to-r from-blue-500 via-purple-500 to-orange-400 hover:from-blue-400 hover:to-orange-300 text-white rounded-xl typo-button shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40 hover:-translate-y-0.5 active:scale-95 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span v-if="loading" class="animate-spin mr-2">⟳</span>
            {{ loading ? localeStore.t('video.processing') : localeStore.t('video.generate') }}
          </button>
        </div>
      </div>

      <!-- Right: Preview -->
      <div class="lg:col-span-8 h-full min-h-0 animate-scale-in" style="animation-delay: 100ms;">
        <div class="h-full bg-white/60 backdrop-blur-xl rounded-[24px] border border-white/60 p-2 flex flex-col gap-4 shadow-xl shadow-slate-200/50 relative overflow-hidden">
          <div class="flex-1 bg-slate-50/50 rounded-[20px] shadow-inner border border-white/50 relative overflow-hidden group flex items-center justify-center">
            <div class="absolute inset-0 opacity-40 pointer-events-none" style="background-image: radial-gradient(#cbd5e1 1.5px, transparent 1.5px); background-size: 24px 24px;"></div>

            <div v-if="!resultVideoUrl" class="text-center relative z-10 animate-fade-in">
              <div v-if="status && status !== 'done'">
                <div class="relative mx-auto mb-6 w-20 h-20">
                  <div class="w-20 h-20 border-4 border-white rounded-full shadow-sm"></div>
                  <div class="w-20 h-20 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin absolute top-0 left-0"></div>
                  <div class="absolute inset-0 flex items-center justify-center">
                    <span class="icon-md animate-pulse">⏳</span>
                  </div>
                </div>
                <div class="typo-status-title mb-2">{{ statusMsg }}</div>
                <div v-if="taskId" class="typo-label-compact font-mono tracking-wider bg-white/50 px-2 py-1 rounded-full border border-slate-200 inline-block">ID: {{ taskId }}</div>
                <div v-if="status === 'failed'" class="text-red-500 typo-button-compact mt-4 bg-red-50 px-4 py-1.5 rounded-full border border-red-100 inline-block shadow-sm">{{ localeStore.t('video.status_failed') }}</div>
              </div>
              <div v-else>
                <div class="w-24 h-24 bg-white rounded-full flex items-center justify-center mx-auto mb-6 shadow-[0_8px_30px_rgba(0,0,0,0.04)] ring-4 ring-white/50">
                  <span class="icon-lg opacity-50 grayscale hover:grayscale-0 transition-all duration-500 cursor-default">🎬</span>
                </div>
                <h3 class="typo-empty-title mb-2">{{ localeStore.t('video.ready_title') }}</h3>
                <p class="typo-empty-desc">{{ localeStore.t('video.ready_desc') }}</p>
              </div>
            </div>

            <div v-if="resultVideoUrl" class="relative w-full h-full p-4 flex items-center justify-center animate-scale-in">
              <video :src="resultVideoUrl" controls class="max-w-full max-h-full rounded-2xl shadow-2xl ring-1 ring-black/5" autoplay loop></video>
            </div>
          </div>

          <div v-if="filteredHistory.length" class="shrink-0 bg-white/80 backdrop-blur-md rounded-[20px] border border-white/60 shadow-sm p-4 animate-slide-up">
            <div class="flex items-center justify-between mb-3 px-2">
              <h4 class="typo-label-compact tracking-[0.2em]">{{ localeStore.t('video.history') }}</h4>
              <span class="typo-label-compact text-indigo-500 bg-indigo-50 px-2 py-0.5 rounded-full">{{ filteredHistory.length }}</span>
            </div>
            <div class="flex gap-3 overflow-x-auto custom-scrollbar pb-2">
              <button
                v-for="item in filteredHistory"
                :key="item.id || item.task_id"
                @click="resultVideoUrl = item.video_url"
                class="flex-shrink-0 w-48 text-left p-3 rounded-2xl border transition-all duration-300 group relative overflow-hidden"
                :class="resultVideoUrl === item.video_url ? 'bg-indigo-600 border-indigo-600 shadow-lg shadow-indigo-500/30' : 'bg-white border-slate-100 hover:border-indigo-300 hover:shadow-md'">
                <div class="flex items-center justify-between mb-2">
                  <span class="typo-label-compact" :class="resultVideoUrl === item.video_url ? 'text-indigo-200' : 'text-slate-400'">{{ formatTime(item.created_at) }}</span>
                  <span class="typo-caption-compact" :class="resultVideoUrl === item.video_url ? 'text-white' : 'text-slate-400'">🎬</span>
                </div>
                <p class="typo-button-compact line-clamp-2 mb-2 leading-relaxed" :class="resultVideoUrl === item.video_url ? 'text-white' : 'text-slate-700'">{{ item.prompt || '—' }}</p>
                <div class="typo-label-compact" :class="resultVideoUrl === item.video_url ? 'text-indigo-200' : 'text-slate-400'">
                  {{ Math.round(item.duration || 0) }}s
                </div>
              </button>
            </div>
          </div>

          <div v-if="resultVideoUrl" class="h-20 shrink-0 bg-white/80 backdrop-blur-md rounded-[20px] border border-white/60 shadow-lg px-8 flex items-center justify-between animate-slide-up">
            <div class="flex items-center gap-4">
              <div class="w-12 h-12 rounded-full bg-green-50 text-green-500 flex items-center justify-center border border-green-100 shadow-sm animate-pulse">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" /></svg>
              </div>
              <div class="flex flex-col">
                <span class="typo-body font-black text-slate-800">{{ localeStore.t('video.render_complete') }}</span>
                <span class="typo-label-compact text-slate-500 tracking-wide">Ready for download</span>
              </div>
            </div>
            <a :href="resultVideoUrl" download class="py-3 px-6 bg-slate-900 hover:bg-black text-white typo-button-compact rounded-xl shadow-lg hover:shadow-xl transition-all flex items-center gap-2 transform hover:-translate-y-0.5">
              <span>📥</span> {{ localeStore.t('video.download') }}
            </a>
          </div>
        </div>
      </div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { NSelect, NUpload, useMessage } from 'naive-ui'
import api from '../services/api'
import { fetchModelCatalog } from '../services/modelCatalog'
import DigitalHumanPanel from './DigitalHumanPanel.vue'
import { useLocaleStore } from '../stores/locale'
import { useAuthStore } from '../stores/auth'
import { selectUserPoolWithFallback } from '../utils/userKeyPools'
import { loadLocalHistory, prependLocalHistory } from '../utils/localHistory'

const localeStore = useLocaleStore()
const authStore = useAuthStore()
const message = useMessage()
const VIDEO_HISTORY_KEY = 'nbs_history_video'
const VIDEO_SEED_KEY = 'nbs_seed_video_from_image'

const modeOptions = [
  { label: localeStore.t('video.text_mode'), value: 'text' },
  { label: localeStore.t('video.image_mode'), value: 'image' },
  { label: localeStore.t('video.digital_human_mode'), value: 'digital_human' }
]

const activeMode = ref('text')
const prompt = ref('')
const settings = ref({
  model: '',
  aspectRatio: '16:9',
  resolution: '720p',
  durationSeconds: 8
})
const imageUrl = ref('')
const imagePreviewUrl = ref('')
const loading = ref(false)
const status = ref('')
const taskId = ref('')
const resultVideoUrl = ref('')
const pollTimer = ref(null)
const videoHistory = ref([])
const modelCatalog = ref([])
const pendingVideoMeta = ref(null)

const loadModelCatalog = async () => {
  try {
    modelCatalog.value = await fetchModelCatalog()
  } catch (e) {
    modelCatalog.value = []
  }
}

const uploadAction = import.meta.env.VITE_PUBLIC_UPLOAD_URL || '/api/upload'

const formatCatalogLabel = (item, withCost = false) => {
  const name = item?.label || item?.model || ''
  const costValue = Number.isFinite(Number(item?.cost)) ? Number(item.cost) : null
  if (withCost && costValue !== null) return `${name}（${costValue}积分）`
  return name
}
const buildCatalogOptions = (service, withCost = false) => {
  const items = modelCatalog.value.filter((m) => m?.service === service)
  return items.map((item) => ({
    label: formatCatalogLabel(item, withCost),
    value: item.model,
    cost: Number.isFinite(Number(item?.cost)) ? Number(item.cost) : null
  }))
}

const videoModelOptionsAll = computed(() => buildCatalogOptions('video', true))
const isI2vModelName = (value) => {
  const text = String(value || '').trim().toLowerCase()
  return text.includes('i2v') || text.includes('wanx') || text.includes('wan2.')
}
const defaultVideoModel = computed(() => {
  const options = videoModelOptionsAll.value || []
  const nonSora = options.find((option) => !String(option.value).toLowerCase().includes('sora'))
  return nonSora?.value || ''
})
const videoModelOptions = computed(() => {
  const options = videoModelOptionsAll.value || []
  if (activeMode.value === 'image') return options
  return options.filter((option) => !String(option.value).toLowerCase().includes('sora'))
})
const emptyModelOption = { label: '请先配置模型', value: '', disabled: true }
const videoModelSelectOptions = computed(() => (videoModelOptions.value.length ? videoModelOptions.value : [emptyModelOption]))

const getVideoCreditCost = (model) => {
  if (!model) return 0
  const match = modelCatalog.value.find((item) => item?.service === 'video' && item?.model === model)
  if (match && Number.isFinite(Number(match.cost))) return Number(match.cost)
  const text = String(model || '').trim().toLowerCase()
  if (text.includes('veo')) return 10
  if (text.includes('sora')) return 10
  if (text.includes('doubao') || text.includes('seedance')) return 5
  return 5
}

const formatVideoCostHint = (cost) => {
  const template = localeStore.t('video.cost_hint')
  if (template === 'video.cost_hint') return `本次生成预计消耗 ${cost} 积分`
  return template.replace('{cost}', cost)
}

const videoCostHint = computed(() => (settings.value.model ? formatVideoCostHint(getVideoCreditCost(settings.value.model)) : ''))
const isSoraModel = computed(() => String(settings.value.model || '').trim().toLowerCase().includes('sora'))
const isBailianI2vModel = computed(() => {
  return isI2vModelName(settings.value.model)
})
const requiresImage = computed(() => activeMode.value === 'image' || isSoraModel.value || isBailianI2vModel.value)

watch(
  () => [activeMode.value, settings.value.model],
  ([mode, model]) => {
    if (mode !== 'image' && String(model || '').toLowerCase().includes('sora')) {
      settings.value.model = defaultVideoModel.value
    }
    if (mode === 'text' && isI2vModelName(model)) {
      activeMode.value = 'image'
    }
  }
)

watch(
  videoModelOptionsAll,
  (options) => {
    const list = options || []
    if (!list.length) {
      settings.value.model = ''
      return
    }
    if (!list.some((o) => o.value === settings.value.model)) settings.value.model = list[0].value
  },
  { immediate: true }
)

const isValid = computed(() => {
  if (activeMode.value === 'digital_human') return false
  if (!settings.value.model) return false
  if (!prompt.value.trim()) return false
  if (requiresImage.value && !imageUrl.value) return false
  return true
})

const statusMsg = computed(() => {
  if (status.value === 'processing' || status.value === 'running') return localeStore.t('video.status_generating')
  if (status.value === 'failed') return localeStore.t('video.status_failed')
  return localeStore.t('video.status_waiting')
})

const filteredHistory = computed(() => {
  if (activeMode.value === 'digital_human') return []
  const items = Array.isArray(videoHistory.value) ? videoHistory.value : []
  return items.filter((item) => (item.mode || 'text') === activeMode.value)
})

const setMode = (mode) => {
  if (mode === 'text' && isI2vModelName(settings.value.model)) {
    const fallback = (videoModelOptionsAll.value || []).find((option) => !isI2vModelName(option.value))
    if (fallback?.value) {
      settings.value.model = fallback.value
    } else {
      message.warning('当前仅配置图生视频模型，请先添加文生视频模型')
      activeMode.value = 'image'
      resetState()
      fetchVideoHistory()
      return
    }
  }
  activeMode.value = mode
  resetState()
  if (mode !== 'digital_human') fetchVideoHistory()
}

const resetState = () => {
  prompt.value = ''
  imageUrl.value = ''
  imagePreviewUrl.value = ''
  loading.value = false
  status.value = ''
  taskId.value = ''
  resultVideoUrl.value = ''
  stopPolling()
}

const applySeededImage = () => {
  const raw = localStorage.getItem(VIDEO_SEED_KEY)
  if (!raw) return
  try {
    const payload = JSON.parse(raw)
    localStorage.removeItem(VIDEO_SEED_KEY)
    if (!payload?.image_url) return
    setMode('image')
    imageUrl.value = payload.image_url
    imagePreviewUrl.value = payload.image_url
    if (payload.prompt && !prompt.value) prompt.value = payload.prompt
    if (payload.aspect_ratio === '16:9' || payload.aspect_ratio === '9:16') {
      settings.value.aspectRatio = payload.aspect_ratio
    }
  } catch (e) {
    localStorage.removeItem(VIDEO_SEED_KEY)
  }
}

const applyUserPoolHeaders = (headers, service, model) => {
  const pool = selectUserPoolWithFallback(service, model)
  if (!pool?.key) return headers
  if (service === 'audio') {
    headers['x-tts-key'] = pool.key
    return headers
  }
  if (service === 'video') {
    headers['x-video-key'] = pool.key
    if (pool.base_url) headers['x-video-base-url'] = pool.base_url
    return headers
  }
  headers['x-model-key'] = pool.key
  if (pool.base_url) headers['x-model-base-url'] = pool.base_url
  return headers
}

const buildVideoHeaders = (model) => {
  const headers = {}
  if (authStore.token) headers.Authorization = `Bearer ${authStore.token}`
  return applyUserPoolHeaders(headers, 'video', model)
}

const handleImageUpload = async ({ file, onProgress }) => {
  const form = new FormData()
  form.append('file', file.file)
  try {
    const tryUpload = async (action) => {
      const res = await api.post(action, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (evt) => {
          if (!onProgress || !evt.total) return
          const percent = Math.round((evt.loaded / evt.total) * 100)
          onProgress({ percent })
        }
      })
      if (res.data?.success) {
        imageUrl.value = res.data.url
        imagePreviewUrl.value = res.data.url
        message.success(localeStore.t('video.upload_success'))
      } else {
        throw new Error(res.data?.detail || 'Upload failed')
      }
    }

    try {
      await tryUpload(uploadAction)
    } catch (err) {
      if (uploadAction !== '/api/upload') {
        message.warning('OSS 上传失败，已自动切换本地存储')
        await tryUpload('/api/upload')
      } else {
        throw err
      }
    }
  } catch (e) {
    message.error(e?.response?.data?.detail || e?.message || 'Upload failed')
  }
}

const clearImage = () => {
  imageUrl.value = ''
  imagePreviewUrl.value = ''
}

const submitTask = async () => {
  if (!isValid.value || loading.value) return
  if (!settings.value.model) {
    message.warning('请先在模型配置中添加视频模型')
    return
  }
  loading.value = true
  status.value = 'processing'
  resultVideoUrl.value = ''
  pendingVideoMeta.value = {
    id: `${Date.now()}`,
    prompt: prompt.value.trim(),
    mode: activeMode.value,
    durationSeconds: settings.value.durationSeconds,
    model: settings.value.model
  }
  try {
    const payload = {
      mode: activeMode.value,
      prompt: prompt.value.trim(),
      model: settings.value.model,
      aspect_ratio: settings.value.aspectRatio,
      resolution: settings.value.resolution,
      duration_seconds: settings.value.durationSeconds,
      image_url: requiresImage.value ? imageUrl.value : null
    }
    const res = await api.post('/api/video/generate', payload, { headers: buildVideoHeaders(settings.value.model) })
    const task = res.data?.data || {}
    taskId.value = task.task_id || ''
    if (!taskId.value) throw new Error('任务创建失败')
    startPolling()
  } catch (e) {
    status.value = 'failed'
    message.error(e?.response?.data?.detail || e?.message || '生成失败')
  } finally {
    loading.value = false
  }
}

const startPolling = () => {
  stopPolling()
  pollTimer.value = setInterval(async () => {
    if (!taskId.value) return
    try {
      const res = await api.get('/api/video/status', {
        params: { task_id: taskId.value },
        headers: buildVideoHeaders(settings.value.model)
      })
      const data = res.data?.data || {}
      if (data.status) status.value = data.status
      if (data.video_url) resultVideoUrl.value = data.video_url
      if (status.value === 'done' && data.video_url && !authStore.token) {
        persistLocalVideo(data.video_url)
      }
      if (status.value === 'done' || status.value === 'failed' || status.value === 'expired') {
        stopPolling()
        fetchVideoHistory()
      }
    } catch (e) {
      stopPolling()
      status.value = 'failed'
    }
  }, 10000)
}

const stopPolling = () => {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

const fetchVideoHistory = async () => {
  if (!authStore.token) {
    videoHistory.value = loadLocalHistory(VIDEO_HISTORY_KEY)
    return
  }
  try {
    const res = await api.get('/api/video/history', { headers: buildVideoHeaders(settings.value.model) })
    videoHistory.value = Array.isArray(res.data) ? res.data : []
  } catch (e) {
    const status = e?.response?.status
    if (status === 401) message.warning('请先登录后查看历史记录')
    videoHistory.value = []
  }
}

const persistLocalVideo = (videoUrl) => {
  if (!videoUrl) return
  const meta = pendingVideoMeta.value || {}
  const entry = {
    id: meta.id || taskId.value || `${Date.now()}`,
    task_id: taskId.value || '',
    video_url: videoUrl,
    prompt: meta.prompt || prompt.value.trim(),
    duration: Number(meta.durationSeconds || settings.value.durationSeconds || 0),
    model: meta.model || settings.value.model,
    mode: meta.mode || activeMode.value,
    created_at: Math.floor(Date.now() / 1000)
  }
  videoHistory.value = prependLocalHistory(VIDEO_HISTORY_KEY, entry, {
    idResolver: (item) => item?.id || item?.task_id || item?.video_url
  })
}

const formatTime = (ts) => {
  if (!ts) return ''
  const date = new Date(ts * 1000)
  return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`
}

onMounted(() => {
  loadModelCatalog()
  applySeededImage()
  if (activeMode.value !== 'digital_human') fetchVideoHistory()
})

onUnmounted(() => {
  stopPolling()
})
</script>
