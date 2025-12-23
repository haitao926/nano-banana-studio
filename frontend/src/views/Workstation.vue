<template>
  <div class="space-y-8">

    <!-- 顶部主导航栏 -->
    <div class="flex justify-center mb-10">
      <div class="bg-white dark:bg-gray-800 p-1.5 rounded-2xl flex gap-2 shadow-sm border border-gray-100 dark:border-gray-700">
        
        <button 
          @click="currentTab = 'single'"
          class="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold transition-all"
          :class="currentTab === 'single' ? 'bg-black text-white shadow-md' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900 dark:hover:bg-gray-700 dark:hover:text-gray-200'"
        >
          <span>✨</span> 单图创作
        </button>

        <button 
          @click="currentTab = 'batch'"
          class="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold transition-all"
          :class="currentTab === 'batch' ? 'bg-black text-white shadow-md' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900 dark:hover:bg-gray-700 dark:hover:text-gray-200'"
        >
          <span>🏭</span> 批量工坊
        </button>

        <div class="w-px bg-gray-200 dark:bg-gray-700 my-2"></div>

        <button 
          @click="currentTab = 'gallery'"
          class="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold transition-all"
          :class="currentTab === 'gallery' ? 'bg-yellow-100 text-yellow-800 shadow-sm' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900 dark:hover:bg-gray-700 dark:hover:text-gray-200'"
        >
          <span>🖼️</span> 学科画廊
        </button>
      </div>
    </div>

    <!-- ==================== 页面 1: 单图创作 ==================== -->
    <Transition name="fade" mode="out-in">
      <div v-if="currentTab === 'single'" class="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
        
        <!-- 左侧：控制台 -->
        <div class="space-y-8">
          <div class="space-y-2">
            <h2 class="text-3xl font-bold text-gray-900 dark:text-white">Single Creation</h2>
            <p class="text-gray-400">精心打磨每一张教学素材。</p>
          </div>

          <div class="bg-white dark:bg-gray-800 rounded-3xl p-6 shadow-xl border border-gray-100 dark:border-gray-700 space-y-6">
            
            <!-- 参数行 -->
            <div class="grid grid-cols-2 gap-4">
              <div class="space-y-2">
                <label class="text-xs font-bold text-gray-400 uppercase tracking-wider">Subject</label>
                <n-popselect v-model:value="settings.subject" :options="subjectOptions" trigger="click">
                  <button class="w-full flex justify-between items-center px-4 py-3 bg-gray-50 dark:bg-gray-900 rounded-xl font-bold hover:bg-yellow-50 transition-colors">
                    <span>{{ getSubjectLabel(settings.subject) }}</span>
                    <span>▼</span>
                  </button>
                </n-popselect>
              </div>

              <div class="space-y-2">
                <label class="text-xs font-bold text-gray-400 uppercase tracking-wider">Aspect Ratio</label>
                 <n-popselect v-model:value="settings.aspectRatio" :options="ratioOptions" trigger="click">
                  <button class="w-full flex justify-between items-center px-4 py-3 bg-gray-50 dark:bg-gray-900 rounded-xl font-bold hover:bg-gray-100 transition-colors">
                    <span>{{ settings.aspectRatio }}</span>
                    <span>▼</span>
                  </button>
                </n-popselect>
              </div>
            </div>

            <!-- 输入框 -->
            <div class="space-y-2">
               <label class="text-xs font-bold text-gray-400 uppercase tracking-wider">Prompt</label>
               <textarea
                v-model="inputText"
                placeholder="描述一个清晰的画面..."
                class="w-full h-48 p-4 bg-gray-50 dark:bg-gray-900 rounded-xl border-none outline-none text-lg resize-none focus:ring-2 focus:ring-yellow-400 transition-all"
                @keydown.enter.ctrl="handleGenerateSingle"
              ></textarea>
            </div>

            <button 
              @click="handleGenerateSingle"
              :disabled="!inputText.trim() || processing"
              class="w-full py-4 bg-black dark:bg-white text-white dark:text-black rounded-xl font-bold text-lg hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50"
            >
              <span v-if="processing">Drawing...</span>
              <span v-else>Generate Image</span>
            </button>
          </div>
        </div>

        <!-- 右侧：预览大图 -->
        <div class="relative min-h-[500px] flex items-center justify-center bg-gray-100 dark:bg-gray-800 rounded-3xl border-2 border-dashed border-gray-200 dark:border-gray-700 overflow-hidden">
          <div v-if="latestSingleTask" class="relative w-full h-full p-4">
             <div v-if="latestSingleTask.status === 'processing' || latestSingleTask.status === 'pending'" class="absolute inset-0 flex flex-col items-center justify-center bg-white/80 dark:bg-gray-800/80 backdrop-blur z-10">
                <div class="text-6xl animate-bounce mb-4">🍌</div>
                <p class="font-bold text-gray-500">AI is painting...</p>
             </div>
             <img 
               v-if="latestSingleTask.resultUrl" 
               :src="latestSingleTask.resultUrl" 
               class="w-full h-full object-contain rounded-xl shadow-lg cursor-pointer"
               @click="openImage(latestSingleTask.resultUrl)"
             />
             <div v-else-if="latestSingleTask.status === 'failed'" class="text-center text-red-500">
               <div class="text-4xl mb-2">❌</div>
               Generation Failed
             </div>
          </div>
          <div v-else class="text-center text-gray-400">
            <div class="text-6xl mb-4">🎨</div>
            <p>Ready to create</p>
          </div>
        </div>
      </div>
    </Transition>


    <!-- ==================== 页面 2: 批量工坊 ==================== -->
    <Transition name="fade" mode="out-in">
      <div v-if="currentTab === 'batch'" class="space-y-10">
        
        <section class="max-w-6xl mx-auto space-y-6">
           <div class="text-center space-y-2">
            <h2 class="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-purple-600">
              Batch Factory
            </h2>
            <p class="text-gray-400">文本输入 或 JSON导入，灵活满足大规模生产。</p>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            
            <!-- 左侧：JSON 导入区 -->
            <div class="md:col-span-1 bg-blue-50 dark:bg-gray-800 rounded-2xl p-6 border-2 border-dashed border-blue-200 dark:border-gray-600 flex flex-col justify-center items-center text-center space-y-4 hover:bg-blue-100 dark:hover:bg-gray-700 transition-colors cursor-pointer relative">
               <input 
                 type="file" 
                 accept=".json" 
                 class="absolute inset-0 opacity-0 cursor-pointer"
                 @change="handleJsonUpload" 
               />
               <div class="text-4xl">📂</div>
               <div>
                  <h3 class="font-bold text-blue-800 dark:text-blue-300">Import JSON</h3>
                  <p class="text-xs text-blue-600 dark:text-gray-400 mt-1">Drag & Drop or Click</p>
               </div>
               <button @click.stop="downloadTemplate" class="text-xs text-gray-500 underline hover:text-blue-600 z-10 relative">下载模板 (Template)</button>
            </div>

            <!-- 右侧：文本输入区 -->
            <div class="md:col-span-2 bg-white dark:bg-gray-800 rounded-2xl shadow-xl overflow-hidden flex flex-col">
               <div class="flex items-center gap-4 px-6 py-4 border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                  <span class="text-sm font-bold text-gray-500">Default Settings:</span>
                  <n-popselect v-model:value="settings.subject" :options="subjectOptions" trigger="click">
                    <button class="px-3 py-1 bg-white dark:bg-gray-700 rounded-md text-sm border hover:border-blue-400 transition-colors">
                      🏷️ {{ getSubjectLabel(settings.subject) }}
                    </button>
                  </n-popselect>
                  <n-popselect v-model:value="settings.aspectRatio" :options="ratioOptions" trigger="click">
                    <button class="px-3 py-1 bg-white dark:bg-gray-700 rounded-md text-sm border hover:border-blue-400 transition-colors">
                      📐 {{ settings.aspectRatio }}
                    </button>
                  </n-popselect>
               </div>

               <div class="relative flex-1">
                  <textarea
                    v-model="batchInputText"
                    placeholder="在此输入批量提示词 (每行一个)..."
                    class="w-full h-full min-h-[200px] p-6 bg-transparent border-none outline-none text-base resize-none font-mono leading-relaxed"
                  ></textarea>
                  
                  <div class="absolute bottom-6 right-6">
                     <button 
                      @click="handleGenerateBatch"
                      :disabled="!batchInputText.trim() || processing"
                      class="px-8 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-full font-bold shadow-lg hover:shadow-blue-500/30 transition-all disabled:opacity-50"
                    >
                      <span v-if="processing">Processing...</span>
                      <span v-else>🚀 Run Batch Text</span>
                    </button>
                  </div>
               </div>
            </div>
          </div>
        </section>

        <!-- 批量任务流 -->
        <section v-if="batchQueue.length > 0" class="max-w-[1600px] mx-auto px-6">
           <div class="flex items-center justify-between mb-4">
              <h3 class="font-bold text-gray-500">Task Queue ({{ batchQueue.filter(t=>t.status==='done').length }}/{{ batchQueue.length }})</h3>
              <button @click="batchQueue = []" class="text-xs text-red-400 hover:underline">Clear All</button>
           </div>
           
           <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
              <TransitionGroup name="list">
                <div v-for="task in reversedBatchQueue" :key="task.id" class="group relative bg-white dark:bg-gray-800 rounded-lg overflow-hidden border border-gray-100 dark:border-gray-700 shadow-sm">
                   
                   <div class="aspect-square relative">
                      <img v-if="task.status === 'done'" :src="task.resultUrl" class="w-full h-full object-cover cursor-pointer hover:opacity-90" @click="openImage(task.resultUrl)" />
                      <div v-else-if="task.status === 'pending'" class="w-full h-full flex items-center justify-center bg-gray-50 text-gray-300 text-xs">Waiting...</div>
                      <div v-else-if="task.status === 'processing'" class="w-full h-full flex flex-col items-center justify-center bg-blue-50 text-blue-500"><div class="animate-spin text-xl mb-1">⏳</div></div>
                      <div v-else class="w-full h-full flex items-center justify-center bg-red-50 text-red-400 text-xs">Failed</div>
                      
                      <!-- 标签 -->
                      <div class="absolute top-1 left-1" v-if="task.settings.subject">
                         <span class="px-1.5 py-0.5 bg-black/50 text-white text-[9px] rounded backdrop-blur">
                            {{ getSubjectLabel(task.settings.subject) }}
                         </span>
                      </div>
                   </div>
                   <div class="p-2">
                      <p class="text-[10px] text-gray-500 truncate" :title="task.prompt">{{ task.prompt }}</p>
                   </div>
                </div>
              </TransitionGroup>
           </div>
        </section>
      </div>
    </Transition>

    <!-- ==================== 页面 3: 学科画廊 ==================== -->
    <Transition name="fade" mode="out-in">
      <div v-if="currentTab === 'gallery'" class="flex gap-8 max-w-[1600px] mx-auto min-h-[600px]">
        <aside class="w-64 flex-shrink-0 space-y-2">
          <h3 class="font-bold text-gray-400 px-4 mb-4 text-xs uppercase tracking-wider">Subjects</h3>
          <button 
            @click="galleryFilter = 'all'"
            class="w-full text-left px-4 py-3 rounded-xl font-medium transition-colors flex justify-between items-center"
            :class="galleryFilter === 'all' ? 'bg-black text-white' : 'hover:bg-gray-100 text-gray-600'"
          >
            <span>全部图片</span>
            <span class="opacity-60 text-xs">{{ galleryImages.length }}</span>
          </button>
          <button 
            v-for="sub in subjectOptions"
            :key="sub.value"
            @click="galleryFilter = sub.value"
            class="w-full text-left px-4 py-3 rounded-xl font-medium transition-colors flex justify-between items-center group"
            :class="galleryFilter === sub.value ? 'bg-yellow-100 text-yellow-800' : 'hover:bg-gray-100 text-gray-600'"
          >
            <span class="flex items-center gap-2"><span>{{ sub.icon }}</span> {{ sub.label }}</span>
            <span class="opacity-0 group-hover:opacity-100 text-xs bg-gray-200 px-1.5 rounded-full transition-opacity">{{ getCountBySubject(sub.value) }}</span>
          </button>
        </aside>
        <main class="flex-1 bg-white dark:bg-gray-800 rounded-3xl p-8 border border-gray-100 shadow-sm min-h-screen">
          <div v-if="filteredGallery.length === 0" class="h-full flex flex-col items-center justify-center text-gray-400"><div class="text-4xl mb-4">📭</div><p>暂无图片</p></div>
          <div v-else class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
             <div 
               v-for="img in filteredGallery" 
               :key="img.id" 
               class="group relative aspect-square rounded-xl overflow-hidden cursor-pointer"
               @click="openImage(img.url)"
             >
               <img :src="img.url" class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110" loading="lazy" />
               <div class="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-4">
                 <span class="text-white text-xs font-bold mb-1">{{ getSubjectLabel(img.subject) }}</span>
                 <p class="text-gray-200 text-[10px] line-clamp-2">{{ img.prompt }}</p>
               </div>
             </div>
          </div>
        </main>
      </div>
    </Transition>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { NPopselect, useMessage } from 'naive-ui'
