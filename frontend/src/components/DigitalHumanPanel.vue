<template>
  <div class="max-w-4xl mx-auto space-y-8">
    <div class="bg-white dark:bg-gray-800 rounded-3xl p-8 shadow-xl border border-gray-100 dark:border-gray-700 space-y-6">
      <h2 class="text-2xl font-bold flex items-center gap-2">
        <span>🗣️</span> 数字人视频生成 (Digital Human)
        <span class="text-xs font-normal text-gray-500 bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">Beta</span>
      </h2>
      
      <!-- Input Section -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
        
        <!-- Image Input -->
        <div class="space-y-2">
          <label class="text-xs font-bold text-gray-400 uppercase tracking-wider">1. 人像图片 (Image)</label>
          <div class="relative group">
             <n-upload 
                action="/api/upload" 
                :max="1" 
                list-type="image-card" 
                @finish="handleImageUpload"
                :show-file-list="false"
                class="w-full"
             >
                <div v-if="imageUrl" class="relative w-full aspect-square rounded-xl overflow-hidden border-2 border-dashed border-gray-200 dark:border-gray-600 hover:border-blue-400 transition-colors">
                   <img :src="imageUrl" class="w-full h-full object-contain" />
                   <div class="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity text-white text-xs font-bold">点击替换</div>
                </div>
                <div v-else class="w-full aspect-square rounded-xl border-2 border-dashed border-gray-200 dark:border-gray-600 flex flex-col items-center justify-center text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors cursor-pointer">
                   <span class="text-4xl mb-2">📸</span>
                   <span class="text-xs">点击上传人像</span>
                </div>
             </n-upload>
          </div>
        </div>

        <!-- Audio Input -->
        <div class="space-y-4">
           <div class="space-y-2">
              <label class="text-xs font-bold text-gray-400 uppercase tracking-wider">2. 音频 (Audio)</label>
              <n-upload 
                action="/api/upload" 
                :max="1" 
                accept="audio/*"
                @finish="handleAudioUpload"
              >
                <button class="w-full py-3 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl text-sm font-bold text-gray-600 dark:text-gray-300 hover:bg-gray-100 transition-colors flex items-center justify-center gap-2">
                   <span>🎵</span> {{ audioUrl ? '已上传音频 (更换)' : '上传音频文件 (MP3/WAV)' }}
                </button>
              </n-upload>
              <audio v-if="audioUrl" :src="audioUrl" controls class="w-full mt-2 h-8" />
           </div>

           <div class="space-y-2">
              <label class="text-xs font-bold text-gray-400 uppercase tracking-wider">3. 提示词 (Prompt - Optional)</label>
              <textarea v-model="prompt" placeholder="描述表情、动作 (例如: 微笑, 点头)..." class="w-full h-24 p-3 bg-gray-50 dark:bg-gray-900 rounded-xl border-none outline-none text-sm resize-none focus:ring-2 focus:ring-blue-400 transition-all"></textarea>
           </div>
           
           <button 
             @click="submitTask" 
             :disabled="!isValid || loading"
             class="w-full py-4 bg-black dark:bg-white text-white dark:text-black rounded-xl font-bold text-lg hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
           >
             <span v-if="loading">提交中...</span>
             <span v-else>生成视频 (Generate)</span>
           </button>
        </div>
      </div>
      
      <!-- Result Section -->
      <div v-if="taskId || resultVideoUrl" class="border-t border-gray-100 dark:border-gray-700 pt-6">
          <h3 class="text-lg font-bold mb-4">生成状态</h3>
          
          <div v-if="status === 'done' && resultVideoUrl" class="space-y-4">
             <div class="aspect-video bg-black rounded-2xl overflow-hidden shadow-lg">
                <video :src="resultVideoUrl" controls class="w-full h-full" autoplay loop></video>
             </div>
             <div class="flex justify-center">
                <a :href="resultVideoUrl" download class="px-6 py-2 bg-green-500 text-white rounded-full font-bold shadow hover:bg-green-600 transition-all">📥 下载视频</a>
             </div>
          </div>
          
          <div v-else class="bg-gray-50 dark:bg-gray-900 rounded-xl p-6 flex flex-col items-center justify-center gap-4 min-h-[200px]">
             <div v-if="status === 'failed'" class="text-red-500 font-bold">❌ 生成失败</div>
             <div v-else class="flex flex-col items-center gap-2">
                <div class="animate-spin text-4xl">⏳</div>
                <div class="font-bold text-gray-500">{{ statusMsg }}</div>
                <div class="text-xs text-gray-400">Task ID: {{ taskId }}</div>
             </div>
          </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { NUpload, useMessage } from 'naive-ui'
import axios from 'axios'

const message = useMessage()

const imageUrl = ref('')
const audioUrl = ref('')
const prompt = ref('')
const loading = ref(false)
const taskId = ref('')
const status = ref('') // processing, done, failed
const resultVideoUrl = ref('')
const pollTimer = ref(null)

const isValid = computed(() => imageUrl.value && audioUrl.value)
const statusMsg = computed(() => {
    if (status.value === 'processing') return '正在生成中 (预计 1-5 分钟)...'
    if (status.value === 'in_queue') return '排队中...'
    return '等待处理...'
})

const handleImageUpload = ({ file, event }) => {
    try {
        const res = JSON.parse(event.target.response)
        if (res.success) {
            imageUrl.value = res.url
            message.success('Image Uploaded')
        }
    } catch(e) {}
}

const handleAudioUpload = ({ file, event }) => {
    try {
        const res = JSON.parse(event.target.response)
        if (res.success) {
            audioUrl.value = res.url
            message.success('Audio Uploaded')
        }
    } catch(e) {}
}

const submitTask = async () => {
    if (!isValid.value) return
    loading.value = true
    status.value = 'processing'
    resultVideoUrl.value = ''
    taskId.value = ''
    
    try {
        const res = await axios.post('/api/digital_human/submit', {
            image_url: imageUrl.value,
            audio_url: audioUrl.value,
            prompt: prompt.value
        })
        
        if (res.data.data && res.data.data.task_id) {
            taskId.value = res.data.data.task_id
            message.success("Task Submitted")
            startPolling()
        } else {
            message.error(res.data.message || "Submission failed")
            status.value = 'failed'
        }
    } catch (e) {
        message.error("Error submitting task")
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
            const res = await axios.get(`/api/digital_human/status/${taskId.value}`)
            const data = res.data.data
            if (data) {
                status.value = data.status
                
                if (data.status === 'done') {
                    resultVideoUrl.value = data.video_url
                    message.success("Video Generated!")
                    clearInterval(pollTimer.value)
                } else if (data.status === 'failed' || data.status === 'not_found' || data.status === 'expired') {
                     status.value = 'failed'
                     clearInterval(pollTimer.value)
                }
            }
        } catch (e) {
            console.error("Poll error", e)
        }
    }, 5000)
}

onUnmounted(() => {
    if (pollTimer.value) clearInterval(pollTimer.value)
})

</script>