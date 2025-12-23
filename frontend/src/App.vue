<template>
  <n-config-provider :theme="null">
    <n-message-provider>
      <div class="min-h-screen bg-[#f8f9fa] dark:bg-[#111827] text-gray-900 dark:text-gray-100 font-sans selection:bg-yellow-200 selection:text-black">
        
        <!-- 顶部导航栏 -->
        <header class="fixed top-0 left-0 right-0 h-16 bg-white/80 dark:bg-gray-900/80 backdrop-blur-md border-b border-gray-200 dark:border-gray-800 z-50 flex items-center justify-between px-6">
          <div class="flex items-center gap-3">
            <img src="/logo.png" class="h-8 w-auto object-contain brightness-0 dark:brightness-100" />
            <div>
              <h1 class="font-bold text-lg tracking-tight leading-none">Nano Banana</h1>
              <div class="text-[10px] font-bold text-yellow-600 tracking-widest uppercase">Workstation</div>
            </div>
          </div>

          <div class="flex items-center gap-4">
             <div class="flex items-center gap-2 px-3 py-1.5 bg-gray-100 dark:bg-gray-800 rounded-full text-xs font-medium text-gray-500">
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
import { NConfigProvider, NMessageProvider } from 'naive-ui'
import Workstation from './views/Workstation.vue'
</script>

<style>
body {
  overflow-y: scroll;
}
</style>