import axios from 'axios'

const message = useMessage()
const currentTab = ref('single') 

// --- 状态 ---
const inputText = ref('') 
const batchInputText = ref('') 
const processing = ref(false)

const singleTasks = ref([]) 
const batchQueue = ref([])

const galleryFilter = ref('all')
const galleryImages = ref([])

// --- 设置 ---
const settings = ref({
  subject: 'general',
  aspectRatio: '1:1',
  style: 'vivid',
  quality: 'standard'
})

const subjectOptions = [
  { label: 'General (通用)', value: 'general', icon: '🌐' },
  { label: 'Math (数学)', value: 'math', icon: '📐' },
  { label: 'Science (科学)', value: 'science', icon: '🔬' },
  { label: 'English (英语)', value: 'english', icon: 'abc' },
  { label: 'Art (艺术)', value: 'art', icon: '🎨' },
  { label: 'History (历史)', value: 'history', icon: '🏛️' }
]

const ratioOptions = [
  { label: 'Square (1:1)', value: '1:1' },
  { label: 'Landscape (16:9)', value: '16:9' },
  { label: 'Portrait (9:16)', value: '9:16' }
]

// --- 辅助 ---
const getSubjectLabel = (val) => subjectOptions.find(o => o.value === val)?.label || val
const getCountBySubject = (sub) => galleryImages.value.filter(i => i.subject === sub).length
const latestSingleTask = computed(() => singleTasks.value[singleTasks.value.length - 1] || null)
const reversedBatchQueue = computed(() => [...batchQueue.value].reverse())
const filteredGallery = computed(() => {
  if (galleryFilter.value === 'all') return galleryImages.value
  return galleryImages.value.filter(img => img.subject === galleryFilter.value)
})

