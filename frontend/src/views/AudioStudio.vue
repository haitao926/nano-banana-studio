<template>
  <div class="h-[calc(100vh-140px)] grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch overflow-hidden">
    <!-- Left: Controls -->
    <div class="lg:col-span-4 flex flex-col h-full min-h-0 animate-slide-up">
       <div class="bg-white/80 backdrop-blur-xl border border-white/60 rounded-[24px] p-6 shadow-sm flex flex-col h-full overflow-y-auto custom-scrollbar hover:shadow-md transition-shadow duration-300">
          <div class="flex items-center gap-2 border-b border-slate-100 pb-5 mb-5 shrink-0">
             <h3 class="typo-section-title flex items-center gap-2">
                <span class="w-2 h-2 rounded-full bg-indigo-500"></span> {{ localeStore.t('audio.title') }}
             </h3>
             <span class="typo-badge text-white bg-gradient-to-r from-indigo-500 to-purple-500 px-2 py-0.5 rounded shadow-sm scale-90">Beta</span>
          </div>

          <!-- Settings -->
          <div class="grid grid-cols-2 gap-4 mb-6 shrink-0">
             <div class="space-y-1.5 col-span-2">
                <label class="typo-label pl-1">{{ localeStore.t('audio.mode') }}</label>
                <div class="bg-slate-50 p-1 rounded-xl flex gap-1 border border-slate-100">
                    <button @click="settings.mode = 'speech'" class="flex-1 py-2 rounded-lg typo-button-compact transition-all" :class="settings.mode === 'speech' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'">{{ localeStore.t('audio.modes.speech') }}</button>
                    <button @click="settings.mode = 'music'" class="flex-1 py-2 rounded-lg typo-button-compact transition-all" :class="settings.mode === 'music' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'">{{ localeStore.t('audio.modes.music') }}</button>
                    <button @click="settings.mode = 'sfx'" class="flex-1 py-2 rounded-lg typo-button-compact transition-all" :class="settings.mode === 'sfx' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'">{{ localeStore.t('audio.modes.sfx') }}</button>
                </div>
             </div>

             <div v-if="settings.mode === 'speech'" class="space-y-1.5 col-span-2">
                <label class="typo-label pl-1">{{ localeStore.t('audio.model') }}</label>
                <div class="relative group">
                    <select v-model="settings.model" :disabled="!ttsModelOptions.length" class="w-full px-4 py-3 bg-white border border-slate-200 hover:border-indigo-400 rounded-xl typo-input font-sans outline-none focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 transition-all shadow-sm appearance-none disabled:opacity-50 disabled:cursor-not-allowed">
                        <option v-if="!ttsModelOptions.length" value="" disabled>请先配置模型</option>
                        <option v-for="option in ttsModelOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                    </select>
                    <div class="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400 group-hover:text-indigo-500 transition-colors">▼</div>
                </div>
             </div>
             
             <div v-if="settings.mode === 'speech'" class="space-y-3 col-span-2 pt-2 border-t border-slate-50">
                <div class="flex items-center justify-between">
                    <label class="typo-label pl-1">{{ localeStore.t('audio.voice_selection') }}</label>
                    <span class="typo-label-compact text-indigo-500 bg-indigo-50 px-2 py-0.5 rounded-full">{{ filteredVoiceOptions.length }} {{ localeStore.t('audio.voice_count') }}</span>
                </div>
                <!-- Gender & Task Filters (Now under the main Voice Selection label) -->
                <div class="grid grid-cols-2 gap-3">
                    <select v-model="voiceFilter.gender" class="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg typo-input font-sans outline-none focus:border-indigo-500 transition-all">
                        <option v-for="option in genderOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                    </select>
                    <select v-model="voiceFilter.task" class="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg typo-input font-sans outline-none focus:border-indigo-500 transition-all">
                        <option v-for="option in taskOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                    </select>
                </div>
                <!-- Voice List -->
                <div class="space-y-1.5 pt-1">
                    <div class="relative group">
                        <select v-model="settings.voice" class="w-full px-4 py-3 bg-white border border-slate-200 hover:border-indigo-400 rounded-xl typo-input font-sans outline-none focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 transition-all shadow-sm appearance-none">
                            <option v-for="option in filteredVoiceOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                        </select>
                        <div class="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400 group-hover:text-indigo-500 transition-colors">▼</div>
                    </div>
                </div>
             </div>

             <div v-else class="space-y-1.5 col-span-2">
                <label class="typo-label pl-1">{{ localeStore.t('audio.duration') }}</label>
                <div class="flex gap-2">
                    <button v-for="d in ['5', '15', '30']" :key="d" @click="settings.duration = d" class="flex-1 py-2 border rounded-lg typo-button-compact transition-all" :class="settings.duration === d ? 'border-indigo-500 bg-indigo-50 text-indigo-700' : 'border-slate-200 hover:border-slate-300 text-slate-600'">{{ d }}s</button>
                </div>
             </div>
          </div>

          <!-- Prompt -->
          <div class="space-y-2 flex-1 flex flex-col min-h-0">
             <div class="flex justify-between items-center shrink-0">
                <label class="typo-label pl-1">{{ promptLabel }}</label>
             </div>
             <textarea 
                v-model="prompt" 
                class="w-full flex-1 p-4 bg-slate-50/50 border-2 border-slate-100 focus:bg-white focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 rounded-xl typo-prompt font-sans placeholder-slate-400 transition-all outline-none resize-none shadow-inner"
                :placeholder="promptPlaceholder"
             ></textarea>

             <div v-if="showInstructions" class="space-y-2 mt-2 pt-2 border-t border-slate-100">
                <div class="flex items-center justify-between">
                    <label class="typo-label pl-1">{{ localeStore.t('audio.instructions') }}</label>
                    <label class="flex items-center gap-1.5 typo-button-compact text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded cursor-pointer hover:bg-indigo-100 transition-colors">
                        <input type="checkbox" v-model="optimizeInstructions" class="accent-indigo-500" />
                        {{ localeStore.t('audio.auto_optimize') }}
                    </label>
                </div>
                <textarea 
                    v-model="instructions" 
                    class="w-full p-3 bg-white border border-slate-200 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 rounded-xl typo-input transition-all outline-none resize-none leading-relaxed shadow-sm h-20"
                    :placeholder="localeStore.t('audio.instruction_placeholder')"
                ></textarea>
             </div>
          </div>

          <button 
             @click="handleGenerate" 
             :disabled="!prompt.trim() || processing || (settings.mode === 'speech' && !settings.model)" 
             class="w-full mt-6 py-4 bg-gradient-to-r from-blue-500 via-purple-500 to-orange-400 hover:from-blue-400 hover:to-orange-300 text-white rounded-xl typo-button shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40 hover:-translate-y-0.5 active:scale-95 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shrink-0 group"
          >
             <span class="flex items-center justify-center gap-2">
                 <span v-if="processing" class="animate-spin">⟳</span>
                 {{ processing ? localeStore.t('audio.synthesizing') : localeStore.t('audio.generate_btn') }}
             </span>
          </button>
       </div>
    </div>

    <!-- Right: Preview -->
    <div class="lg:col-span-8 h-full min-h-0 animate-scale-in" style="animation-delay: 100ms;">
       <div class="h-full bg-white/60 backdrop-blur-xl rounded-[24px] border border-white/60 p-2 flex flex-col gap-4 shadow-xl shadow-slate-200/50 relative overflow-hidden">
          
          <!-- Screen Area -->
          <div class="flex-1 bg-slate-50/50 rounded-[20px] shadow-inner border border-white/50 relative overflow-hidden group flex items-center justify-center">
              <!-- Dot Pattern -->
              <div class="absolute inset-0 opacity-40 pointer-events-none" style="background-image: radial-gradient(#cbd5e1 1.5px, transparent 1.5px); background-size: 24px 24px;"></div>
              
              <!-- Empty State -->
              <div v-if="!currentAudio && !processing" class="text-center relative z-10 animate-fade-in">
                  <div class="w-24 h-24 bg-white rounded-full flex items-center justify-center mx-auto mb-6 shadow-[0_8px_30px_rgba(0,0,0,0.04)] ring-4 ring-white/50">
                      <span class="icon-lg opacity-50 grayscale">🎵</span>
                  </div>
                  <h3 class="typo-empty-title mb-2">{{ localeStore.t('audio.ready_title') }}</h3>
                  <p class="typo-empty-desc">{{ localeStore.t('audio.ready_desc') }}</p>
              </div>

              <!-- Processing (Shimmer) -->
              <div v-if="processing" class="absolute inset-0 z-20 bg-white/80 backdrop-blur-sm flex flex-col items-center justify-center">
                  <div class="w-64 h-64 rounded-full bg-gradient-to-tr from-indigo-50 via-purple-50 to-indigo-50 animate-pulse relative flex items-center justify-center border-4 border-white shadow-2xl">
                       <div class="absolute inset-0 rounded-full border-t-4 border-indigo-500 animate-spin"></div>
                       <span class="icon-lg animate-bounce">🎹</span>
                  </div>
                  <div class="mt-8 text-center">
                      <p class="typo-status-title">{{ processingTitle }}</p>
                      <p class="typo-label-compact text-indigo-500 mt-1 tracking-[0.2em] animate-pulse">{{ processingSubtitle }}</p>
                  </div>
              </div>

              <!-- Result Audio -->
              <div v-if="currentAudio && !processing" class="relative w-full h-full p-8 flex flex-col items-center justify-center animate-scale-in">
                  <!-- Visualizer Circle -->
                  <div class="w-64 h-64 rounded-full bg-gradient-to-br from-indigo-500 via-purple-600 to-pink-500 flex items-center justify-center shadow-[0_20px_50px_-12px_rgba(99,102,241,0.5)] mb-10 relative overflow-hidden group/disc">
                      <div class="absolute inset-0 bg-[url('/img/noise.png')] opacity-20 mix-blend-overlay"></div>
                      <div class="absolute inset-0 animate-spin-slow opacity-50 bg-gradient-to-t from-black/20 to-transparent"></div>
                      <span class="icon-hero text-white relative z-10 drop-shadow-md group-hover/disc:scale-110 transition-transform duration-500">🎧</span>
                  </div>
                  
                  <!-- Player Card -->
                  <div class="w-full max-w-xl bg-white/90 backdrop-blur-xl p-6 rounded-[24px] border border-white/60 shadow-2xl">
                      <audio controls class="w-full mb-4 accent-indigo-600">
                          <source :src="currentAudio.url" :type="currentAudio.type || 'audio/wav'">
                          Your browser does not support the audio element.
                      </audio>
                      <div class="text-center">
                          <p class="typo-body font-bold text-slate-800 line-clamp-1 mb-1">{{ currentAudio.prompt }}</p>
                          <div class="flex items-center justify-center gap-2 typo-label-compact">
                              <span class="bg-slate-100 px-2 py-0.5 rounded">{{ currentAudio.mode }}</span>
                              <span>•</span>
                              <span>{{ currentAudio.mode === 'speech' ? currentAudio.voice : currentAudio.duration + 's' }}</span>
                          </div>
                      </div>
                  </div>
              </div>
          </div>

          <!-- History Rail -->
          <div v-if="history.length" class="shrink-0 bg-white/80 backdrop-blur-md rounded-[20px] border border-white/60 shadow-sm p-4 animate-slide-up">
               <div class="flex items-center justify-between mb-4 px-2">
                  <h4 class="typo-label-compact tracking-[0.2em]">{{ localeStore.t('audio.history') }}</h4>
                  <span class="typo-label-compact text-indigo-500 bg-indigo-50 px-2 py-0.5 rounded-full">{{ history.length }}</span>
               </div>
               <div class="flex gap-4 overflow-x-auto custom-scrollbar pb-2">
                    <button v-for="item in history" :key="item.id" @click="currentAudio = item"
                        class="flex-shrink-0 w-48 text-left p-3 rounded-2xl border transition-all duration-300 group relative overflow-hidden"
                        :class="currentAudio?.id === item.id ? 'bg-indigo-600 border-indigo-600 shadow-lg shadow-indigo-500/30' : 'bg-white border-slate-100 hover:border-indigo-300 hover:shadow-md'">
                        
                        <div class="flex items-center justify-between mb-2">
                            <span class="typo-label-compact" :class="currentAudio?.id === item.id ? 'text-indigo-200' : 'text-slate-400'">{{ formatTime(item.created_at || item.id) }}</span>
                            <span class="typo-caption-compact" :class="currentAudio?.id === item.id ? 'text-white' : 'text-slate-400'">🎵</span>
                        </div>
                        <p class="typo-button-compact line-clamp-2 mb-2 leading-relaxed" :class="currentAudio?.id === item.id ? 'text-white' : 'text-slate-700'">{{ item.prompt }}</p>
                        <div class="typo-label-compact" :class="currentAudio?.id === item.id ? 'text-indigo-200' : 'text-slate-400'">
                             {{ item.mode === 'speech' ? item.voice : item.duration + 's' }}
                        </div>
                    </button>
               </div>
          </div>
       </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import api from '../services/api'
