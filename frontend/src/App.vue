<template>
  <n-config-provider :theme="null">
    <n-message-provider>
      <div class="min-h-screen bg-[#f8f9fa] dark:bg-[#111827] text-gray-900 dark:text-gray-100 font-sans selection:bg-yellow-200 selection:text-black">
        
        <!-- 顶部导航栏 -->
        <header class="fixed top-0 left-0 right-0 h-16 bg-white/80 dark:bg-gray-900/80 backdrop-blur-md border-b border-gray-200 dark:border-gray-800 z-50 flex items-center justify-between px-6">
          <div class="flex items-center gap-3">
            <img src="/logo.png" class="h-8 w-auto object-contain invert dark:invert-0" />
            <div>
              <h1 class="font-bold text-lg tracking-tight leading-none">ReOpenInnoLab-智绘工坊</h1>
              <div class="text-[10px] font-bold text-yellow-600 tracking-widest uppercase">AI Teaching Assistant</div>
            </div>
          </div>

          <div class="flex items-center gap-4">
             <!-- User Info in Header -->
             <div v-if="authStore.isLoggedIn || authStore.isGuest" class="flex items-center gap-3 bg-gray-100 dark:bg-gray-800 rounded-full pl-1 pr-4 py-1">
                <div class="w-8 h-8 rounded-full bg-gradient-to-tr from-yellow-400 to-orange-500 flex items-center justify-center text-white font-bold text-sm">
                   {{ authStore.user.username.charAt(0).toUpperCase() }}
                </div>
                <div class="flex flex-col text-xs">
                   <span class="font-bold text-gray-900 dark:text-gray-100 leading-none">{{ authStore.user.username }}</span>
                   <span class="text-[10px] text-gray-500 leading-none mt-0.5" v-if="authStore.isGuest">BYOK User</span>
                   <span class="text-[10px] text-gray-500 leading-none mt-0.5" v-else-if="authStore.user.is_pro">PRO User</span>
                   <span class="text-[10px] text-gray-500 leading-none mt-0.5" v-else>Standard</span>
                </div>
             </div>

             <div v-else class="flex items-center gap-2 px-3 py-1.5 bg-gray-100 dark:bg-gray-800 rounded-full text-xs font-medium text-gray-500">
                <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                API Connected
             </div>
          </div>
        </header>

        <!-- 主工作区 -->
        <main class="pt-24 pb-12 px-6 max-w-[1600px] mx-auto">
          <Workstation />
        </main>

      </div>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { onMounted } from 'vue'
import { NConfigProvider, NMessageProvider } from 'naive-ui'
import Workstation from './views/Workstation.vue'
import { useAuthStore } from './stores/auth'

const authStore = useAuthStore()

onMounted(() => {
    authStore.checkAuth()
})
</script>

<style>
body {
  overflow-y: scroll;
}
</style>