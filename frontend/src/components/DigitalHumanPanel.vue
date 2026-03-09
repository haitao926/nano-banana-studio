<template>
  <div class="h-[calc(100vh-140px)] grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch overflow-hidden">
    <!-- Left: Controls -->
    <div class="lg:col-span-4 flex flex-col h-full min-h-0 animate-slide-up">
       <div class="bg-white/80 backdrop-blur-xl border border-white/60 rounded-[24px] p-4 shadow-sm flex flex-col h-full overflow-y-auto custom-scrollbar hover:shadow-md transition-shadow duration-300">
          <div class="flex items-center gap-2 border-b border-slate-100 pb-3 mb-3 shrink-0">
             <h3 class="typo-section-title flex items-center gap-2">
                <span class="w-2 h-2 rounded-full bg-indigo-500"></span> {{ localeStore.t('dh.title') }}
             </h3>
             <span class="typo-badge text-indigo-500 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">Beta</span>
          </div>

          <div v-if="$slots['mode-selector']" class="mb-4">
             <slot name="mode-selector" />
          </div>

          <!-- Config (Match Other Pages: Above Prompt) -->
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-2 shrink-0 mb-2">
             <div class="space-y-1.5">
                <label class="typo-label">{{ localeStore.t('video.model') }}</label>
                <div class="relative group">
                  <select v-model="model" :disabled="!digitalHumanModelOptions.length" class="w-full pl-3 pr-8 py-2 bg-white border border-slate-200 hover:border-indigo-300 rounded-lg typo-input outline-none appearance-none cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                    <option v-for="option in digitalHumanModelSelectOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                  </select>
                  <div class="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none typo-caption-compact text-slate-400">▼</div>
                </div>
             </div>
             <div class="space-y-1.5">
                <label class="typo-label">{{ localeStore.t('dh.resolution') }}</label>
                <div class="relative group">
                  <select v-model.number="resolution" class="w-full pl-3 pr-8 py-2 bg-white border border-slate-200 hover:border-indigo-300 rounded-lg typo-input outline-none appearance-none cursor-pointer transition-colors">
                    <option :value="480">480P</option>
                  </select>
                  <div class="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none typo-caption-compact text-slate-400">▼</div>
                </div>
             </div>
             <div class="space-y-1.5">
                <label class="typo-label">{{ localeStore.t('dh.seed') }}</label>
                <input v-model="seedInput" type="number" placeholder="Seed" class="w-full px-3 py-2 bg-white border border-slate-200 hover:border-indigo-300 rounded-lg typo-input-mono outline-none transition-colors" />
             </div>
          </div>
          <label class="flex items-center gap-2 cursor-pointer group px-1 mb-3 shrink-0">
             <input type="checkbox" v-model="fastMode" class="rounded text-indigo-600 focus:ring-indigo-500 border-slate-300 w-4 h-4 transition-all" />
             <span class="typo-label-compact text-slate-500 group-hover:text-indigo-600 transition-colors">{{ localeStore.t('dh.turbo_mode') }}</span>
          </label>

          <!-- Prompt Stage (Flexible Height) -->
          <div class="flex-1 min-h-0 flex flex-col space-y-1.5">
            <div class="flex justify-between items-center shrink-0 px-1">
              <label class="typo-label">{{ localeStore.t('dh.motion_prompt') }}</label>
            </div>
            <div class="flex-1 flex flex-col bg-slate-50/50 border-2 border-slate-100 hover:border-indigo-200 focus-within:bg-white focus-within:border-indigo-500 focus-within:ring-4 focus-within:ring-indigo-500/10 rounded-xl transition-all shadow-inner overflow-hidden group/box">
              <textarea
                v-model="prompt"
                :maxlength="MAX_PROMPT_LENGTH"
                :placeholder="localeStore.t('dh.motion_placeholder')"
                class="w-full flex-1 p-3 bg-transparent border-none outline-none resize-none typo-prompt font-sans placeholder-slate-400 min-h-[88px]"
              ></textarea>

              <div v-if="imageDisplayUrl || audioDisplayUrl" class="px-4 pb-2 flex flex-wrap gap-2 overflow-x-auto custom-scrollbar">
                <div v-if="imageDisplayUrl" class="relative w-12 h-12 flex-shrink-0 rounded-lg overflow-hidden border border-slate-200 bg-white/70">
                  <img :src="imageDisplayUrl" class="w-full h-full object-cover" />
                  <button @click="clearImage" class="absolute -top-1 -right-1 w-5 h-5 bg-white/90 border border-slate-200 text-slate-500 rounded-full flex items-center justify-center text-xs hover:text-red-500">×</button>
                  <div class="absolute bottom-1 left-1 bg-black/50 backdrop-blur px-1.5 py-0.5 rounded text-[10px] text-white">{{ localeStore.t('dh.avatar_image') }}</div>
                </div>
                <div
                  v-if="audioDisplayUrl"
                  class="relative w-12 h-12 flex-shrink-0 rounded-lg overflow-hidden border border-slate-200 bg-white/70 flex flex-col items-center justify-center gap-1 group/audio"
                  :title="audioInfo || localeStore.t('dh.driver_audio')"
                >
                  <span class="text-base text-slate-500">🎵</span>
                  <span class="text-[10px] text-slate-400">{{ localeStore.t('dh.driver_audio') }}</span>
                  <button @click="clearAudio" class="absolute -top-1 -right-1 w-5 h-5 bg-white/90 border border-slate-200 text-slate-500 rounded-full flex items-center justify-center text-xs hover:text-red-500">×</button>
                  <div class="absolute left-0 top-[60px] z-20 hidden group-hover/audio:flex flex-col gap-1 rounded-lg border border-slate-200 bg-white/90 p-2 shadow-lg">
                    <div class="text-[10px] text-slate-400">{{ audioInfo || localeStore.t('dh.driver_audio') }}</div>
                    <audio :src="audioDisplayUrl" controls class="w-40 h-8 opacity-90" />
                  </div>
                </div>
              </div>

              <div class="px-3 py-2 border-t border-slate-100/50 flex items-center justify-between bg-white/50">
                <div class="flex items-center gap-2">
                  <n-upload v-if="!imageDisplayUrl" :custom-request="handleImageCustomUpload" :max="1" accept="image/jpeg,image/png,image/bmp,image/webp" :show-file-list="false" @error="handleUploadError">
                    <button class="px-2.5 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 border border-indigo-200 rounded-lg transition-all shadow-sm hover:shadow flex items-center gap-2 active:scale-95">
                      <span class="text-xs font-bold">{{ localeStore.t('dh.avatar_image') }}</span>
                    </button>
                  </n-upload>
                  <n-upload v-if="!audioDisplayUrl" :custom-request="handleAudioCustomUpload" :max="1" accept="audio/mpeg,audio/wav,.mp3,.wav" :show-file-list="false" @error="handleUploadError">
                    <button class="px-2.5 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 border border-indigo-200 rounded-lg transition-all shadow-sm hover:shadow flex items-center gap-2 active:scale-95">
                      <span class="text-xs font-bold">{{ localeStore.t('dh.driver_audio') }}</span>
                    </button>
                  </n-upload>
                  <div v-if="imageDisplayUrl || audioDisplayUrl" class="flex items-center gap-2 animate-fade-in">
                    <div class="h-4 w-px bg-slate-200"></div>
                    <span class="text-xs text-slate-400 font-medium">{{ (imageDisplayUrl ? 1 : 0) + (audioDisplayUrl ? 1 : 0) }} / 2</span>
                  </div>
                </div>

                <div class="text-xs text-slate-300 font-mono group-focus-within/box:text-slate-400 transition-colors">
                  {{ promptLength }} / {{ MAX_PROMPT_LENGTH }}
                </div>
              </div>
            </div>
          </div>

          <button
             @click="submitTask"
             :disabled="!isValid || loading || !model"
             class="w-full mt-3 py-2.5 bg-gradient-to-r from-blue-500 via-purple-500 to-orange-400 hover:from-blue-400 hover:to-orange-300 text-white rounded-xl typo-button shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40 hover:-translate-y-0.5 active:scale-95 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed group overflow-hidden relative shrink-0"
           >
             <span class="relative z-10 flex items-center justify-center gap-2">
                 <span v-if="loading" class="animate-spin">⟳</span>
                 {{ loading ? localeStore.t('dh.processing') : localeStore.t('dh.generate_btn') }}
             </span>
          </button>
       </div>
    </div>

    <!-- Right: Preview -->
    <div class="lg:col-span-8 h-full min-h-0 animate-scale-in" style="animation-delay: 100ms;">
      <div class="h-full bg-white/60 backdrop-blur-xl rounded-[24px] border border-white/60 p-2 flex flex-col gap-3 shadow-xl shadow-slate-200/50 relative overflow-hidden">
        
        <!-- Screen Area -->
        <div class="flex-1 bg-slate-50/50 rounded-[20px] shadow-inner border border-white/50 relative overflow-hidden group flex items-center justify-center">
            <!-- Grid Pattern -->
            <div class="absolute inset-0 opacity-40 pointer-events-none" style="background-image: radial-gradient(#cbd5e1 1.5px, transparent 1.5px); background-size: 24px 24px;"></div>

            <!-- Empty State -->
            <div v-if="!resultVideoUrl" class="text-center relative z-10 animate-fade-in">
                <div v-if="status && status !== 'done'">
                   <!-- Processing Status -->
                   <div class="relative mx-auto mb-6 w-20 h-20">
                      <div class="w-20 h-20 border-4 border-white rounded-full shadow-sm"></div>
                      <div class="w-20 h-20 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin absolute top-0 left-0"></div>
                      <div class="absolute inset-0 flex items-center justify-center">
                          <span class="icon-md animate-pulse">⏳</span>
                      </div>
                   </div>
                   <div class="typo-status-title mb-2">{{ statusMsg }}</div>
                   <div v-if="taskId" class="typo-label-compact font-mono tracking-wider bg-white/50 px-2 py-1 rounded-full border border-slate-200 inline-block">ID: {{ taskId }}</div>
                   <div v-if="status === 'failed'" class="text-red-500 typo-button-compact mt-4 bg-red-50 px-4 py-1.5 rounded-full border border-red-100 inline-block shadow-sm">{{ localeStore.t('dh.status_failed') }}</div>
                </div>
                <div v-else>
                   <!-- Initial State -->
                   <div class="w-24 h-24 bg-white rounded-full flex items-center justify-center mx-auto mb-6 shadow-[0_8px_30px_rgba(0,0,0,0.04)] ring-4 ring-white/50">
                      <span class="icon-lg opacity-50 grayscale hover:grayscale-0 transition-all duration-500 cursor-default">🎬</span>
                   </div>
                   <h3 class="typo-empty-title mb-2">{{ localeStore.t('dh.ready_title') }}</h3>
                   <p class="typo-empty-desc">{{ localeStore.t('dh.ready_desc') }}</p>
                </div>
            </div>

            <!-- Result Video -->
            <div v-if="resultVideoUrl" class="relative w-full h-full p-4 flex items-center justify-center animate-scale-in">
              <video :src="resultVideoUrl" controls class="max-w-full max-h-full rounded-2xl shadow-2xl ring-1 ring-black/5" autoplay loop></video>
            </div>
        </div>

        <!-- History Rail -->
        <div v-if="videoHistory.length" class="shrink-0 bg-white/80 backdrop-blur-md rounded-[20px] border border-white/60 shadow-sm p-3 animate-slide-up">
            <div class="flex items-center justify-between mb-2 px-1">
                <h4 class="typo-label-compact tracking-[0.2em]">HISTORY</h4>
                <span class="typo-label-compact text-indigo-500 bg-indigo-50 px-2 py-0.5 rounded-full">{{ videoHistory.length }}</span>
            </div>
            <div class="flex gap-3 overflow-x-auto custom-scrollbar pb-2">
                <button
                    v-for="item in videoHistory"
                    :key="item.id || item.task_id"
                    @click="resultVideoUrl = item.video_url"
                    class="flex-shrink-0 w-40 text-left p-2.5 rounded-2xl border transition-all duration-300 group relative overflow-hidden"
                    :class="resultVideoUrl === item.video_url ? 'bg-indigo-600 border-indigo-600 shadow-lg shadow-indigo-500/30' : 'bg-white border-slate-100 hover:border-indigo-300 hover:shadow-md'">
                    <div class="flex items-center justify-between mb-2">
                        <span class="typo-label-compact" :class="resultVideoUrl === item.video_url ? 'text-indigo-200' : 'text-slate-400'">{{ formatTime(item.created_at) }}</span>
                        <span class="typo-caption-compact" :class="resultVideoUrl === item.video_url ? 'text-white' : 'text-slate-400'">🎬</span>
                    </div>
                        <p class="typo-button-compact line-clamp-2 mb-1.5 leading-relaxed" :class="resultVideoUrl === item.video_url ? 'text-white' : 'text-slate-700'">{{ item.prompt || '—' }}</p>
                    <div class="typo-label-compact" :class="resultVideoUrl === item.video_url ? 'text-indigo-200' : 'text-slate-400'">
                        {{ Math.round(item.duration || 0) }}s
                    </div>
                </button>
            </div>
        </div>

        <!-- Action Dock (Bottom) -->
        <div v-if="resultVideoUrl" class="h-16 shrink-0 bg-white/80 backdrop-blur-md rounded-[20px] border border-white/60 shadow-lg px-6 flex items-center justify-between animate-slide-up">
            <div class="flex items-center gap-4">
                <div class="w-12 h-12 rounded-full bg-green-50 text-green-500 flex items-center justify-center border border-green-100 shadow-sm animate-pulse">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" /></svg>
                </div>
                <div class="flex flex-col">
                    <span class="typo-body font-black text-slate-800">{{ localeStore.t('dh.render_complete') }}</span>
                    <span class="typo-label-compact text-slate-500 tracking-wide">Ready for download</span>
                </div>
            </div>
            <a :href="resultVideoUrl" download class="py-3 px-6 bg-slate-900 hover:bg-black text-white typo-button-compact rounded-xl shadow-lg hover:shadow-xl transition-all flex items-center gap-2 transform hover:-translate-y-0.5">
                <span>📥</span> {{ localeStore.t('dh.download_video') }}
            </a>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { NUpload, useMessage } from 'naive-ui'
