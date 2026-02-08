<script setup>
import logoMark from './assets/logo-mark.svg'
import logoType from './assets/logo.png'
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-50 via-[#F8FAFC] to-slate-100 text-slate-800 font-sans">
    <div class="flex min-h-screen">
      <!-- Sidebar -->
      <aside class="w-72 flex flex-col flex-shrink-0 bg-white/70 backdrop-blur-2xl border-r border-white/40 shadow-[4px_0_30px_-10px_rgba(0,0,0,0.03)]">
        <!-- Logo Area (Top-Left) -->
        <div class="py-4 px-6 flex items-center gap-4 relative overflow-hidden shrink-0">
          <div class="absolute top-0 left-0 w-40 h-40 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none -translate-x-1/2 -translate-y-1/4"></div>
          <img :src="logoMark" class="w-12 h-12 object-contain relative z-10" alt="Logo Mark" />
          <div class="flex flex-col gap-1 relative z-10 min-w-0">
            <img :src="logoType" class="h-6 w-auto object-contain opacity-90" alt="Logo Type" />
            <span class="typo-caption-compact text-slate-500">Design System</span>
          </div>
        </div>

        <!-- Nav -->
        <nav class="flex-1 px-4 py-4 space-y-8 overflow-y-auto custom-scrollbar">
          <div>
            <h3 class="px-4 mb-3 typo-label opacity-80">Workspace</h3>
            <div class="space-y-1">
              <button class="w-full flex items-center gap-3 px-4 py-3 rounded-xl typo-button text-indigo-600 bg-white shadow-[0_4px_20px_-4px_rgba(99,102,241,0.15)] ring-1 ring-slate-100/50">
                <span class="icon-sm">✨</span>
                <span>Overview</span>
              </button>
              <button class="w-full flex items-center gap-3 px-4 py-3 rounded-xl typo-button text-slate-500 hover:text-slate-900 hover:bg-white/50 transition-all">
                <span class="icon-sm">🎛️</span>
                <span>Studio</span>
              </button>
            </div>
          </div>
          <div>
            <h3 class="px-4 mb-3 typo-label opacity-80">System</h3>
            <div class="space-y-1">
              <button class="w-full flex items-center gap-3 px-4 py-3 rounded-xl typo-button text-slate-500 hover:text-slate-900 hover:bg-white/50 transition-all">
                <span class="icon-sm">⚙️</span>
                <span>Settings</span>
              </button>
            </div>
          </div>
        </nav>
      </aside>

      <!-- Main -->
      <main class="flex-1 flex flex-col min-w-0">
        <!-- Header -->
        <header class="h-24 flex items-center justify-between px-10">
          <div>
            <p class="typo-page-subtitle">Workspace / Overview</p>
            <h2 class="typo-page-title text-slate-800">Welcome back, Creator</h2>
          </div>
          <button class="px-4 py-2 rounded-xl typo-button text-white bg-gradient-to-r from-blue-500 via-purple-500 to-orange-400 shadow-lg">
            Primary Action
          </button>
        </header>

        <!-- Content -->
        <section class="flex-1 px-10 pb-10">
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-8">
            <div class="lg:col-span-4 bg-white/80 backdrop-blur-xl border border-white/60 rounded-[24px] p-6 shadow-sm">
              <h3 class="typo-section-title mb-4">Left Panel</h3>
              <p class="typo-body mb-4">用于放置表单、选项或控制区。</p>
              <button class="px-4 py-2 rounded-xl typo-button text-white bg-gradient-to-r from-blue-500 via-purple-500 to-orange-400 shadow-lg">
                Save
              </button>
            </div>
            <div class="lg:col-span-8 bg-white/60 backdrop-blur-xl border border-white/60 rounded-[24px] p-6 shadow-sm">
              <h3 class="typo-section-title mb-4">Right Panel</h3>
              <div class="h-64 flex items-center justify-center text-center">
                <div>
                  <div class="icon-hero mb-4">🎨</div>
                  <p class="typo-empty-desc">空状态示例</p>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  </div>
</template>
