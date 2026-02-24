<template>
  <n-config-provider :theme="null">
    <n-message-provider>
      <!-- 全局背景增加微弱渐变，提升空间感 -->
      <div class="flex h-screen bg-gradient-to-br from-slate-50 via-[#F8FAFC] to-slate-100 overflow-hidden font-sans text-slate-800 selection:bg-indigo-100 selection:text-indigo-700">
        
        <!-- Sidebar Navigation -->
        <!-- 优化：加宽侧边栏(w-72)，增强毛玻璃模糊度(backdrop-blur-2xl)，添加右侧柔光阴影 -->
        <aside class="w-72 flex flex-col flex-shrink-0 z-30 bg-white/70 backdrop-blur-2xl border-r border-white/40 shadow-[4px_0_30px_-10px_rgba(0,0,0,0.03)] transition-all duration-300">
        
          <!-- Logo Area -->
          <div class="py-2 px-6 flex flex-row items-center gap-4 relative overflow-hidden group shrink-0">
            <!-- 装饰性光斑 -->
            <div class="absolute top-0 left-0 w-40 h-40 bg-indigo-500/10 rounded-full blur-3xl group-hover:bg-indigo-500/20 transition-all duration-500 pointer-events-none -translate-x-1/2 -translate-y-1/4"></div>
            
            <!-- 1. Big Icon (Left) -->
            <img :src="logoMarkUrl" class="w-20 h-20 object-contain shrink-0 relative z-20" alt="Logo Mark" />

            <!-- 2. Text Stack (Right) -->
            <div class="flex flex-col items-start gap-2 relative z-20 min-w-0">
                <h1 class="text-[18px] font-bold tracking-tight text-slate-900 leading-none">
                  <span class="text-blue-500">R</span>e<span class="text-indigo-500">O</span>pen<span class="text-purple-500">I</span>nno<span class="text-orange-400">L</span>ab
                </h1>
                <img
                  :src="schoolLogoUrl"
                  class="h-7 w-auto object-contain invert"
                  alt="School Logo"
                />
            </div>
          </div>
        
          <!-- Nav Menu -->
          <nav class="flex-1 px-4 space-y-8 py-4 overflow-y-auto custom-scrollbar">
             <div v-for="group in menuGroups" :key="group.title" class="animate-slide-up" :style="{ animationDelay: '100ms' }">
                <h3 class="px-4 mb-3 typo-label opacity-80">{{ group.title }}</h3>
                <div class="space-y-1">
                  <button 
                    v-for="item in group.items" 
                    :key="item.id"
                    @click="currentTab = item.id"
                    class="w-full flex items-center gap-3 px-4 py-3 rounded-xl typo-button transition-all duration-300 group relative overflow-hidden"
                    :class="currentTab === item.id 
                      ? 'bg-white text-indigo-600 shadow-[0_4px_20px_-4px_rgba(99,102,241,0.15)] ring-1 ring-slate-100/50 scale-[1.02]' 
                      : 'text-slate-500 hover:text-slate-900 hover:bg-white/50 hover:shadow-sm hover:scale-[1.01]'"
                  >
                    <!-- 激活状态的左侧指示条 -->
                    <div v-if="currentTab === item.id" class="absolute left-0 top-1/2 -translate-y-1/2 w-1.5 h-8 bg-gradient-to-b from-blue-400 via-purple-400 to-orange-300 rounded-r-full shadow-lg shadow-indigo-100"></div>

                    <component :is="item.icon" class="w-5 h-5 transition-transform duration-300 group-hover:scale-110 group-active:scale-95 filter drop-shadow-sm" 
                        :class="currentTab === item.id ? 'text-purple-500' : 'text-slate-400 group-hover:text-slate-600'" />
                    <span :class="currentTab === item.id ? 'bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent font-semibold' : ''">{{ item.label }}</span>
                    <span v-if="item.beta" class="ml-auto px-1.5 py-0.5 bg-gradient-to-r from-purple-400 to-orange-300 text-white typo-badge rounded shadow-sm transform scale-90">Beta</span>
                  </button>
                </div>
             </div>
          </nav>

          <!-- User Footer -->
          <div class="p-6 border-t border-slate-100/50 backdrop-blur-sm bg-white/30 flex flex-col gap-3">
             <div v-if="authStore.isLoggedIn || authStore.isGuest" class="flex items-center gap-3 p-3 rounded-2xl bg-white/60 border border-white/50 shadow-sm hover:shadow-md hover:bg-white transition-all duration-300 cursor-pointer group" @click="authStore.logout()">
                <div class="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white typo-button font-black shadow-md ring-2 ring-white group-hover:scale-105 transition-transform">
                   {{ authStore.user.username.charAt(0).toUpperCase() }}
                </div>
                <div class="flex-1 min-w-0">
                   <p class="typo-inline-label text-slate-800 truncate group-hover:text-indigo-600 transition-colors">{{ authStore.user.username }}</p>
                   <div class="flex items-center gap-1 mt-0.5">
                       <span class="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
                       <p class="typo-caption-compact truncate">
                          {{ authStore.isGuest ? localeStore.t('app.guest') : (authStore.user.is_pro ? localeStore.t('app.pro') : localeStore.t('app.basic')) }}
                       </p>
                   </div>
                </div>
                <div class="p-1.5 rounded-lg text-slate-300 group-hover:text-red-500 group-hover:bg-red-50 transition-all">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
                </div>
             </div>
             <div v-else class="text-center py-2">
                <span class="typo-inline-label text-slate-400 animate-pulse">{{ localeStore.t('app.waiting_connect') }}</span>
             </div>

             <!-- Language Toggle -->
             <button @click="localeStore.toggleLocale()" class="flex items-center justify-center gap-2 py-2 rounded-xl border border-slate-200 bg-white/40 hover:bg-white hover:border-indigo-200 transition-all typo-caption-compact hover:text-indigo-600 group">
                <span class="w-4 h-4 rounded-full bg-slate-100 flex items-center justify-center group-hover:bg-indigo-50 transition-colors">
                    <Globe class="w-3 h-3" />
                </span>
                <span>{{ localeStore.locale === 'zh' ? 'English' : '中文' }}</span>
             </button>
          </div>
        </aside>

        <!-- Main Area -->
        <div class="flex-1 flex flex-col min-w-0 overflow-hidden relative z-10">
           
           <!-- Top Header (Floating Glass) -->
           <header class="h-24 flex items-center justify-between px-10 flex-shrink-0 z-20 transition-all duration-300">
              <div class="flex flex-col justify-center animate-fade-in">
                 <nav class="flex items-center gap-2 typo-page-subtitle mb-1">
                    <span class="hover:text-slate-700 transition-colors cursor-default">{{ localeStore.t('app.workspace') }}</span>
                    <span class="text-slate-300">/</span>
                    <span class="text-slate-900">{{ currentTabLabel }}</span>
                 </nav>
                 <h2 class="typo-page-title text-slate-800 drop-shadow-sm">
                    {{ getGreeting }}, <span class="text-indigo-600">{{ authStore.user.username || '创造者' }}</span>
                 </h2>
              </div>

              <div class="flex items-center gap-6">
                 <!-- Quota Widget -->
                 <div v-if="authStore.isLoggedIn || authStore.isGuest" class="animate-fade-in group hover:-translate-y-0.5 transition-transform duration-300">
                     <div class="flex items-center gap-5 bg-white/80 backdrop-blur-md px-6 py-3 rounded-2xl shadow-[0_4px_20px_-8px_rgba(0,0,0,0.05)] border border-white/60 hover:shadow-lg hover:border-indigo-100 transition-all">
                        <div class="text-right">
                           <p class="typo-label-compact mb-0.5">{{ localeStore.t('app.quota_weekly') }}</p>
                           <p class="typo-card-title font-mono leading-none">
                              <span :class="{'text-orange-500': authStore.user.quota_remaining < 5}">{{ authStore.user.quota_remaining }}</span>
                              <span class="typo-body text-slate-300 mx-1">/</span>
                              <span class="typo-body text-slate-400">{{ authStore.user.quota_limit }}</span>
                           </p>
                        </div>
                        <div class="w-10 h-10 rounded-full bg-slate-50 border border-slate-100 flex items-center justify-center icon-sm shadow-inner group-hover:scale-110 transition-transform">
                            ⚡️
                        </div>
                     </div>
                 </div>
              </div>
           </header>

           <!-- Scrollable Content -->
           <main class="flex-1 overflow-y-auto px-10 pb-10 custom-scrollbar">
              <!-- 使用 TransitionGroup 实现页面切换动画 -->
              <Transition name="page-fade" mode="out-in">
                  <div :key="currentTab" class="h-full">
                      <Workstation v-if="currentTab !== 'audio' && currentTab !== 'video'" :active-tab="currentTab" @update-tab="currentTab = $event" />
                      <AudioStudio v-else-if="currentTab === 'audio'" />
                      <VideoStudio v-else />
                  </div>
              </Transition>
           </main>
        </div>

      </div>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { NConfigProvider, NMessageProvider } from 'naive-ui'