import api from '../services/api'
import { fetchModelCatalog } from '../services/modelCatalog'
import { useLocaleStore } from '../stores/locale'
import { useAuthStore } from '../stores/auth'
import { selectUserPoolWithFallback } from '../utils/userKeyPools'
import { loadLocalHistory, prependLocalHistory } from '../utils/localHistory'

const localeStore = useLocaleStore()
const message = useMessage()
const authStore = useAuthStore()
const uploadAction = import.meta.env.VITE_PUBLIC_UPLOAD_URL || '/api/upload'
const DIGITAL_HUMAN_HISTORY_KEY = 'nbs_history_digital_human'

const MIN_IMAGE_DIM = 400
const MAX_IMAGE_DIM = 7000
const MAX_IMAGE_MB = 10
const MAX_AUDIO_MB = 15
const MAX_AUDIO_SECONDS = 20
const RECOMMENDED_AUDIO_SECONDS = 15
const MAX_PROMPT_LENGTH = 300

const modelCatalog = ref([])

const loadModelCatalog = async () => {
    try {
        modelCatalog.value = await fetchModelCatalog()
    } catch (e) {
        modelCatalog.value = []
    }
}

const formatCatalogLabel = (item, withCost = false) => {
    const name = item?.label || item?.model || ''
    const costValue = Number.isFinite(Number(item?.cost)) ? Number(item.cost) : null
    if (withCost && costValue !== null) return `${name}（${costValue}积分）`
    return name
}