// --- 逻辑: JSON 处理 ---
const handleJsonUpload = (event) => {
  const file = event.target.files[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const tasks = JSON.parse(e.target.result)
      if (!Array.isArray(tasks)) throw new Error('Root must be an array')
      
      const newTasks = tasks.map(t => ({
        id: Date.now() + Math.random().toString(),
        prompt: t.prompt,
        status: 'pending',
        resultUrl: null,
        settings: {
          subject: t.subject || settings.value.subject,
          aspectRatio: t.aspectRatio || settings.value.aspectRatio,
          style: t.style || settings.value.style
        }
      }))
      
      batchQueue.value.push(...newTasks)
      message.success(`成功导入 ${newTasks.length} 个任务`)
      processBatchQueue() // 自动开始
      
    } catch (err) {
      message.error('JSON 格式错误: ' + err.message)
    }
  }
  reader.readAsText(file)
  event.target.value = '' // reset
}

const downloadTemplate = () => {
  const template = [
    { prompt: "Example prompt 1", subject: "science", aspectRatio: "1:1" },
    { prompt: "Example prompt 2", subject: "math", aspectRatio: "16:9" }
  ]
  const blob = new Blob([JSON.stringify(template, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'nano_banana_template.json'
  a.click()
}

// --- 逻辑: 生成 ---
const handleGenerateSingle = async () => {
  if (!inputText.value.trim()) return
  const newTask = { id: Date.now(), prompt: inputText.value, status: 'pending', resultUrl: null, settings: { ...settings.value } }
  singleTasks.value.push(newTask)
  processing.value = true
  await executeTask(newTask)
  processing.value = false
}

const handleGenerateBatch = async () => {
  const text = batchInputText.value.trim()
  if (!text) return
  const prompts = text.split('\n').map(p => p.trim()).filter(p => p.length > 0)
  const newTasks = prompts.map(p => ({ id: Date.now() + Math.random().toString(), prompt: p, status: 'pending', resultUrl: null, settings: { ...settings.value } }))
  batchQueue.value.push(...newTasks)
  batchInputText.value = ''
  message.success(`${newTasks.length} tasks added`)
  processBatchQueue()
}

const executeTask = async (task) => {
  task.status = 'processing'
  try {
    let size = '1024x1024'
    if (task.settings.aspectRatio === '16:9') size = '1792x1024'
    if (task.settings.aspectRatio === '9:16') size = '1024x1792'

    const res = await axios.post('/api/generate/single', {
      prompt: task.prompt,
      size: size,
      style: task.settings.style || 'vivid'
    })

    if (res.data.success) {
      task.status = 'done'
      task.resultUrl = res.data.url
      addToGallery(task)
    } else { throw new Error('API Fail') }
  } catch (e) { task.status = 'failed' }
}

const processBatchQueue = async () => {
  if (processing.value) return
  processing.value = true
  while (true) {
    const nextTask = batchQueue.value.find(t => t.status === 'pending')
    if (!nextTask) break
    await executeTask(nextTask)
  }
  processing.value = false
}

const addToGallery = (task) => {
  galleryImages.value.unshift({ id: task.id, url: task.resultUrl, prompt: task.prompt, subject: task.settings.subject, timestamp: Date.now() })
}

const fetchHistory = async () => {
    try {
        const res = await axios.get('/api/gallery')
        galleryImages.value = res.data.map(img => ({ id: img.name, url: img.url, prompt: 'History Image', subject: 'general', timestamp: img.time }))
    } catch(e) {}
}

const openImage = (url) => { if(url) window.open(url, '_blank') }

onMounted(fetchHistory)
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.list-enter-active, .list-leave-active { transition: all 0.5s ease; }
.list-enter-from { opacity: 0; transform: translateY(20px); }
</style>