import { fetchModelCatalog } from '../services/modelCatalog'
import { useMessage } from 'naive-ui'
import { useLocaleStore } from '../stores/locale'
import { useAuthStore } from '../stores/auth'
import { voiceCatalog } from '../data/voiceCatalog'

const localeStore = useLocaleStore()
const message = useMessage()
const authStore = useAuthStore()
const modelCatalog = ref([])

const loadModelCatalog = async () => {
    try {
        modelCatalog.value = await fetchModelCatalog()
    } catch (e) {
        modelCatalog.value = []
    }
}
const prompt = ref('')
const processing = ref(false)
const currentAudio = ref(null)
const history = ref([])

const ttsModelOptions = computed(() => {
  const items = modelCatalog.value.filter((m) => m?.service === 'audio')
  return items.map((item) => ({
    label: item.label || item.model,
    value: item.model
  }))
})

const genderOptions = computed(() => [
  { label: localeStore.t('audio.filters.all_genders'), value: 'all' },
  { label: localeStore.t('audio.filters.female'), value: 'female' },
  { label: localeStore.t('audio.filters.male'), value: 'male' }
])

const taskOptions = computed(() => [
  { label: localeStore.t('audio.filters.all_scenarios'), value: 'all' },
  { label: localeStore.t('audio.filters.general'), value: 'general' },
  { label: localeStore.t('audio.filters.character'), value: 'character' },
  { label: localeStore.t('audio.filters.broadcast'), value: 'broadcast' },
  { label: localeStore.t('audio.filters.sleep'), value: 'sleep' },
  { label: localeStore.t('audio.filters.dialect'), value: 'dialect' },
  { label: localeStore.t('audio.filters.intl'), value: 'intl' }
])