const digitalHumanModelOptions = computed(() => {
    const items = modelCatalog.value.filter((m) => m?.service === 'digital_human')
    return items.map((item) => ({
        label: formatCatalogLabel(item, true),
        value: item.model
    }))
})

const emptyModelOption = { label: '请先配置模型', value: '', disabled: true }
const digitalHumanModelSelectOptions = computed(() => (
    digitalHumanModelOptions.value.length ? digitalHumanModelOptions.value : [emptyModelOption]
))

const imageUrl = ref('')
const audioUrl = ref('')
const imagePreviewUrl = ref('')
const audioPreviewUrl = ref('')
const prompt = ref('')
const model = ref('')
const resolution = ref(480)
const style = 'speech'
const seedInput = ref('')
const fastMode = ref(false)
const loading = ref(false)
const taskId = ref('')
const status = ref('') // processing, done, failed
const resultVideoUrl = ref('')
const pollTimer = ref(null)
const videoHistory = ref([])
const pendingMeta = ref(null)

const imageMeta = ref({ size: 0, width: 0, height: 0, type: '' })
const audioMeta = ref({ size: 0, duration: 0, type: '' })

const promptLength = computed(() => prompt.value.length)
const promptError = computed(() => promptLength.value > MAX_PROMPT_LENGTH ? `Max ${MAX_PROMPT_LENGTH} characters` : '')