import { Sparkles, Music, Zap, Image as ImageIcon, Settings, Globe, Video } from 'lucide-vue-next'
import Workstation from './views/Workstation.vue'
import AudioStudio from './views/AudioStudio.vue'
import VideoStudio from './components/VideoStudio.vue'
import { useAuthStore } from './stores/auth'
import { useLocaleStore } from './stores/locale'
import logoMarkUrl from './assets/logo-mark.png'

const schoolLogoUrl = '/logo.png'

const authStore = useAuthStore()
const localeStore = useLocaleStore()
const currentTab = ref('single')

const menuGroups = computed(() => [
  {
    title: localeStore.t('menu.creation_suite'),
    items: [
      { id: 'single', label: localeStore.t('menu.image_studio'), icon: Sparkles },
      { id: 'video', label: localeStore.t('menu.video_studio'), icon: Video, beta: true },
      { id: 'audio', label: localeStore.t('menu.audio_studio'), icon: Music, beta: true },
      { id: 'batch', label: localeStore.t('menu.batch_factory'), icon: Zap }
    ]
  },
  {
    title: localeStore.t('menu.assets'),
    items: [
      { id: 'gallery', label: localeStore.t('menu.gallery'), icon: ImageIcon },
    ]
  },
  {
    title: localeStore.t('menu.system'),
    items: [
      { id: 'settings', label: localeStore.t('menu.settings'), icon: Settings },
    ]
  }
])

const currentTabLabel = computed(() => {
  for (const group of menuGroups.value) {
    const item = group.items.find(i => i.id === currentTab.value)
    if (item) return item.label
  }
  return localeStore.t('app.dashboard')
})

const getGreeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 12) return localeStore.t('app.greeting_morning')
  if (hour < 18) return localeStore.t('app.greeting_afternoon')
  return localeStore.t('app.greeting_evening')
})

onMounted(() => {
    authStore.checkAuth()
})
</script>

<style>
/* Reusable styles */
.input-code {
  @apply w-full px-3 py-2 bg-white border border-slate-200 rounded-lg text-[11px] font-mono text-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all placeholder-slate-300;
}

/* 页面切换动画 */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: all 0.3s ease-out;
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