const settings = reactive({
    mode: 'speech',
    duration: '15',
    voice: 'Cherry',
    model: ''
})

watch(
    ttsModelOptions,
    (options) => {
        const list = options || []
        if (!list.length) {
            settings.model = ''
            return
        }
        if (!list.some((o) => o.value === settings.model)) settings.model = list[0].value
    },
    { immediate: true }
)

const voiceFilter = reactive({
    gender: 'all',
    task: 'all'
})

const instructions = ref('')
const optimizeInstructions = ref(true)

const supportsInstructions = computed(() => settings.mode === 'speech' && settings.model.includes('instruct'))
const showInstructions = computed(() => supportsInstructions.value)
const promptLabel = computed(() => (settings.mode === 'speech' ? localeStore.t('audio.prompt_label_speech') : localeStore.t('audio.prompt_label_audio')))
const promptPlaceholder = computed(() => {
    if (settings.mode === 'speech') return localeStore.t('audio.prompt_placeholder_speech')
    if (settings.mode === 'music') return localeStore.t('audio.prompt_placeholder_music')
    return localeStore.t('audio.prompt_placeholder_sfx')
})
const processingTitle = computed(() => {
    if (settings.mode === 'speech') return localeStore.t('audio.processing_title_speech')
    if (settings.mode === 'music') return localeStore.t('audio.processing_title_music')
    return localeStore.t('audio.processing_title_sfx')
})
const processingSubtitle = computed(() => (settings.mode === 'speech' ? 'AI Voice Engine' : 'Audio Model'))
const formatTime = (timestamp) => {
    try {
        return new Date(Number(timestamp)).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } catch (e) {
        return '—'
    }
}