const imageError = computed(() => {
    if (!imageMeta.value.size) return ''
    if (imageMeta.value.type && !['image/jpeg', 'image/jpg', 'image/png', 'image/bmp', 'image/webp'].includes(imageMeta.value.type)) {
        return 'Image must be jpg/png/bmp/webp'
    }
    if (imageMeta.value.size > MAX_IMAGE_MB * 1024 * 1024) return `Image > ${MAX_IMAGE_MB}MB`
    if (imageMeta.value.width && imageMeta.value.height) {
        if (imageMeta.value.width < MIN_IMAGE_DIM || imageMeta.value.height < MIN_IMAGE_DIM) {
            return `Min dimension ${MIN_IMAGE_DIM}px`
        }
        if (imageMeta.value.width > MAX_IMAGE_DIM || imageMeta.value.height > MAX_IMAGE_DIM) {
            return `Max dimension ${MAX_IMAGE_DIM}px`
        }
    }
    return ''
})

const audioError = computed(() => {
    if (!audioMeta.value.size && !audioMeta.value.duration) return ''
    if (audioMeta.value.size > MAX_AUDIO_MB * 1024 * 1024) return `Audio > ${MAX_AUDIO_MB}MB`
    if (audioMeta.value.duration && audioMeta.value.duration > MAX_AUDIO_SECONDS) return `Audio > ${MAX_AUDIO_SECONDS}s`
    if (audioMeta.value.type && !['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav'].includes(audioMeta.value.type)) {
        return 'Audio must be mp3 or wav'
    }
    return ''
})

