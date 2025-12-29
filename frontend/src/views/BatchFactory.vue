<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <div>
        <h2 class="text-2xl font-bold text-gray-800">批量工厂</h2>
        <p class="text-gray-500 mt-1">组合风格与内容，打造图片矩阵</p>
      </div>
      <div v-if="config" class="text-right">
        <n-tag type="info">已加载 {{ Object.keys(config.system_prompts).length }} 种风格</n-tag>
      </div>
    </div>

    <n-alert v-if="!config" type="info" title="正在加载配置...">
      连接后端服务中...
    </n-alert>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <!-- 1. 选择风格 -->
      <n-card title="Step 1: 选择风格 (Styles)" size="small">
        <n-checkbox-group v-model:value="selectedStyles">
          <div class="grid grid-cols-1 gap-2">
            <n-checkbox 
              v-for="(prompt, key) in config.system_prompts" 
              :key="key" 
              :value="key"
              class="p-2 hover:bg-gray-50 rounded"
            >
              <div class="font-medium">{{ key }}</div>
              <div class="text-xs text-gray-500 truncate w-64">{{ prompt }}</div>
            </n-checkbox>
          </div>
        </n-checkbox-group>
      </n-card>

      <!-- 2. 选择内容 -->
      <n-card title="Step 2: 选择内容 (Requirements)" size="small">
        <n-checkbox-group v-model:value="selectedReqs">
          <div class="grid grid-cols-1 gap-2 max-h-[400px] overflow-y-auto">
            <n-checkbox 
              v-for="(prompt, index) in config.requirement_prompts" 
              :key="index" 
              :value="index"
              class="p-2 hover:bg-gray-50 rounded"
            >
              <div class="text-sm">{{ index + 1 }}. {{ prompt }}</div>
            </n-checkbox>
          </div>
        </n-checkbox-group>
      </n-card>
    </div>

    <!-- 生成结果展示区 -->
    <div v-if="results.length > 0" class="space-y-4">
      <div class="flex justify-between items-center bg-green-50 p-4 rounded-lg border border-green-100">
        <div>
          <h3 class="text-lg font-bold text-green-800">生成完成 ({{ results.length }}张)</h3>
          <p class="text-sm text-green-600">所有图片已生成完毕，您可以预览或一键打包下载。</p>
        </div>
        <n-button type="success" size="large" @click="downloadAll">
          📦 一键打包下载 (ZIP)
        </n-button>
      </div>
      
      <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
        <div v-for="img in results" :key="img.id" class="border rounded-lg p-2 bg-white shadow-sm hover:shadow-md transition-shadow relative group">
           <div class="aspect-square w-full overflow-hidden rounded mb-2 bg-gray-100">
             <n-image :src="img.url" class="w-full h-full object-cover" object-fit="cover" />
           </div>
           <div class="text-xs text-gray-500 truncate" :title="img.filename">{{ img.filename }}</div>
        </div>
      </div>
    </div>

    <!-- 底部操作栏 -->
    <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex justify-between items-center sticky bottom-6 z-10">
      <div class="text-gray-600">
        已选: <strong class="text-yellow-600">{{ selectedStyles.length }}</strong> 种风格 x 
        <strong class="text-yellow-600">{{ selectedReqs.length }}</strong> 个需求 = 
        <strong class="text-lg text-black">{{ totalTasks }}</strong> 张图片
      </div>

      <n-button 
        type="primary" 
        size="large" 
        color="#f59e0b"
        :loading="isRunning"
        :disabled="totalTasks === 0 || isRunning"
        @click="startBatch"
      >
        {{ isRunning ? '正在生产中...' : '🚀 启动批量任务' }}
      </n-button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { NCard, NCheckbox, NCheckboxGroup, NButton, NTag, NAlert, NImage, useMessage } from 'naive-ui'
import axios from 'axios'

const message = useMessage()
const config = ref(null)
const selectedStyles = ref([])
const selectedReqs = ref([])
const isRunning = ref(false)
const results = ref([])

const totalTasks = computed(() => selectedStyles.value.length * selectedReqs.value.length)

const fetchConfig = async () => {
  try {
    const res = await axios.get('/api/config')
    config.value = res.data
  } catch (err) {
    message.error('无法加载配置，请检查后端服务')
  }
}

const startBatch = async () => {
  if (totalTasks.value === 0) return
  isRunning.value = true
  results.value = [] // Clear previous results
  
  message.loading('开始批量生成，请保持页面打开... (任务较多时可能需要几分钟)')
  
  try {
    const res = await axios.post('/api/generate/batch', {
      system_keys: selectedStyles.value,
      requirement_indices: selectedReqs.value
    })
    
    if (res.data.success) {
      results.value = res.data.results
      message.success(`成功生成 ${res.data.successful} 张图片`)
      // Scroll to results
      setTimeout(() => {
        window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
      }, 500)
    }
  } catch (err) {
    console.error(err)
    message.error('生成失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    isRunning.value = false
  }
}

const downloadAll = async () => {
    if (results.value.length === 0) return
    const filenames = results.value.map(r => r.filename)
    
    message.loading('正在打包...')
    try {
        const response = await axios.post('/api/download/batch', { filenames }, {
            responseType: 'blob'
        })
        
        // Trigger download
        const url = window.URL.createObjectURL(new Blob([response.data]))
        const link = document.createElement('a')
        link.href = url
        link.setAttribute('download', `NanoBanana_Batch_${Date.now()}.zip`)
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        message.success('下载已开始')
    } catch (err) {
        message.error('下载失败')
    }
}

onMounted(fetchConfig)
</script>