const normalizeAssetUrl = (url) => {
    if (!url) return ''
    if (url.startsWith('http://') || url.startsWith('https://')) {
        try {
            const parsed = new URL(url)
            if (parsed.pathname.startsWith('/static/')) {
                return `${window.location.origin}${parsed.pathname}`
            }
        } catch (e) {
            // ignore
        }
        return url
    }
    return `${window.location.origin}${url.startsWith('/') ? '' : '/'}${url}`
}

const buildTtsHeaders = (model) => {
    const headers = {}
    if (authStore.token) headers.Authorization = `Bearer ${authStore.token}`
    return headers
}

const fetchAudioHistory = async () => {
    if (!authStore.token) return
    try {
        const res = await api.get('/api/audio/history', { headers: buildTtsHeaders(settings.model) })
        if (Array.isArray(res.data)) {
            history.value = res.data.map((item) => ({
                ...item,
                url: normalizeAssetUrl(item.url)
            }))
            if (!currentAudio.value && history.value.length) {
                currentAudio.value = history.value[0]
            }
        }
    } catch (e) {}
}

const filteredVoiceOptions = computed(() => {
    return voiceCatalog.filter((voice) => {
        const genderMatch = voiceFilter.gender === 'all' || voice.gender === voiceFilter.gender
        const taskMatch = voiceFilter.task === 'all' || voice.tasks.includes(voiceFilter.task)
        return genderMatch && taskMatch
    })
})