const audioWarning = computed(() => {
    if (!audioMeta.value.duration) return ''
    if (audioMeta.value.duration > RECOMMENDED_AUDIO_SECONDS) return 'Recommended < 15s for stability'
    return ''
})

const imageInfo = computed(() => {
    const parts = []
    if (imageMeta.value.size) parts.push(formatBytes(imageMeta.value.size))
    if (imageMeta.value.width && imageMeta.value.height) parts.push(`${imageMeta.value.width}×${imageMeta.value.height}`)
    return parts.join(' · ')
})

const audioInfo = computed(() => {
    const parts = []
    if (audioMeta.value.duration) parts.push(formatDuration(audioMeta.value.duration))
    if (audioMeta.value.size) parts.push(formatBytes(audioMeta.value.size))
    return parts.join(' · ')
})

const imageDisplayUrl = computed(() => imagePreviewUrl.value || imageUrl.value)
const audioDisplayUrl = computed(() => audioPreviewUrl.value || audioUrl.value)

const isValid = computed(() => imageUrl.value && audioUrl.value && !imageError.value && !audioError.value && !promptError.value)
const statusMsg = computed(() => {
    if (status.value === 'processing' || status.value === 'running') return localeStore.t('dh.status_generating')
    if (status.value === 'in_queue') return 'In Queue...'
    if (status.value === 'failed') return localeStore.t('dh.status_failed')
    return 'Waiting...'
})

