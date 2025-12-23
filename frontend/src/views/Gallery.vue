<template>
  <div class="space-y-6">
    <div class="flex justify-between items-center">
      <div>
        <h2 class="text-2xl font-bold text-gray-800">作品画廊</h2>
        <p class="text-gray-500 mt-1">浏览所有生成的杰作</p>
      </div>
      <n-button @click="fetchGallery">🔄 刷新</n-button>
    </div>

    <div v-if="images.length === 0" class="text-center py-20 text-gray-400">
      暂无图片，快去生成一张吧！
    </div>

    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      <div 
        v-for="img in images" 
        :key="img.name" 
        class="group relative aspect-square bg-gray-100 rounded-lg overflow-hidden cursor-pointer"
        @click="openImage(img.url)"
      >
        <img :src="img.url" class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" loading="lazy" />
        
        <div class="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-end p-4">
          <div class="text-white opacity-0 group-hover:opacity-100 transition-opacity text-xs truncate w-full">
            {{ img.name }}
          </div>
        </div>
        
        <div class="absolute top-2 right-2">
          <n-tag size="small" :type="img.type === 'batch' ? 'warning' : 'success'">
            {{ img.type }}
          </n-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { NButton, NTag, useMessage } from 'naive-ui'
import axios from 'axios'

const images = ref([])
const message = useMessage()

const fetchGallery = async () => {
  try {
    const res = await axios.get('/api/gallery')
    images.value = res.data
  } catch (err) {
    message.error('加载画廊失败')
  }
}

const openImage = (url) => {
  window.open(url, '_blank')
}

onMounted(fetchGallery)
</script>
