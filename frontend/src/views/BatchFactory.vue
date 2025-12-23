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

    <!-- 底部操作栏 -->
    <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex justify-between items-center sticky bottom-6">
      <div class="text-gray-600">
        已选: <strong class="text-yellow-600">{{ selectedStyles.length }}</strong> 种风格 x 
        <strong class="text-yellow-600">{{ selectedReqs.length }}</strong> 个需求 = 
        <strong class="text-lg text-black">{{ totalTasks }}</strong> 张图片
      </div>

      <n-button 
        type="primary" 
        size="large" 
        color="#f59e0b"
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
import { NCard, NCheckbox, NCheckboxGroup, NButton, NTag, NAlert, useMessage } from 'naive-ui'
import axios from 'axios'

const message = useMessage()
const config = ref(null)
const selectedStyles = ref([])
const selectedReqs = ref([])
const isRunning = ref(false)

const totalTasks = computed(() => selectedStyles.value.length * selectedReqs.value.length)

const fetchConfig = async () => {
  try {
    const res = await axios.get('/api/config')
    config.value = res.data
  } catch (err) {
    message.error('无法加载配置，请检查后端服务')
  }
}

const startBatch = () => {
  message.info('批量生成功能需要在后端实现任务队列，目前仅为演示界面。')
  // 这里可以调用 /api/generate/batch
}

onMounted(fetchConfig)
</script>