watch(
    digitalHumanModelOptions,
    (options) => {
        const list = options || []
        if (!list.length) {
            model.value = ''
            return
        }
        if (!list.some((o) => o.value === model.value)) {
            model.value = list[0].value
        }
    },
    { immediate: true }
)

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

const buildVideoHeaders = (modelHint) => {
    const headers = {}
    if (authStore.token) headers.Authorization = `Bearer ${authStore.token}`
    return applyUserPoolHeaders(headers, 'video', modelHint)
}

const handleUploadError = ({ event, message: errorMessage }) => {
    let detail = ''
    try {
        const res = JSON.parse(event?.target?.response || '{}')
        detail = res.detail || res.message || res.error || ''
    } catch (e) {}
    message.error(detail || errorMessage || 'Upload Failed')
}

const revokeObjectUrl = (url) => {
    if (url && url.startsWith('blob:')) {
        URL.revokeObjectURL(url)
    }
}

const clearImage = () => {
    revokeObjectUrl(imagePreviewUrl.value)
    imagePreviewUrl.value = ''
    imageUrl.value = ''
    imageMeta.value = { size: 0, width: 0, height: 0, type: '' }
    resetTaskState()
}

const clearAudio = () => {
    revokeObjectUrl(audioPreviewUrl.value)
    audioPreviewUrl.value = ''
    audioUrl.value = ''
    audioMeta.value = { size: 0, duration: 0, type: '' }
    resetTaskState()
}

const uploadFileToPublic = async (rawFile, onProgress) => {
    const form = new FormData()
    form.append('file', rawFile)
    const tryUpload = async (action) => {
        const res = await api.post(action, form, {
            headers: { 'Content-Type': 'multipart/form-data' },
            onUploadProgress: (evt) => {
                if (!onProgress || !evt.total) return
                const percent = Math.round((evt.loaded / evt.total) * 100)
                onProgress({ percent })
            }
        })
        if (res?.data?.success && res?.data?.url) {
            return res.data.url
        }
        throw new Error(res?.data?.detail || 'Upload Failed')
    }

    try {
        return await tryUpload(uploadAction)
    } catch (err) {
        if (uploadAction !== '/api/upload') {
            message.warning('OSS 上传失败，已自动切换本地存储')
            return await tryUpload('/api/upload')
        }
        throw err
    }
}

const handleImageCustomUpload = async ({ file, onFinish, onError, onProgress }) => {
    const rawFile = file?.file || file
    if (!rawFile) {
        if (onError) onError()
        handleUploadError({ message: 'Upload Failed' })
        return
    }
    revokeObjectUrl(imagePreviewUrl.value)
    imagePreviewUrl.value = URL.createObjectURL(rawFile)
    imageUrl.value = ''
    updateImageMeta(rawFile)
    resetTaskState()

    try {
        const url = await uploadFileToPublic(rawFile, onProgress)
        imageUrl.value = url
        revokeObjectUrl(imagePreviewUrl.value)
        imagePreviewUrl.value = ''
        if (onFinish) onFinish()
    } catch (err) {
        if (onError) onError(err)
        handleUploadError({ message: err?.message || 'Upload Failed' })
    }
}

