<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <div>
        <h2 class="text-2xl font-bold text-gray-800">创作空间</h2>
        <p class="text-gray-500 mt-1">输入提示词，激发无限创意</p>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
      <!-- 左侧：控制区 -->
      <div class="space-y-6">
        <n-card class="shadow-sm rounded-xl border-0">
          <div class="space-y-4">
            <div>
              <div class="flex justify-between items-center mb-2">
                <label class="block text-sm font-medium text-gray-700">Prompt (提示词)</label>
                <n-button 
                  size="tiny" 
                  secondary 
                  type="primary" 
                  @click="handleOptimize" 
                  :loading="optimizing"
                  :disabled="!prompt"
                >
                  ✨ 魔法润色
                </n-button>
              </div>
              <n-input
                v-model:value="prompt"
                type="textarea"
                placeholder="描述你想生成的画面..."
                :rows="5"
                class="rounded-lg"
              />
            </div>

            <!-- 参考图上传区域 -->
            <div class="border-2 border-red-500 p-2 rounded-lg">
              <label class="block text-sm font-bold text-red-600 mb-2">📸 参考图 (调试中 - 可选)</label>
              <n-upload
                action="/api/upload"
                :max="1"
                list-type="image-card"
                @finish="handleUploadFinish"
                @remove="handleRemove"
              >
                点击上传
              </n-upload>
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">尺寸</label>
                <n-select v-model:value="size" :options="sizeOptions" />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">风格</label>
                <n-select v-model:value="style" :options="styleOptions" />
              </div>
            </div>

            <n-button 
              type="primary" 
              class="w-full mt-4 h-12 text-lg font-medium" 
              :loading="loading"
              :disabled="!prompt"
              @click="handleGenerate"
              color="#f59e0b"
            >
              {{ loading ? '正在绘制中...' : '🚀 开始生成' }}
            </n-button>
            
            <!-- 二次修改区域 -->
            <div v-if="resultUrl && !loading" class="mt-8 pt-6 border-t border-gray-100">
              <h3 class="text-md font-bold text-gray-800 mb-3">🎨 基于结果修改</h3>
              <n-input
                v-model:value="modificationPrompt"
                type="textarea"
                placeholder="例如：给它加上一顶帽子，或者变成夜晚..."
                :rows="3"
                class="rounded-lg mb-3"
              />
              <n-button 
                secondary
                type="info" 
                class="w-full" 
                :loading="modifying"
                :disabled="!modificationPrompt"
                @click="handleModify"
              >
                ✨ 确认修改
              </n-button>
            </div>
          </div>
        </n-card>
      </div>

      <!-- 右侧：预览区 -->
      <div class="bg-white rounded-xl shadow-sm p-2 min-h-[500px] flex items-center justify-center border border-gray-100 relative group">
        
        <div v-if="!resultUrl && !loading" class="text-center text-gray-400">
          <div class="text-6xl mb-4">🎨</div>
          <p>预览区域</p>
        </div>

        <n-spin v-if="loading" size="large">
          <template #description>AI 正在绘图...</template>
        </n-spin>

        <div v-if="resultUrl && !loading" class="relative w-full h-full">
          <img :src="resultUrl" class="w-full h-full object-contain rounded-lg shadow-sm" />
          
          <div class="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
            <n-button secondary circle type="info" @click="openImage(resultUrl)">
              👁️
            </n-button>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { NCard, NInput, NSelect, NButton, NSpin, NUpload, useMessage } from 'naive-ui'
import axios from 'axios'

const message = useMessage()
const loading = ref(false)
const optimizing = ref(false)
const modifying = ref(false)

const prompt = ref('')
const modificationPrompt = ref('')
const resultUrl = ref('')
const refImageUrl = ref('') // 存储参考图URL

const size = ref('1024x1024')
const style = ref('vivid')

const sizeOptions = [
  { label: 'Square (1024x1024)', value: '1024x1024' },
  { label: 'Wide (1792x1024)', value: '1792x1024' },
  { label: 'Tall (1024x1792)', value: '1024x1792' }
]

const styleOptions = [
  { label: 'Vivid (鲜艳)', value: 'vivid' },
  { label: 'Natural (自然)', value: 'natural' }
]

const handleUploadFinish = ({ file, event }) => {
  const res = JSON.parse(event.target.response)
  if (res.success) {
    refImageUrl.value = res.url
    message.success('参考图上传成功')
  } else {
    message.error('上传失败')
  }
}

const handleRemove = () => {
  refImageUrl.value = ''
}

const handleOptimize = async () => {
  if (!prompt.value) return
  optimizing.value = true
  try {
    const res = await axios.post('/api/optimize_prompt', {
      prompt: prompt.value
    })
    if (res.data.success) {
      prompt.value = res.data.optimized_prompt
      message.success('提示词已润色！')
    }
  } catch (err) {
    message.error('润色失败: ' + err.message)
  } finally {
    optimizing.value = false
  }
}

const handleGenerate = async () => {
  if (!prompt.value) return
  
  loading.value = true
  resultUrl.value = '' // clear previous
  modificationPrompt.value = '' // clear mod prompt
  
  try {
    const res = await axios.post('/api/generate/single', {
      prompt: prompt.value,
      size: size.value,
      style: style.value,
      reference_image_url: refImageUrl.value || null
    })
    
    if (res.data.success) {
      resultUrl.value = res.data.url
      message.success('生成成功！')
    }
  } catch (err) {
    message.error('生成失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    loading.value = false
  }
}

const handleModify = async () => {
  if (!modificationPrompt.value || !resultUrl.value) return
  
  modifying.value = true
  // Don't clear resultUrl, just show loading on button or overlay? 
  // User might want to see old image while waiting.
  
  try {
    const res = await axios.post('/api/generate/modify', {
      prompt: modificationPrompt.value,
      original_image_url: resultUrl.value
    })
    
    if (res.data.success) {
      resultUrl.value = res.data.url
      modificationPrompt.value = '' // clear after success
      message.success('修改成功！')
    }
  } catch (err) {
    message.error('修改失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    modifying.value = false
  }
}

const openImage = (url) => {
  window.open(url, '_blank')
}
</script>