watch(filteredVoiceOptions, (list) => {
    if (!list.length) return
    if (!list.find((item) => item.value === settings.voice)) {
        settings.voice = list[0].value
    }
}, { immediate: true })

const handleGenerate = async () => {
    if (!prompt.value.trim()) return
    if (settings.mode === 'speech' && !settings.model) {
        message.warning('请先在模型配置中添加音频模型')
        return
    }
    
    processing.value = true
    try {
        if (settings.mode === 'speech') {
            const payload = {
                text: prompt.value.trim(),
                voice: settings.voice,
                model: settings.model,
                language_type: 'Auto'
            }
            if (showInstructions.value && instructions.value.trim()) {
                payload.instructions = instructions.value.trim()
                payload.optimize_instructions = optimizeInstructions.value
            }

        const res = await api.post('/api/audio/tts', payload, {
                headers: buildTtsHeaders(settings.model)
            })
            if (!res?.data?.success) throw new Error(res?.data?.detail || '语音合成失败')

            const historyItem = res.data.history_item || {
                id: Date.now(),
                url: res.data.url,
                type: res.data.type || 'audio/wav',
                prompt: prompt.value.trim(),
                mode: 'speech',
                model: settings.model,
                voice: settings.voice,
                duration: res.data.duration,
                created_at: Date.now()
            }
            const newAudio = {
                ...historyItem,
                url: normalizeAssetUrl(historyItem.url || res.data.url),
                type: historyItem.type || res.data.type || 'audio/wav'
            }
            currentAudio.value = newAudio
            history.value.unshift(newAudio)
            authStore.checkAuth()
            message.success('Success')
        } else {
            const newAudio = {
                id: Date.now(),
                url: 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3',
                type: 'audio/mpeg',
                prompt: prompt.value.trim(),
                mode: settings.mode,
                duration: settings.duration
            }
            currentAudio.value = newAudio
            history.value.unshift(newAudio)
            message.success('Success')
        }
    } catch (err) {
        const status = err?.response?.status
        const msg = err?.response?.data?.detail || err?.message || 'Failed'
        if (status === 401) {
            message.error('请登录或填写自定义 TTS Key')
            return
        }
        if (status === 403 && /quota|余额|quota exceeded/i.test(msg)) {
            message.error('余额不足，请填写自定义 TTS Key')
            return
        }
        message.error(msg)
    } finally {
        processing.value = false
    }
}

onMounted(() => {
    loadModelCatalog()
    fetchAudioHistory()
})
</script>