const handleAudioCustomUpload = async ({ file, onFinish, onError, onProgress }) => {
    const rawFile = file?.file || file
    if (!rawFile) {
        if (onError) onError()
        handleUploadError({ message: 'Upload Failed' })
        return
    }
    revokeObjectUrl(audioPreviewUrl.value)
    audioPreviewUrl.value = URL.createObjectURL(rawFile)
    audioUrl.value = ''
    updateAudioMeta(rawFile)
    resetTaskState()

    try {
        const url = await uploadFileToPublic(rawFile, onProgress)
        audioUrl.value = url
        revokeObjectUrl(audioPreviewUrl.value)
        audioPreviewUrl.value = ''
        if (onFinish) onFinish()
    } catch (err) {
        if (onError) onError(err)
        handleUploadError({ message: err?.message || 'Upload Failed' })
    }
}

const submitTask = async () => {
    if (!isValid.value) {
        message.warning('Please check limits')
        return
    }
    if (!model.value) {
        message.warning('请先在模型配置中添加数字人模型')
        return
    }

    loading.value = true
    status.value = 'processing'
    resultVideoUrl.value = ''
    taskId.value = ''
    pendingMeta.value = {
        id: `${Date.now()}`,
        prompt: prompt.value.trim(),
        model: model.value,
        duration: Math.round(audioMeta.value?.duration || 0)
    }

    if (pollTimer.value) clearInterval(pollTimer.value)

    try {
        const seedValue = seedInput.value === '' ? -1 : Number(seedInput.value)
        const payload = {
            image_url: imageUrl.value,
            audio_url: audioUrl.value,
            audio_duration: audioMeta.value?.duration || null,
            model: model.value,
            seed: Number.isFinite(seedValue) ? seedValue : -1,
            resolution: resolution.value,
            fast_mode: fastMode.value,
            style
        }
        const trimmedPrompt = prompt.value.trim()
        if (trimmedPrompt) payload.prompt = trimmedPrompt

        const res = await api.post('/api/digital_human/submit', payload, { headers: buildVideoHeaders(model.value) })
        const rawPayload = res.data?.raw || res.data
        const taskIdValue = res.data?.data?.task_id || extractValue(rawPayload, ['task_id', 'taskId', 'TaskID', 'TaskId'])

        if (taskIdValue) {
            taskId.value = taskIdValue
            message.success('Task Submitted')
            authStore.checkAuth()
            startPolling()
        } else {
            message.error(res.data?.message || res.data?.error || 'Submission Failed')
            status.value = 'failed'
        }
    } catch (e) {
        const detail = e?.response?.data?.detail || e?.response?.data?.message || e?.response?.data?.error || e?.message
        message.error(detail || 'Error')
        status.value = 'failed'
    } finally {
        loading.value = false
    }
}

const startPolling = () => {
    if (pollTimer.value) clearInterval(pollTimer.value)

    pollTimer.value = setInterval(async () => {
        if (!taskId.value) return

        try {
            const res = await api.get(`/api/digital_human/status/${taskId.value}`, { headers: buildVideoHeaders(model.value) })
            const rawPayload = res.data?.raw || res.data
            const data = res.data?.data || {}
            const statusValue = data.status || extractValue(rawPayload, ['status', 'Status', 'state', 'State'])
            const videoUrlValue = data.video_url || extractValue(rawPayload, ['video_url', 'videoUrl', 'VideoURL', 'VideoUrl'])

            if (statusValue) {
                status.value = statusValue
            }

            if (statusValue === 'done' && videoUrlValue) {
                resultVideoUrl.value = videoUrlValue
                if (!authStore.token) persistLocalHistory(videoUrlValue)
                message.success('Render Complete!')
                clearInterval(pollTimer.value)
                fetchVideoHistory()
            } else if (statusValue === 'failed' || statusValue === 'not_found' || statusValue === 'expired') {
                status.value = 'failed'
                clearInterval(pollTimer.value)
            }
        } catch (e) {
            console.error('Poll error', e)
        }
    }, 10000)
}

const resetTaskState = () => {
    taskId.value = ''
    status.value = ''
    resultVideoUrl.value = ''
    if (pollTimer.value) clearInterval(pollTimer.value)
}

const fetchVideoHistory = async () => {
    if (!authStore.token) {
        videoHistory.value = loadLocalHistory(DIGITAL_HUMAN_HISTORY_KEY)
        return
    }
    try {
        const res = await api.get('/api/video/history', { headers: buildVideoHeaders(model.value) })
        if (Array.isArray(res.data)) {
            videoHistory.value = res.data.filter((item) => item.video_url && (item.mode || 'digital_human') === 'digital_human')
        }
    } catch (e) {}
}

const persistLocalHistory = (videoUrl) => {
    if (!videoUrl) return
    const meta = pendingMeta.value || {}
    const entry = {
        id: meta.id || taskId.value || `${Date.now()}`,
        task_id: taskId.value || '',
        video_url: videoUrl,
        prompt: meta.prompt || prompt.value.trim(),
        duration: meta.duration || Math.round(audioMeta.value?.duration || 0),
        model: meta.model || model.value,
        mode: 'digital_human',
        created_at: Math.floor(Date.now() / 1000)
    }
    videoHistory.value = prependLocalHistory(DIGITAL_HUMAN_HISTORY_KEY, entry, {
        idResolver: (item) => item?.id || item?.task_id || item?.video_url
    })
}

const updateImageMeta = (rawFile) => {
    if (!rawFile) return
    imageMeta.value = { size: rawFile.size || 0, width: 0, height: 0, type: rawFile.type || '' }
    const objectUrl = URL.createObjectURL(rawFile)
    const img = new Image()
    img.onload = () => {
        imageMeta.value.width = img.width || 0
        imageMeta.value.height = img.height || 0
        URL.revokeObjectURL(objectUrl)
    }
    img.onerror = () => URL.revokeObjectURL(objectUrl)
    img.src = objectUrl
}

const updateAudioMeta = (rawFile) => {
    if (!rawFile) return
    audioMeta.value = { size: rawFile.size || 0, duration: 0, type: rawFile.type || '' }
    const objectUrl = URL.createObjectURL(rawFile)
    const audio = new Audio()
    audio.onloadedmetadata = () => {
        audioMeta.value.duration = audio.duration || 0
        URL.revokeObjectURL(objectUrl)
    }
    audio.onerror = () => URL.revokeObjectURL(objectUrl)
    audio.src = objectUrl
    audio.load()
}

const formatBytes = (bytes) => {
    if (!bytes) return ''
    const mb = bytes / (1024 * 1024)
    if (mb >= 1) return `${mb.toFixed(2)} MB`
    const kb = bytes / 1024
    return `${kb.toFixed(1)} KB`
}

const formatDuration = (seconds) => {
    if (!seconds) return ''
    const total = Math.round(seconds)
    const mins = Math.floor(total / 60)
    const secs = total % 60
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`
}

const formatTime = (timestamp) => {
    try {
        const value = Number(timestamp || Date.now())
        const ms = value < 1e12 ? value * 1000 : value
        return new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } catch (e) {
        return '—'
    }
}

const extractValue = (payload, keys) => {
    if (!payload) return null
    if (Array.isArray(payload)) {
        for (const item of payload) {
            const found = extractValue(item, keys)
            if (found !== null && found !== undefined) return found
        }
        return null
    }
    if (typeof payload === 'object') {
        for (const key of keys) {
            if (Object.prototype.hasOwnProperty.call(payload, key)) {
                return payload[key]
            }
        }
        for (const value of Object.values(payload)) {
            const found = extractValue(value, keys)
            if (found !== null && found !== undefined) return found
        }
    }
    return null
}

onUnmounted(() => {
    if (pollTimer.value) clearInterval(pollTimer.value)
    revokeObjectUrl(imagePreviewUrl.value)
    revokeObjectUrl(audioPreviewUrl.value)
})

onMounted(() => {
    loadModelCatalog()
    fetchVideoHistory()
})
</script>
