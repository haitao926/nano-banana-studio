<template>
  <div class="space-y-8 h-full flex flex-col">

    <!-- Login Modal (Glassmorphism + Scale Animation) -->
    <Transition name="fade">
      <div v-if="!authStore.isLoggedIn && !authStore.isGuest" class="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/40 backdrop-blur-md transition-all duration-500">
        <div class="bg-white/90 backdrop-blur-xl rounded-[32px] shadow-2xl p-10 w-full max-w-md border border-white/60 animate-scale-in relative overflow-hidden">
          <!-- Decorative Background Blob -->
          <div class="absolute -top-20 -right-20 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"></div>
          
          <div class="text-center mb-10 relative z-10">
            <h2 class="typo-modal-title mb-3 tracking-tight">Welcome Back</h2>
            <p class="typo-page-subtitle">Unlock your creative potential</p>
          </div>
          
          <div class="space-y-5 relative z-10">
             <div class="space-y-4">
                <input v-model="loginForm.username" type="text" class="w-full px-6 py-4 bg-slate-50/50 border-2 border-slate-100 rounded-2xl typo-input font-semibold text-slate-900 focus:outline-none focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-500/10 transition-all" placeholder="Username" @keyup.enter="handleAuthAction" />
                <input v-model="loginForm.password" type="password" class="w-full px-6 py-4 bg-slate-50/50 border-2 border-slate-100 rounded-2xl typo-input font-semibold text-slate-900 focus:outline-none focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-500/10 transition-all" placeholder="Password" @keyup.enter="handleAuthAction" />
             </div>
             
             <button @click="handleAuthAction" class="w-full py-4 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white rounded-2xl typo-button shadow-lg shadow-indigo-500/30 hover:shadow-indigo-500/40 hover:-translate-y-0.5 active:scale-95 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed group" :disabled="authLoading">
               <span v-if="authLoading" class="inline-block animate-spin mr-2">⟳</span>
               {{ authLoading ? 'Verifying...' : 'Sign In' }}
             </button>
             
             <div class="flex items-center gap-4 my-2">
                <div class="h-px bg-slate-200 flex-1"></div>
                <span class="typo-label-compact text-slate-300">or</span>
                <div class="h-px bg-slate-200 flex-1"></div>
             </div>
             
             <button @click="handleGuestAccess" class="w-full py-3 text-slate-500 typo-button font-bold hover:text-indigo-600 hover:bg-slate-50 rounded-2xl transition-colors">
               Continue as Guest
             </button>
          </div>
        </div>
      </div>
    </Transition>

    <div v-if="authStore.isLoggedIn || authStore.isGuest" class="h-full flex flex-col">
      
      <!-- TAB: SINGLE IMAGE STUDIO -->
      <!-- 使用 grid 布局，左侧控制台，右侧预览 -->
      <Transition name="fade" mode="out-in">
        <div v-if="activeTab === 'single'" class="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch">
           
           <!-- Controls (Left) -->
           <div class="lg:col-span-4 flex flex-col gap-6 h-full min-h-0 animate-slide-up">
              <!-- Parameter Card -->
              <div class="bg-white/80 backdrop-blur-xl border border-white/60 rounded-[24px] p-6 shadow-sm flex flex-col shrink-0 relative group hover:shadow-md transition-shadow duration-300">
                  <div class="flex items-center justify-between mb-6">
                     <h3 class="typo-section-title flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full bg-indigo-500"></span> {{ localeStore.t('image.configuration') }}
                     </h3>
                     <button @click="resetSettings" class="typo-label-compact hover:text-indigo-600 px-2 py-1 rounded-lg hover:bg-indigo-50 transition-colors">{{ localeStore.t('image.reset') }}</button>
                  </div>

                  <div class="grid grid-cols-2 gap-4">
                     <!-- Custom Selectors -->
                     <div class="space-y-1.5">
                        <label class="typo-label pl-1">{{ tSettings('settings.image_provider', '绘图厂商') }}</label>
                        <n-popselect v-model:value="settings.imageProvider" :options="imageProviderOptions" trigger="click">
                           <button class="w-full text-left px-4 py-3 bg-slate-50/50 border border-slate-200 hover:border-indigo-400 hover:bg-white rounded-xl typo-input font-sans transition-all shadow-sm flex items-center justify-between group-hover:shadow-indigo-500/5">
                              <span class="truncate">{{ getImageProviderLabel(settings.imageProvider) }}</span>
                              <span class="typo-caption-compact text-slate-300">▼</span>
                           </button>
                        </n-popselect>
                     </div>
                     <div class="space-y-1.5">
                        <label class="typo-label pl-1">{{ localeStore.t('image.subject') }}</label>
                        <n-popselect v-model:value="settings.subject" :options="subjectOptions" trigger="click">
                           <button class="w-full text-left px-4 py-3 bg-slate-50/50 border border-slate-200 hover:border-indigo-400 hover:bg-white rounded-xl typo-input font-sans transition-all shadow-sm flex items-center justify-between group-hover:shadow-indigo-500/5">
                              <span class="truncate">{{ getSubjectLabel(settings.subject) }}</span>
                              <span class="typo-caption-compact text-slate-300">▼</span>
                           </button>
                        </n-popselect>
                     </div>
                     <div class="space-y-1.5">
                        <label class="typo-label pl-1">{{ localeStore.t('image.ratio') }}</label>
                        <n-popselect v-model:value="settings.aspectRatio" :options="ratioOptions" trigger="click">
                           <button class="w-full text-left px-4 py-3 bg-slate-50/50 border border-slate-200 hover:border-indigo-400 hover:bg-white rounded-xl typo-input-mono transition-all shadow-sm flex items-center justify-between group-hover:shadow-indigo-500/5">
                              <span>{{ ratioOptions.find(o => o.value === settings.aspectRatio)?.label }}</span>
                              <span class="typo-caption-compact text-slate-300">▼</span>
                           </button>
                        </n-popselect>
                     </div>
                     <div class="space-y-1.5">
                        <label class="typo-label pl-1">{{ localeStore.t('image.quality') }}</label>
                        <n-popselect v-model:value="settings.quality" :options="qualityOptions" trigger="click">
                           <button class="w-full text-left px-4 py-3 bg-slate-50/50 border border-slate-200 hover:border-indigo-400 hover:bg-white rounded-xl typo-input font-sans transition-all shadow-sm flex items-center justify-between group-hover:shadow-indigo-500/5">
                              <span>{{ qualityOptions.find(o => o.value === settings.quality)?.label }}</span>
                              <span class="typo-caption-compact text-slate-300">▼</span>
                           </button>
                        </n-popselect>
                     </div>
                     <div v-if="isSeedreamGroupModel" class="col-span-2 space-y-2 bg-slate-50/60 border border-slate-100 rounded-xl p-4">
                        <div class="flex items-center justify-between">
                           <label class="typo-label">{{ tSettings('settings.seedream_group', 'Seedream 组图') }}</label>
                           <label class="flex items-center gap-2 text-xs text-slate-600">
                              <input type="checkbox" v-model="settings.seedreamGroup" class="rounded text-indigo-600 focus:ring-indigo-500" />
                              {{ tSettings('settings.seedream_group_enable', '启用组图') }}
                           </label>
                        </div>
                        <div class="flex items-center gap-3">
                           <span class="text-[11px] text-slate-400">{{ tSettings('settings.seedream_max_images', '最大张数') }}</span>
                           <input v-model.number="settings.seedreamMaxImages" type="number" min="1" max="15" :disabled="!settings.seedreamGroup" class="w-20 px-2 py-1 bg-white border border-slate-200 rounded-lg text-xs text-slate-700 focus:outline-none focus:border-indigo-500 disabled:opacity-60 disabled:cursor-not-allowed" />
                           <span class="text-[10px] text-slate-400">{{ tSettings('settings.seedream_max_images_hint', '最多 15（含参考图）') }}</span>
                        </div>
                     </div>
                  </div>
              </div>

              <!-- Input Card (The Console) -->
              <div class="flex-1 bg-white/80 backdrop-blur-xl border border-white/60 rounded-[24px] p-6 shadow-sm flex flex-col relative group hover:shadow-md transition-shadow duration-300 min-h-0">
                  <div class="flex justify-between items-center mb-4 shrink-0">
                    <h3 class="typo-section-title flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full bg-purple-500"></span> {{ localeStore.t('image.prompt_label') }}
                     </h3>
                    <button @click="handleOptimizePrompt" class="typo-button-compact text-indigo-600 bg-indigo-50 hover:bg-indigo-100 px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 border border-indigo-100" :disabled="optimizing || !inputText.trim()">
                       <Wand2 class="w-3 h-3" />
                       {{ localeStore.t('image.ai_enhance') }}
                    </button>
                 </div>

                 <div class="relative flex-1 flex flex-col min-h-0">
                    <!-- Integrated Prompt Box -->
                    <div class="flex-1 flex flex-col bg-slate-50/50 border-2 border-slate-100 focus-within:bg-white focus-within:border-indigo-500 focus-within:ring-4 focus-within:ring-indigo-500/10 rounded-xl transition-all shadow-inner overflow-hidden group/box">
                        
                        <!-- Textarea -->
                        <textarea 
                            v-model="inputText" 
                            class="w-full flex-1 p-4 bg-transparent border-none outline-none resize-none typo-prompt font-sans placeholder-slate-400 min-h-[100px]"
                            :placeholder="localeStore.t('image.prompt_placeholder')"
                            @keydown.enter.ctrl="handleGenerateSingle"
                        ></textarea>

                        <!-- Attachments Preview -->
                        <div v-if="refImageUrls.length > 0" class="px-4 pb-2 flex gap-2 overflow-x-auto custom-scrollbar">
                             <div v-for="(url, idx) in refImageUrls" :key="idx" class="relative w-12 h-12 flex-shrink-0 rounded-lg overflow-hidden border border-slate-200 group/img cursor-pointer">
                                <img :src="url" class="w-full h-full object-cover" />
                                <div class="absolute inset-0 bg-black/50 opacity-0 group-hover/img:opacity-100 transition-all flex items-center justify-center">
                                    <button @click="refImageUrls = refImageUrls.filter(u => u !== url)" class="text-white hover:text-red-400 typo-button-compact">×</button>
                                </div>
                             </div>
                        </div>

                        <!-- Bottom Toolbar -->
                        <div class="px-3 py-2 border-t border-slate-100/50 flex items-center justify-between bg-white/50">
                            <div class="flex items-center gap-2">
                                 <!-- Reference Upload Trigger (Prominent) -->
                                 <n-upload v-if="refImageUrls.length < 4" :action="uploadAction" :max="4" multiple :show-file-list="false" @finish="handleUploadFinishWithStore">
                                    <button class="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 border border-indigo-200 rounded-lg transition-all shadow-sm hover:shadow flex items-center gap-2 group/btn active:scale-95" :title="localeStore.t('image.add_ref')">
                                        <ImageIcon class="w-4 h-4" />
                                        <span class="text-xs font-bold">{{ localeStore.t('image.add_ref_short') || '上传参考图' }}</span>
                                    </button>
                                 </n-upload>
                                 
                                 <!-- Counter / Divider -->
                                 <div v-if="refImageUrls.length > 0" class="flex items-center gap-2 animate-fade-in">
                                     <div class="h-4 w-px bg-slate-200"></div>
                                     <span class="text-xs text-slate-400 font-medium">{{ refImageUrls.length }} / 4</span>
                                 </div>
                            </div>
                            
                            <!-- Char Count -->
                            <div class="text-xs text-slate-300 font-mono group-focus-within/box:text-slate-400 transition-colors">
                                {{ inputText.length }} chars
                            </div>
                        </div>
                    </div>
                 </div>

                 <button @click="handleGenerateSingle" :disabled="!inputText.trim() || processing || !settings.model" class="w-full mt-4 py-4 bg-gradient-to-r from-blue-500 via-purple-500 to-orange-400 hover:from-blue-400 hover:to-orange-300 text-white rounded-xl typo-button shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40 hover:-translate-y-0.5 active:translate-y-0 active:scale-95 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shrink-0 overflow-hidden relative group/btn">
                     <span class="relative z-10 flex items-center justify-center gap-2">
                        <span v-if="processing" class="animate-spin">⟳</span>
                        {{ processing ? localeStore.t('image.generating') : localeStore.t('image.generate') }}
                     </span>
                     <!-- Button Shine Effect -->
                     <div class="absolute inset-0 -translate-x-full group-hover/btn:translate-x-full transition-transform duration-700 bg-gradient-to-r from-transparent via-white/20 to-transparent skew-x-12"></div>
                  </button>
              </div>
           </div>
           
           <!-- Right: Preview (Viewport) -->
           <div class="lg:col-span-8 h-full min-h-0 animate-scale-in" style="animation-delay: 100ms;">
               <div class="h-full bg-white/60 backdrop-blur-xl rounded-[32px] border border-white/60 p-2 flex flex-col gap-4 shadow-xl shadow-slate-200/50 relative overflow-hidden">
                  
                  <!-- Screen Area -->
                  <div class="flex-1 bg-slate-100/50 rounded-[24px] border border-white/50 relative overflow-hidden group flex flex-col shadow-inner">
                      <!-- Grid Pattern Background -->
                      <div class="absolute inset-0 opacity-40 pointer-events-none" style="background-image: linear-gradient(#cbd5e1 1px, transparent 1px), linear-gradient(90deg, #cbd5e1 1px, transparent 1px); background-size: 40px 40px;"></div>
                      
                      <!-- Empty State -->
                      <div v-if="!currentDisplayImage && !processing" class="text-center relative z-10 animate-fade-in m-auto">
                          <div class="w-24 h-24 bg-white rounded-full flex items-center justify-center mx-auto mb-6 shadow-[0_8px_30px_rgba(0,0,0,0.04)] ring-4 ring-white/50">
                              <ImageIcon class="w-10 h-10 text-slate-300" />
                          </div>
                          <h3 class="typo-empty-title mb-2">{{ localeStore.t('image.ready_title') }}</h3>
                          <p class="typo-empty-desc max-w-xs mx-auto">{{ localeStore.t('image.ready_desc') }}</p>
                      </div>

                      <!-- Loading State (Shimmer) -->
                      <div v-if="processing" class="absolute inset-0 z-20 bg-white/80 backdrop-blur-sm flex flex-col items-center justify-center">
                          <div class="w-64 h-64 rounded-2xl bg-gradient-to-r from-slate-200 via-slate-100 to-slate-200 animate-shimmer relative overflow-hidden shadow-2xl">
                              <div class="absolute inset-0 flex items-center justify-center text-indigo-500/20">
                                  <Bot class="w-24 h-24" />
                              </div>
                          </div>
                          <p class="mt-6 typo-label text-indigo-600 animate-pulse">{{ localeStore.t('image.rendering') }}</p>
                      </div>

                      <!-- Result Image -->
                      <div v-if="currentDisplayImage && !processing" class="relative w-full h-full flex flex-col min-h-0 animate-scale-in">
                          <!-- Image Display Area -->
                          <div class="flex-1 flex items-center justify-center p-4 min-h-0 overflow-hidden relative">
                              <div class="relative group/img max-w-full max-h-full shadow-2xl rounded-lg overflow-hidden transition-transform duration-500 hover:scale-[1.01]">
                                  <img :src="currentDisplayImage.url" class="max-w-full max-h-full object-contain" @click="openImage(currentDisplayImage)" />
                                  
                                  <!-- Image Actions Overlay -->
                                  <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-6 opacity-0 group-hover/img:opacity-100 transition-opacity duration-300 flex justify-between items-end">
                                      <div class="text-white flex-1 min-w-0 mr-4">
                                          <p class="typo-label-compact text-white/80 mb-1">{{ getSubjectLabel(currentDisplayImage.subject) }}</p>
                                          <p class="typo-body font-bold text-white line-clamp-1" :title="currentDisplayImage.prompt">{{ currentDisplayImage.prompt }}</p>
                                      </div>
                                      <div class="flex gap-2 items-center shrink-0">
                                          <button @click.stop="handleDownload" class="bg-white text-slate-900 p-2 rounded-lg typo-button-compact hover:bg-indigo-500 hover:text-white transition-colors shadow-lg" :title="localeStore.t('image.download') || 'Download'">
                                              <Download class="w-4 h-4" />
                                          </button>
                                          <button @click.stop="handleRedraw" class="bg-white text-slate-900 p-2 rounded-lg typo-button-compact hover:bg-indigo-500 hover:text-white transition-colors shadow-lg" :title="localeStore.t('image.redraw') || 'Redraw'">
                                              <RefreshCw class="w-4 h-4" />
                                          </button>
                                          <button @click.stop="jumpToVideo(currentDisplayImage)" class="bg-white text-slate-900 p-2 rounded-lg typo-button-compact hover:bg-indigo-500 hover:text-white transition-colors shadow-lg" :title="localeStore.t('image.to_video') || 'Generate Video'">
                                              <Video class="w-4 h-4" />
                                          </button>
                                          <button @click="openImage(currentDisplayImage)" class="bg-white text-slate-900 p-2 rounded-lg typo-button-compact hover:bg-indigo-500 hover:text-white transition-colors shadow-lg" :title="localeStore.t('image.view_details')">
                                              <Maximize2 class="w-4 h-4" />
                                          </button>
                                      </div>
                                  </div>
                              </div>
                          </div>
                          
                          <!-- Quick Refine Bar -->
                          <div class="p-4 bg-white/40 border-t border-white/50 backdrop-blur-md flex gap-3 items-center shrink-0 z-20">
                              <div class="flex-1 relative group/input">
                                  <input 
                                      v-model="quickRefineText" 
                                      @keydown.enter="handleQuickRefine" 
                                      :placeholder="localeStore.t('image.quick_refine_placeholder') || '快速修改 (默认使用 Gemini Pro 重绘)...'" 
                                      class="w-full px-4 py-2.5 rounded-xl bg-white/60 border border-white/60 focus:bg-white focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/10 outline-none transition-all shadow-sm text-sm placeholder-slate-400" 
                                  />
                                  <div class="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400 font-mono pointer-events-none opacity-0 group-focus-within/input:opacity-100 transition-opacity">Enter ↵</div>
                              </div>
                              <button @click="handleQuickRefine" :disabled="!quickRefineText.trim()" class="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl typo-button-compact shadow-md hover:shadow-lg hover:-translate-y-0.5 active:translate-y-0 active:scale-95 transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
                                  <Zap class="w-4 h-4" />
                                  <span>{{ localeStore.t('image.redraw') || '重绘' }}</span>
                              </button>
                          </div>
                      </div>
                  </div>

                  <!-- History Rail (Floating - Moved to Top) -->
                  <div v-if="recentHistory.length" class="absolute top-6 left-1/2 -translate-x-1/2 h-16 bg-white/90 backdrop-blur-md rounded-2xl border border-white/50 p-2 shadow-[0_8px_30px_rgba(0,0,0,0.12)] flex items-center gap-3 overflow-x-auto custom-scrollbar z-30 max-w-[90%] animate-slide-down">
                       <div v-for="img in recentHistory" :key="img.id" @click="handleHistorySelect(img)" 
                            class="h-12 w-12 flex-shrink-0 rounded-xl overflow-hidden cursor-pointer transition-all duration-300 relative group"
                            :class="currentDisplayImage?.id === img.id ? 'ring-2 ring-indigo-500 ring-offset-2 scale-110' : 'opacity-60 hover:opacity-100 hover:scale-105'">
                            <img :src="img.thumbnail_url || img.url" class="w-full h-full object-cover" />
                       </div>
                  </div>
               </div>
           </div>
        </div>
      </Transition>

      <!-- TAB: BATCH FACTORY -->
      <Transition name="fade" mode="out-in">
        <div v-if="activeTab === 'batch'" class="space-y-5 animate-fade-in">
            <!-- Batch Header -->
            <div class="bg-gradient-to-r from-indigo-600 to-purple-700 rounded-2xl p-4 shadow-lg shadow-indigo-500/20 text-white">
                <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
                    <div class="flex items-center gap-3 min-w-0">
                        <span class="bg-white/20 p-1.5 rounded-lg backdrop-blur-sm shrink-0">
                            <Zap class="w-5 h-5 text-white" />
                        </span>
                        <h3 class="typo-card-title text-white shrink-0">{{ localeStore.t('batch.title') }}</h3>
                        <p class="typo-caption-compact text-indigo-100 truncate">{{ localeStore.t('batch.desc') }}</p>
                    </div>
                    <div class="flex flex-wrap gap-2 lg:justify-end">
                       <button @click="downloadTemplate" class="px-3 py-1.5 bg-white/10 hover:bg-white/20 backdrop-blur-md rounded-lg typo-button-compact transition-all border border-white/10">{{ localeStore.t('batch.download_template') }}</button>
                       <label class="px-3 py-1.5 bg-white text-indigo-600 hover:bg-indigo-50 rounded-lg typo-button-compact transition-all cursor-pointer shadow-md hover:shadow-lg border border-white">
                          {{ localeStore.t('batch.import_json') }} <input type="file" accept=".json" class="hidden" @change="handleJsonUpload" />
                       </label>
                    </div>
                </div>
            </div>

            <!-- Unified Design Format -->
            <div class="bg-white/80 backdrop-blur-md border border-white/60 rounded-2xl p-6 shadow-sm">
                <div class="flex flex-wrap items-center justify-between gap-4">
                    <div>
                        <h3 class="typo-card-title">{{ localeStore.t('batch.format_title') }}</h3>
                        <p class="typo-caption-compact text-slate-400">{{ localeStore.t('batch.format_desc') }}</p>
                    </div>
                    <div class="flex items-center gap-2 bg-slate-100 p-1 rounded-xl">
                        <button v-for="opt in batchTypeOptions" :key="opt.value" @click="batchType = opt.value" class="px-4 py-2 rounded-lg typo-button-compact transition-all" :class="batchType === opt.value ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'">
                            {{ opt.label }}
                        </button>
                    </div>
                </div>

                <div v-if="batchType === 'image'" class="grid grid-cols-1 md:grid-cols-4 gap-4 mt-6">
                    <div class="space-y-1.5">
                        <label class="typo-label pl-1">{{ tSettings('settings.image_provider', '绘图厂商') }}</label>
                        <n-popselect v-model:value="batchDefaults.image.imageProvider" :options="imageProviderOptions" trigger="click">
                           <button class="w-full text-left px-4 py-3 bg-slate-50 border border-slate-200 hover:border-indigo-400 rounded-xl typo-input font-sans transition-all shadow-sm flex items-center justify-between">
                              <span class="truncate">{{ getImageProviderLabel(batchDefaults.image.imageProvider) }}</span>
                              <span class="typo-caption-compact text-slate-300">▼</span>
                           </button>
                        </n-popselect>
                    </div>
                    <div class="space-y-1.5">
                        <label class="typo-label pl-1">{{ localeStore.t('image.ratio') }}</label>
                        <n-popselect v-model:value="batchDefaults.image.aspectRatio" :options="ratioOptions" trigger="click">
                           <button class="w-full text-left px-4 py-3 bg-slate-50 border border-slate-200 hover:border-indigo-400 rounded-xl typo-input-mono transition-all shadow-sm flex items-center justify-between">
                              <span>{{ ratioOptions.find(o => o.value === batchDefaults.image.aspectRatio)?.label }}</span>
                              <span class="typo-caption-compact text-slate-300">▼</span>
                           </button>
                        </n-popselect>
                    </div>
                    <div class="space-y-1.5">
                        <label class="typo-label pl-1">{{ localeStore.t('image.quality') }}</label>
                        <n-popselect v-model:value="batchDefaults.image.quality" :options="qualityOptions" trigger="click">
                           <button class="w-full text-left px-4 py-3 bg-slate-50 border border-slate-200 hover:border-indigo-400 rounded-xl typo-input transition-all shadow-sm flex items-center justify-between">
                              <span>{{ qualityOptions.find(o => o.value === batchDefaults.image.quality)?.label }}</span>
                              <span class="typo-caption-compact text-slate-300">▼</span>
                           </button>
                        </n-popselect>
                    </div>
                    <div class="space-y-1.5">
                        <label class="typo-label pl-1">{{ localeStore.t('image.subject') }}</label>
                        <n-popselect v-model:value="batchDefaults.image.subject" :options="subjectOptions" trigger="click">
                           <button class="w-full text-left px-4 py-3 bg-slate-50 border border-slate-200 hover:border-indigo-400 rounded-xl typo-input transition-all shadow-sm flex items-center justify-between">
                              <span class="truncate">{{ getSubjectLabel(batchDefaults.image.subject) }}</span>
                              <span class="typo-caption-compact text-slate-300">▼</span>
                           </button>
                        </n-popselect>
                    </div>
                    <div class="md:col-span-4">
                        <label class="flex items-center gap-2 typo-button-compact text-indigo-600 bg-indigo-50 px-3 py-1.5 rounded-lg cursor-pointer hover:bg-indigo-100 transition-colors">
                            <input type="checkbox" v-model="batchDefaults.image.optimize" class="accent-indigo-500" />
                            {{ localeStore.t('batch.prompt_optimize') }}
                        </label>
                    </div>
                    <div v-if="isBatchSeedreamGroupModel" class="md:col-span-4">
                        <div class="space-y-2 bg-slate-50 border border-slate-100 rounded-xl p-4">
                            <div class="flex items-center justify-between">
                                <label class="typo-label">{{ tSettings('settings.seedream_group', 'Seedream 组图') }}</label>
                                <label class="flex items-center gap-2 text-xs text-slate-600">
                                    <input type="checkbox" v-model="batchDefaults.image.seedreamGroup" class="rounded text-indigo-600 focus:ring-indigo-500" />
                                    {{ tSettings('settings.seedream_group_enable', '启用组图') }}
                                </label>
                            </div>
                            <div class="flex items-center gap-3">
                                <span class="text-[11px] text-slate-400">{{ tSettings('settings.seedream_max_images', '最大张数') }}</span>
                                <input v-model.number="batchDefaults.image.seedreamMaxImages" type="number" min="1" max="15" :disabled="!batchDefaults.image.seedreamGroup" class="w-20 px-2 py-1 bg-white border border-slate-200 rounded-lg text-xs text-slate-700 focus:outline-none focus:border-indigo-500 disabled:opacity-60 disabled:cursor-not-allowed" />
                                <span class="text-[10px] text-slate-400">{{ tSettings('settings.seedream_max_images_hint', '最多 15（含参考图）') }}</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div v-if="batchType === 'video'" class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
                    <div class="space-y-1.5 md:col-span-3">
                        <label class="typo-label pl-1">{{ localeStore.t('video.mode') }}</label>
                        <div class="bg-slate-50 p-1 rounded-xl flex gap-1 border border-slate-100">
                            <button @click="batchDefaults.video.mode = 'text'" class="flex-1 py-2 rounded-lg typo-button-compact transition-all" :class="batchDefaults.video.mode === 'text' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'">
                                {{ localeStore.t('video.text_mode') }}
                            </button>
                            <button @click="batchDefaults.video.mode = 'image'" class="flex-1 py-2 rounded-lg typo-button-compact transition-all" :class="batchDefaults.video.mode === 'image' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'">
                                {{ localeStore.t('video.image_mode') }}
                            </button>
                        </div>
                    </div>
                    <div class="space-y-1.5">
                        <label class="typo-label pl-1">{{ localeStore.t('video.model') }}</label>
                        <select v-model="batchDefaults.video.model" :disabled="!batchVideoModelOptions.length" class="w-full px-4 py-3 bg-slate-50 border border-slate-200 hover:border-indigo-400 rounded-xl typo-input font-sans outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed">
                            <option v-if="!batchVideoModelOptions.length" value="" disabled>{{ tSettings('settings.model_empty_hint', '请先配置模型') }}</option>
                            <option v-for="option in batchVideoModelOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                        </select>
                        <p v-if="batchDefaults.video.model" class="text-xs text-slate-400">{{ batchVideoCostHint }}</p>
                    </div>
                    <div class="space-y-1.5">
                        <label class="typo-label pl-1">{{ localeStore.t('video.ratio') }}</label>
                        <select v-model="batchDefaults.video.aspectRatio" class="w-full px-4 py-3 bg-slate-50 border border-slate-200 hover:border-indigo-400 rounded-xl typo-input font-sans outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all shadow-sm">
                            <option value="16:9">16:9</option>
                            <option value="9:16">9:16</option>
                        </select>
                    </div>
                    <div class="space-y-1.5">
                        <label class="typo-label pl-1">{{ localeStore.t('video.duration') }}</label>
                        <select v-model.number="batchDefaults.video.durationSeconds" class="w-full px-4 py-3 bg-slate-50 border border-slate-200 hover:border-indigo-400 rounded-xl typo-input font-sans outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all shadow-sm">
                            <option :value="4">4s</option>
                            <option :value="6">6s</option>
                            <option :value="8">8s</option>
                        </select>
                    </div>
                    <div class="space-y-1.5">
                        <label class="typo-label pl-1">{{ localeStore.t('video.resolution') }}</label>
                        <select v-model="batchDefaults.video.resolution" class="w-full px-4 py-3 bg-slate-50 border border-slate-200 hover:border-indigo-400 rounded-xl typo-input font-sans outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all shadow-sm">
                            <option value="720p">720p</option>
                            <option value="1080p">1080p</option>
                            <option value="4k">4k</option>
                        </select>
                    </div>
                    <div v-if="batchVideoRequiresImage" class="md:col-span-2 space-y-2">
                        <label class="typo-label pl-1">{{ localeStore.t('video.image_source') }}</label>
                        <div v-if="batchDefaults.video.imageUrl" class="relative w-full h-32 rounded-xl overflow-hidden border border-slate-200 bg-slate-50">
                            <img :src="batchDefaults.video.imageUrl" class="w-full h-full object-cover" />
                            <button @click="batchDefaults.video.imageUrl = ''" class="absolute top-2 right-2 bg-white/80 text-slate-600 hover:text-red-500 rounded-full w-7 h-7 flex items-center justify-center shadow">×</button>
                        </div>
                        <n-upload v-else :action="uploadAction" :max="1" accept="image/*" :show-file-list="false" @finish="handleBatchVideoImageUpload">
                            <div class="w-full h-32 rounded-xl border-2 border-dashed border-indigo-200 bg-indigo-50 hover:bg-indigo-100 hover:border-indigo-400 flex items-center justify-center text-indigo-500 transition-all cursor-pointer">
                                <span class="typo-button-compact">{{ localeStore.t('video.upload_image') }}</span>
                            </div>
                        </n-upload>
                    </div>
                </div>

                <div v-if="showAudioSettings" class="grid grid-cols-1 md:grid-cols-3 gap-3 mt-5">
                    <div class="space-y-1.5">
                        <label class="typo-label pl-1">{{ localeStore.t('batch.audio_model') }}</label>
                        <select v-model="batchDefaults.audio.model" :disabled="!ttsModelOptions.length" class="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 hover:border-indigo-400 rounded-xl typo-input font-sans outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed">
                            <option v-if="!ttsModelOptions.length" value="" disabled>{{ tSettings('settings.model_empty_hint', '请先配置模型') }}</option>
                            <option v-for="option in ttsModelOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                        </select>
                    </div>
                    <div class="space-y-1.5">
                        <label class="typo-label pl-1">{{ localeStore.t('batch.audio_voice') }}</label>
                        <select v-model="batchDefaults.audio.voice" class="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 hover:border-indigo-400 rounded-xl typo-input font-sans outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all shadow-sm">
                            <option v-for="option in voiceOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                        </select>
                    </div>
                    <div class="space-y-1.5 md:col-span-3">
                        <div class="flex items-center justify-between">
                            <label class="typo-label pl-1">{{ localeStore.t('batch.audio_instructions') }}</label>
                            <label class="flex items-center gap-1.5 typo-button-compact text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded cursor-pointer hover:bg-indigo-100 transition-colors">
                                <input type="checkbox" v-model="batchDefaults.audio.optimize_instructions" class="accent-indigo-500" />
                                {{ localeStore.t('batch.audio_optimize') }}
                            </label>
                        </div>
                        <textarea v-model="batchDefaults.audio.instructions" :class="batchType === 'digital_human' ? 'h-14' : 'h-20'" class="w-full p-3 bg-white border border-slate-200 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 rounded-xl typo-input transition-all outline-none resize-none leading-relaxed shadow-sm" :placeholder="localeStore.t('audio.instruction_placeholder')"></textarea>
                    </div>
                </div>

                <div v-if="batchType === 'digital_human'" class="mt-5 space-y-2">
                    <div class="flex items-center justify-between px-1">
                        <span class="typo-label">{{ tSettings('settings.model_service_dh', '数字人') }}</span>
                        <span class="typo-caption-compact text-slate-400">{{ localeStore.t('batch.dh_audio_hint') }}</span>
                    </div>
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
                        <div class="rounded-2xl border border-slate-200 bg-slate-50/70 p-3 space-y-3">
                            <div class="typo-label pl-1">{{ localeStore.t('batch.audio_model') }}</div>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                                <div class="space-y-1.5">
                                    <label class="typo-label pl-1">{{ localeStore.t('batch.audio_model') }}</label>
                                    <select v-model="batchDefaults.audio.model" :disabled="!ttsModelOptions.length" class="w-full px-3 py-2.5 bg-white border border-slate-200 hover:border-indigo-400 rounded-xl typo-input font-sans outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed">
                                        <option v-if="!ttsModelOptions.length" value="" disabled>{{ tSettings('settings.model_empty_hint', '请先配置模型') }}</option>
                                        <option v-for="option in ttsModelOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                                    </select>
                                </div>
                                <div class="space-y-1.5">
                                    <label class="typo-label pl-1">{{ localeStore.t('batch.audio_voice') }}</label>
                                    <select v-model="batchDefaults.audio.voice" class="w-full px-3 py-2.5 bg-white border border-slate-200 hover:border-indigo-400 rounded-xl typo-input font-sans outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all shadow-sm">
                                        <option v-for="option in voiceOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                                    </select>
                                </div>
                            </div>
                            <div class="space-y-1.5">
                                <div class="flex items-center justify-between">
                                    <label class="typo-label pl-1">{{ localeStore.t('batch.audio_instructions') }}</label>
                                    <label class="flex items-center gap-1.5 typo-button-compact text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded cursor-pointer hover:bg-indigo-100 transition-colors">
                                        <input type="checkbox" v-model="batchDefaults.audio.optimize_instructions" class="accent-indigo-500" />
                                        {{ localeStore.t('batch.audio_optimize') }}
                                    </label>
                                </div>
                                <textarea v-model="batchDefaults.audio.instructions" class="w-full h-14 p-3 bg-white border border-slate-200 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 rounded-xl typo-input transition-all outline-none resize-none leading-relaxed shadow-sm" :placeholder="localeStore.t('audio.instruction_placeholder')"></textarea>
                            </div>
                        </div>

                        <div class="rounded-2xl border border-slate-200 bg-slate-50/70 p-3">
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                                <div class="space-y-2 md:col-span-1">
                                    <label class="typo-label pl-1">{{ localeStore.t('batch.avatar_upload') }}</label>
                                    <div v-if="batchDefaults.digital_human.avatarUrl" class="relative w-full h-28 rounded-xl overflow-hidden border border-slate-200 bg-slate-50">
                                        <img :src="batchDefaults.digital_human.avatarUrl" class="w-full h-full object-cover" />
                                        <button @click="batchDefaults.digital_human.avatarUrl = ''" class="absolute top-2 right-2 bg-white/80 text-slate-600 hover:text-red-500 rounded-full w-7 h-7 flex items-center justify-center shadow">×</button>
                                    </div>
                                    <n-upload v-else :action="uploadAction" :max="1" accept="image/*" :show-file-list="false" @finish="handleBatchAvatarUpload">
                                        <div class="w-full h-28 rounded-xl border-2 border-dashed border-indigo-200 bg-white hover:bg-indigo-50 hover:border-indigo-400 flex items-center justify-center text-indigo-500 transition-all cursor-pointer">
                                            <span class="typo-button-compact">{{ localeStore.t('batch.avatar_upload') }}</span>
                                        </div>
                                    </n-upload>
                                </div>
                                <div class="md:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-3">
                                    <div class="space-y-1.5">
                                        <label class="typo-label pl-1">{{ localeStore.t('batch.dh_provider') }}</label>
                                        <select v-model="batchDefaults.digital_human.provider" class="w-full px-3 py-2.5 bg-white border border-slate-200 hover:border-indigo-400 rounded-xl typo-input font-sans outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all shadow-sm">
                                            <option v-for="option in digitalHumanProviderOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                                        </select>
                                    </div>
                                    <div class="space-y-1.5">
                                        <label class="typo-label pl-1">{{ localeStore.t('batch.dh_resolution') }}</label>
                                        <select v-model="batchDefaults.digital_human.resolution" class="w-full px-3 py-2.5 bg-white border border-slate-200 hover:border-indigo-400 rounded-xl typo-input font-sans outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all shadow-sm">
                                            <option v-for="option in digitalHumanResolutionOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                                        </select>
                                    </div>
                                    <div class="space-y-1.5 md:col-span-2">
                                        <label class="typo-label pl-1">{{ tSettings('settings.model_service_dh', '数字人') }}</label>
                                        <select v-model="batchDefaults.digital_human.model" :disabled="!digitalHumanModelOptions.length" class="w-full px-3 py-2.5 bg-white border border-slate-200 hover:border-indigo-400 rounded-xl typo-input font-sans outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed">
                                            <option v-if="!digitalHumanModelOptions.length" value="" disabled>{{ tSettings('settings.model_empty_hint', '请先配置模型') }}</option>
                                            <option v-for="option in digitalHumanModelOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                                        </select>
                                    </div>
                                    <div class="space-y-1.5">
                                        <label class="typo-label pl-1">{{ localeStore.t('batch.dh_style') }}</label>
                                        <select v-model="batchDefaults.digital_human.style" class="w-full px-3 py-2.5 bg-white border border-slate-200 hover:border-indigo-400 rounded-xl typo-input font-sans outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all shadow-sm">
                                            <option v-for="option in digitalHumanStyleOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="text-[11px] text-slate-500 px-1">
                        当前为单头像模式；请在任务中填写 `digital_human.avatarUrl`（完整 URL、`/static/uploads/...` 或文件名）。
                    </div>
                </div>
            </div>

            <!-- Queue List -->
            <div v-if="batchQueue.length" class="space-y-6">
                <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 px-4">
                    <h3 class="typo-card-title flex items-center gap-3">
                        {{ localeStore.t('batch.task_queue') }} <span class="bg-slate-200 text-slate-600 px-3 py-1 rounded-full typo-badge">{{ batchQueue.length }}</span>
                    </h3>
                    <div class="flex gap-3 bg-white p-1.5 rounded-xl border border-slate-200 shadow-sm">
                        <button v-if="hasPending && !batchRunning" @click="startBatchProcessing" class="px-4 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg typo-button-compact shadow-sm hover:-translate-y-0.5 transition-all">{{ localeStore.t('batch.start_all') }}</button>
                        <button v-if="batchRunning" @click="pauseBatchProcessing" class="px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg typo-button-compact shadow-sm">{{ localeStore.t('batch.pause') }}</button>
                        <button @click="downloadBatchResults" class="px-4 py-2 hover:bg-slate-100 text-slate-700 rounded-lg typo-button-compact transition-colors disabled:opacity-60 disabled:cursor-not-allowed" :disabled="!hasDownloadable || batchDownloading">
                            {{ batchDownloading ? '打包中...' : localeStore.t('batch.download_results') }}
                        </button>
                        <div class="w-px bg-slate-200 my-1"></div>
                        <button @click="batchQueue = []" class="px-4 py-2 text-red-500 hover:bg-red-50 rounded-lg typo-button-compact transition-colors">{{ localeStore.t('batch.clear') }}</button>
                    </div>
                </div>
                <div class="px-4 grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div class="rounded-xl border border-slate-200 bg-white px-3 py-2">
                        <div class="text-[11px] text-slate-400">{{ localeStore.t('batch.status_pending') }}</div>
                        <div class="text-sm font-semibold text-orange-500">{{ pendingCount }}</div>
                    </div>
                    <div class="rounded-xl border border-slate-200 bg-white px-3 py-2">
                        <div class="text-[11px] text-slate-400">{{ localeStore.t('batch.status_generating') }}</div>
                        <div class="text-sm font-semibold text-indigo-500">{{ processingCount }}</div>
                    </div>
                    <div class="rounded-xl border border-slate-200 bg-white px-3 py-2">
                        <div class="text-[11px] text-slate-400">{{ localeStore.t('batch.status_done') }}</div>
                        <div class="text-sm font-semibold text-emerald-500">{{ doneCount }}</div>
                    </div>
                    <div class="rounded-xl border border-slate-200 bg-white px-3 py-2">
                        <div class="text-[11px] text-slate-400">{{ localeStore.t('batch.status_failed') }}</div>
                        <div class="text-sm font-semibold text-red-500">{{ failedCount }}</div>
                    </div>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-4 gap-6">
                    <TransitionGroup name="list">
                        <div v-for="task in reversedBatchQueue" :key="task.id" class="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm hover:shadow-xl transition-all duration-300 group hover:-translate-y-1">
                            <div class="aspect-video bg-slate-50 relative border-b border-slate-100 group-hover:border-indigo-100 transition-colors">
                                 <span class="absolute top-2 left-2 px-2 py-1 bg-white/80 text-slate-600 rounded-full typo-badge shadow-sm">{{ getBatchTypeLabel(task.type) }}</span>
                                 <template v-if="task.status === 'done' && task.resultUrl">
                                     <img v-if="task.resultType === 'image'" :src="task.resultUrl" class="w-full h-full object-cover cursor-pointer transition-transform duration-700 group-hover:scale-110" @click="openBatchImage(task)" />
                                     <div v-else-if="task.resultType === 'audio'" class="absolute inset-0 flex items-center justify-center p-4">
                                         <audio :src="task.resultUrl" controls class="w-full" />
                                     </div>
                                     <div v-else-if="task.resultType === 'video'" class="absolute inset-0 flex items-center justify-center">
                                         <video :src="task.resultUrl" controls class="w-full h-full object-cover"></video>
                                     </div>
                                     <div v-else class="absolute inset-0 flex items-center justify-center">
                                         <span class="typo-badge text-emerald-600 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-100 shadow-sm">{{ localeStore.t('batch.status_done') }}</span>
                                     </div>
                                 </template>
                                 <div v-else class="absolute inset-0 flex flex-col items-center justify-center gap-3">
                                     <span v-if="task.status === 'pending'" class="typo-badge text-orange-500 bg-orange-50 px-3 py-1 rounded-full border border-orange-100 shadow-sm">{{ localeStore.t('batch.status_pending') }}</span>
                                     <span v-else-if="task.status === 'processing'" class="typo-badge text-indigo-500 bg-indigo-50 px-3 py-1 rounded-full border border-indigo-100 animate-pulse shadow-sm">{{ localeStore.t('batch.status_generating') }}</span>
                                     <span v-else-if="task.status === 'failed'" class="typo-badge text-red-500 bg-red-50 px-3 py-1 rounded-full border border-red-100 shadow-sm">{{ localeStore.t('batch.status_failed') }}</span>
                                     <span v-else class="typo-badge text-slate-400 bg-slate-100 px-3 py-1 rounded-full border border-slate-200">{{ localeStore.t('batch.status_draft') }}</span>
                                     <span v-if="task.status === 'processing' && getBatchPhaseLabel(task)" class="text-[11px] text-slate-500 bg-white/80 px-2 py-1 rounded-md border border-slate-200">
                                        {{ getBatchPhaseLabel(task) }}
                                     </span>
                                 </div>
                            </div>
                            <div class="p-5">
                                <p class="typo-caption-compact text-slate-600 line-clamp-2 mb-4 leading-relaxed font-mono bg-slate-50 p-2 rounded-lg" :title="task.prompt">{{ task.prompt }}</p>
                                <p v-if="task.optimizedPrompt" class="typo-caption-compact text-indigo-500 line-clamp-2 mb-3" :title="task.optimizedPrompt">{{ localeStore.t('batch.prompt_optimized') }}: {{ task.optimizedPrompt }}</p>
                                <div class="flex flex-wrap gap-2">
                                    <span v-for="tag in getBatchTags(task)" :key="tag" class="px-2 py-1 bg-white border border-slate-200 rounded-md typo-caption-compact font-bold text-slate-500 shadow-sm">{{ tag }}</span>
                                </div>
                                <p v-if="task.optimizationError" class="typo-caption-compact text-amber-500 line-clamp-2 mb-2">{{ task.optimizationError }}</p>
                                <p v-if="task.status === 'failed' && task.error" class="mt-3 typo-caption-compact text-red-500 line-clamp-2">{{ task.error }}</p>
                            </div>
                        </div>
                    </TransitionGroup>
                </div>
            </div>
        </div>
      </Transition>

      <!-- TAB: DIGITAL HUMAN -->
      <Transition name="fade" mode="out-in">
        <div v-if="activeTab === 'digital_human'" class="animate-fade-in">
             <DigitalHumanPanel />
        </div>
      </Transition>

      <!-- TAB: GALLERY -->
      <Transition name="fade" mode="out-in">
        <div v-if="activeTab === 'gallery'" class="space-y-8 animate-fade-in">
             <!-- Gallery Filter Bar -->
             <div class="bg-white/80 backdrop-blur-md border border-white/60 rounded-2xl p-4 shadow-sm flex flex-col md:flex-row justify-between items-center gap-4 sticky top-0 z-10">
                 <div class="flex gap-2 overflow-x-auto pb-1 custom-scrollbar w-full md:w-auto">
                     <button @click="galleryFilter = 'all'" class="px-5 py-2.5 rounded-xl typo-button-compact transition-all shadow-sm" :class="galleryFilter === 'all' ? 'bg-slate-900 text-white shadow-md scale-105' : 'bg-white border border-slate-200 text-slate-500 hover:bg-slate-50'">{{ localeStore.t('gallery.all') }}</button>
                     <button v-for="sub in subjectOptions" :key="sub.value" @click="galleryFilter = sub.value" class="px-5 py-2.5 rounded-xl typo-button-compact transition-all whitespace-nowrap shadow-sm" :class="galleryFilter === sub.value ? 'bg-indigo-600 text-white shadow-md scale-105' : 'bg-white border border-slate-200 text-slate-500 hover:bg-slate-50'">{{ sub.label }}</button>
                 </div>
                 <div class="flex gap-6 border-t md:border-t-0 md:border-l border-slate-200 pt-4 md:pt-0 md:pl-6 w-full md:w-auto justify-end">
                     <label class="typo-inline-label flex items-center gap-2 cursor-pointer hover:text-indigo-600 transition-colors select-none">
                         <input type="checkbox" v-model="showMyImages" class="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 border-slate-300 transition-all"> 
                         {{ localeStore.t('gallery.my_creations') }}
                     </label>
                     <label class="typo-inline-label flex items-center gap-2 cursor-pointer hover:text-indigo-600 transition-colors select-none">
                         <input type="checkbox" v-model="showFeaturedOnly" class="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 border-slate-300 transition-all"> 
                         {{ localeStore.t('gallery.featured') }}
                     </label>
                 </div>
             </div>
             
             <!-- Masonry-like Grid -->
             <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-6">
                 <TransitionGroup name="list">
                     <div v-for="img in filteredGallery" :key="img.id" class="bg-white rounded-2xl overflow-hidden border border-slate-100 shadow-sm hover:shadow-2xl transition-all duration-500 hover:-translate-y-2 cursor-pointer group relative aspect-square" @click="openImage(img)">
                         <img :src="img.thumbnail_url || img.url" class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" />
                         <div class="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent opacity-0 group-hover:opacity-100 transition-all duration-300 flex flex-col justify-end p-5">
                             <div class="transform translate-y-4 group-hover:translate-y-0 transition-transform duration-300 delay-75">
                                 <p class="text-white typo-button-compact line-clamp-2 mb-2">{{ img.prompt }}</p>
                                 <span class="inline-block px-2 py-0.5 bg-white/20 backdrop-blur-md rounded typo-caption-compact font-bold text-white border border-white/20">{{ getSubjectLabel(img.subject) }}</span>
                             </div>
                         </div>
                         <button @click.stop="jumpToVideo(img)" class="absolute bottom-3 right-3 bg-white/90 text-slate-800 p-2 rounded-lg shadow-lg opacity-0 group-hover:opacity-100 transition-all hover:bg-indigo-500 hover:text-white" :title="localeStore.t('image.to_video') || '生成视频'">
                             <Video class="w-4 h-4" />
                         </button>
                         <span v-if="img.is_mine" class="absolute top-3 left-3 px-2 py-1 bg-indigo-600/90 backdrop-blur text-white typo-badge rounded-lg shadow-lg">ME</span>
                     </div>
                 </TransitionGroup>
             </div>
             <div v-if="!filteredGallery.length" class="h-96 flex flex-col items-center justify-center text-slate-300 border-2 border-dashed border-slate-200 rounded-3xl bg-slate-50/50">
                 <ImageIcon class="w-16 h-16 mb-4 opacity-50" />
                 <p class="typo-empty-title text-slate-300">{{ localeStore.t('gallery.no_data') }}</p>
                 <button @click="activeTab = 'single'" class="mt-4 typo-inline-label text-indigo-600 hover:underline">{{ localeStore.t('gallery.create_now') }}</button>
             </div>
        </div>
      </Transition>
      
      <!-- TAB: SETTINGS -->
      <Transition name="fade" mode="out-in">
        <div v-if="activeTab === 'settings'" class="max-w-[1400px] w-full mx-auto space-y-8 animate-fade-in">
            <div class="bg-white/80 backdrop-blur-xl border border-white/60 rounded-[20px] p-3 shadow-sm">
                <div class="flex flex-wrap gap-2">
                    <button
                        v-for="tab in settingsTabs"
                        :key="tab.id"
                        @click="activeSettingsTab = tab.id"
                        class="px-4 py-2 rounded-xl typo-button-compact transition-all border"
                        :class="activeSettingsTab === tab.id ? 'bg-slate-900 text-white border-slate-900 shadow' : 'bg-white/70 text-slate-500 border-white/70 hover:bg-white hover:text-slate-700'"
                    >
                        {{ tab.label }}
                    </button>
                </div>
            </div>
            <div class="space-y-8">
                <div v-if="activeSettingsTab === 'user'" class="space-y-6">
                    <div class="bg-white/80 backdrop-blur-xl border border-white/60 rounded-[24px] p-8 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300 space-y-4">
                        <div class="flex items-center justify-between gap-4 flex-wrap">
                            <div class="flex items-center gap-4">
                                <div class="w-12 h-12 rounded-2xl bg-gradient-to-br from-indigo-50 to-purple-50 border border-white/70 shadow-inner flex items-center justify-center icon-md">🔑</div>
                                <div>
                                    <h3 class="typo-card-title">{{ tSettings('settings.key_pools_title', '账号池') }}</h3>
                                    <p class="typo-page-subtitle">{{ tSettings('settings.user_tip_desc', '在此配置个人 Key（支持阿里百炼 / 火山方舟等），仅当前浏览器生效；保存后优先使用你的 Key。') }}</p>
                                </div>
                            </div>
                            <div class="flex items-center gap-2">
                                <button @click="addUserKeyPool" class="typo-button-compact text-indigo-600 bg-white/70 border border-white/70 px-3 py-1.5 rounded-lg shadow-sm hover:bg-white hover:text-indigo-700 transition-all">
                                    {{ tSettings('settings.key_pool_add', '添加') }}
                                </button>
                                <button @click="reorderUserKeyPools" class="typo-button-compact text-slate-600 bg-white/70 border border-white/70 px-3 py-1.5 rounded-lg shadow-sm hover:bg-white hover:text-slate-700 transition-all">
                                    {{ tSettings('settings.key_pool_sort', '按优先级重排') }}
                                </button>
                                <button @click="handleSaveUserPools" class="typo-button-compact text-white bg-slate-900 px-3 py-1.5 rounded-lg shadow-sm hover:bg-black transition-all">
                                    {{ tSettings('settings.save', '保存') }}
                                </button>
                            </div>
                        </div>
                        <div v-if="userPoolsDirty" class="text-xs text-amber-500">{{ tSettings('settings.unsaved_hint', '有未保存的更改') }}</div>
                        <div class="space-y-4 max-h-[70vh] overflow-y-auto custom-scrollbar pr-2">
                            <div v-if="!userKeyPools.length" class="text-xs text-slate-400">{{ tSettings('settings.key_pool_empty', '暂无账号池配置') }}</div>
                            <div v-for="(pool, idx) in userKeyPools" :key="idx" class="p-4 rounded-2xl border border-slate-100 bg-white/80 space-y-3 shadow-sm">
                                <div class="flex items-center justify-between gap-3">
                                    <div class="flex items-center gap-3 text-xs text-slate-400">
                                        <span>#{{ idx + 1 }}</span>
                                        <span class="px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-500 border border-indigo-100 text-[10px]">{{ tSettings('settings.tag_personal', '个人') }}</span>
                                        <span class="text-slate-500">{{ poolSummary(pool) }}</span>
                                    </div>
                                    <div class="flex items-center gap-2 text-xs">
                                        <button @click="moveUserKeyPool(idx, -1)" class="text-slate-500 hover:text-slate-700">{{ tSettings('settings.key_pool_up', '上移') }}</button>
                                        <button @click="moveUserKeyPool(idx, 1)" class="text-slate-500 hover:text-slate-700">{{ tSettings('settings.key_pool_down', '下移') }}</button>
                                        <button @click="toggleUserPoolExpand(idx)" class="text-indigo-500 hover:text-indigo-700">
                                            {{ expandedUserPools.has(idx) ? tSettings('settings.key_pool_collapse', '收起') : tSettings('settings.key_pool_expand', '展开') }}
                                        </button>
                                        <button @click="removeUserKeyPool(idx)" class="text-red-400 hover:text-red-600">{{ tSettings('settings.key_pool_remove', '删除') }}</button>
                                    </div>
                                </div>
                                <div v-if="expandedUserPools.has(idx)" class="space-y-3">
                                    <div class="grid grid-cols-1 lg:grid-cols-7 gap-3">
                                        <div class="space-y-1">
                                            <label class="text-[11px] text-slate-500">{{ tSettings('settings.key_pool_service_label', '用途（单选）') }}</label>
                                            <select v-model="pool.service" class="w-full px-3 py-2 bg-white border border-slate-100 rounded-xl text-xs text-slate-700 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all" @change="handleUserServiceChange(pool)">
                                                <option value="image">{{ tSettings('settings.key_pool_service_image', '绘图') }}</option>
                                                <option value="audio">{{ tSettings('settings.key_pool_service_audio', '音频') }}</option>
                                                <option value="video">{{ tSettings('settings.key_pool_service_video', '视频/数字人') }}</option>
                                                <option value="digital_human">{{ tSettings('settings.key_pool_service_dh', '数字人') }}</option>
                                                <option value="prompt">{{ tSettings('settings.key_pool_service_prompt', '提示词优化') }}</option>
                                            </select>
                                        </div>
                                        <div class="space-y-1 lg:col-span-2">
                                            <label class="text-[11px] text-slate-500">{{ tSettings('settings.model_id', '模型') }}</label>
                                            <input
                                                v-model="pool.models"
                                                :list="`user-model-options-${idx}`"
                                                class="w-full px-3 py-2 bg-white border border-slate-100 rounded-xl text-xs text-slate-700 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all"
                                                :placeholder="tSettings('settings.key_pool_models_hint', '支持输入自定义模型 ID，多个用逗号分隔')"
                                            />
                                            <datalist :id="`user-model-options-${idx}`">
                                                <option v-for="opt in getUserModelOptionsForService(pool.service)" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                                            </datalist>
                                        </div>
                                        <div class="space-y-1 lg:col-span-3">
                                            <label class="text-[11px] text-slate-500">{{ tSettings('settings.key_pool_key', 'API 密钥') }}</label>
                                            <input v-model="pool.key" type="password" class="w-full px-3 py-2 bg-white border border-slate-100 rounded-xl text-xs text-slate-700 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all" placeholder="sk-***" />
                                        </div>
                                        <div class="space-y-1 lg:col-span-1">
                                            <label class="text-[11px] text-slate-500">{{ tSettings('settings.key_pool_enabled', '启用') }}</label>
                                            <label class="flex items-center gap-2 text-xs text-slate-600 mt-2">
                                                <input type="checkbox" v-model="pool.enabled" class="rounded text-indigo-600 focus:ring-indigo-500" />
                                                {{ tSettings('settings.key_pool_enabled', '启用') }}
                                            </label>
                                        </div>
                                    </div>
                                    <div class="grid grid-cols-1 lg:grid-cols-6 gap-3 pt-2">
                                        <div class="space-y-1">
                                            <label class="text-[11px] text-slate-500">{{ tSettings('settings.key_pool_provider_label', '通道/厂商（可选）') }}</label>
                                            <select v-model="pool.provider" class="w-full px-3 py-2 bg-white border border-slate-100 rounded-xl text-xs text-slate-700 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all" @change="handleUserProviderChange(pool)">
                                                <option value="">{{ tSettings('settings.key_pool_provider_any', '不限') }}</option>
                                                <option value="vector">{{ tSettings('settings.key_pool_provider_vector', 'ReOpenInnoLab') }}</option>
                                                <option value="bailian">{{ tSettings('settings.key_pool_provider_bailian', '百炼') }}</option>
                                                <option value="ark">{{ tSettings('settings.key_pool_provider_ark', '火山方舟') }}</option>
                                            </select>
                                        </div>
                                        <div class="space-y-1 lg:col-span-3">
                                            <label class="text-[11px] text-slate-500">{{ tSettings('settings.key_pool_base_url', '接口地址（可选）') }}</label>
                                            <input v-model="pool.base_url" type="text" class="w-full px-3 py-2 bg-white border border-slate-100 rounded-xl text-xs text-slate-700 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all" :placeholder="tSettings('settings.base_url_placeholder', '可选，例如 https://api.xxx.com')" />
                                        </div>
                                    </div>
                                </div>
                                <div v-else class="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                                    <span class="px-2 py-0.5 rounded-full bg-slate-50 border border-slate-200">
                                        {{ isPoolCompleted(pool) ? tSettings('settings.key_pool_configured', 'Key 已配置') : tSettings('settings.key_pool_not_configured', 'Key 未配置') }}
                                    </span>
                                    <span v-if="pool.base_url" class="px-2 py-0.5 rounded-full bg-slate-50 border border-slate-200 max-w-full truncate">
                                        {{ pool.base_url }}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div v-if="authStore.user.username === 'admin' && activeSettingsTab === 'models'" class="space-y-6">
                <div class="bg-white/80 backdrop-blur-xl border border-white/60 rounded-[24px] p-8 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300 space-y-5">
                    <div class="flex justify-between items-center gap-4 flex-wrap pb-4 border-b border-slate-100/70">
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 rounded-2xl bg-gradient-to-br from-indigo-50 to-cyan-50 border border-white/70 shadow-inner flex items-center justify-center icon-md">🔐</div>
                            <div>
                                <h3 class="typo-card-title">{{ tSettings('settings.system_pool_title', '系统账号池') }}</h3>
                                <p class="typo-page-subtitle">{{ tSettings('settings.system_key_pools_desc', '按用途配置系统 Key 池，运行时按优先级自动回退。') }}</p>
                            </div>
                        </div>
                        <div class="flex items-center gap-2">
                            <button @click="addKeyPool" class="typo-button-compact text-indigo-600 bg-white/70 border border-white/70 px-3 py-1.5 rounded-lg shadow-sm hover:bg-white hover:text-indigo-700 transition-all">
                                {{ tSettings('settings.key_pool_add', '添加') }}
                            </button>
                            <button @click="reorderKeyPools" class="typo-button-compact text-slate-600 bg-white/70 border border-white/70 px-3 py-1.5 rounded-lg shadow-sm hover:bg-white hover:text-slate-700 transition-all">
                                {{ tSettings('settings.key_pool_sort', '按优先级重排') }}
                            </button>
                            <button @click="fetchSystemConfig" class="typo-button-compact text-slate-600 bg-white/70 border border-white/70 px-3 py-1.5 rounded-lg shadow-sm hover:bg-white hover:text-slate-700 transition-all">
                                {{ localeStore.t('settings.refresh') }}
                            </button>
                        </div>
                    </div>

                    <div class="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                        <span class="px-2.5 py-1 rounded-full bg-slate-50 border border-slate-200">
                            {{ tSettings('settings.system_pool_total', '总池数') }}: {{ systemPoolStats.total }}
                        </span>
                        <span class="px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-100 text-emerald-700">
                            {{ tSettings('settings.system_pool_enabled', '已启用') }}: {{ systemPoolStats.enabled }}
                        </span>
                        <span class="px-2.5 py-1 rounded-full bg-amber-50 border border-amber-100 text-amber-700">
                            {{ tSettings('settings.system_pool_unconfigured', '未配置 Key') }}: {{ systemPoolStats.unconfigured }}
                        </span>
                        <span v-if="systemConfigDirty" class="text-amber-500">{{ tSettings('settings.unsaved_hint', '有未保存的更改') }}</span>
                    </div>

                    <div class="flex flex-wrap gap-2">
                        <button
                            v-for="group in systemPoolServiceGroups"
                            :key="`system-pool-${group.id}`"
                            @click="activeSystemPoolService = group.id"
                            class="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border"
                            :class="activeSystemPoolService === group.id ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm' : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300 hover:text-indigo-600'"
                        >
                            {{ group.label }}
                        </button>
                    </div>

                    <div class="space-y-3 max-h-[48vh] overflow-y-auto custom-scrollbar pr-2">
                        <div v-if="!filteredSystemKeyPools.length" class="text-xs text-slate-400 p-3 rounded-xl border border-dashed border-slate-200 bg-slate-50/60">
                            {{ tSettings('settings.system_pool_filtered_empty', '当前用途暂无账号池，请点击“添加”创建。') }}
                        </div>
                        <div v-for="entry in filteredSystemKeyPools" :key="`system-pool-${entry.index}`" class="p-4 rounded-2xl border border-slate-100 bg-white/80 space-y-3 shadow-sm">
                            <div class="flex items-center justify-between gap-3">
                                <div class="flex items-center gap-3 text-xs text-slate-400 min-w-0">
                                    <span>#{{ entry.index + 1 }}</span>
                                    <span class="px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-600 border border-indigo-100 text-[10px]">
                                        {{ tSettings('settings.pool_tag', '系统') }}
                                    </span>
                                    <span class="text-slate-500 truncate">{{ poolSummary(entry.item) }}</span>
                                </div>
                                <div class="flex items-center gap-2 text-xs">
                                    <button @click="moveKeyPool(entry.index, -1)" class="text-slate-500 hover:text-slate-700">{{ tSettings('settings.key_pool_up', '上移') }}</button>
                                    <button @click="moveKeyPool(entry.index, 1)" class="text-slate-500 hover:text-slate-700">{{ tSettings('settings.key_pool_down', '下移') }}</button>
                                    <button @click="duplicateKeyPool(entry.index)" class="text-indigo-500 hover:text-indigo-700">{{ tSettings('settings.key_pool_copy', '复制') }}</button>
                                    <button @click="togglePoolExpand(entry.index)" class="text-indigo-500 hover:text-indigo-700">
                                        {{ expandedPools.has(entry.index) ? tSettings('settings.key_pool_collapse', '收起') : tSettings('settings.key_pool_expand', '展开') }}
                                    </button>
                                    <button @click="removeKeyPool(entry.index)" class="text-red-400 hover:text-red-600">{{ tSettings('settings.key_pool_remove', '删除') }}</button>
                                </div>
                            </div>

                            <div v-if="!expandedPools.has(entry.index)" class="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                                <span class="px-2 py-0.5 rounded-full bg-slate-50 border border-slate-200">
                                    {{ isPoolCompleted(entry.item) ? tSettings('settings.key_pool_configured', 'Key 已配置') : tSettings('settings.key_pool_not_configured', 'Key 未配置') }}
                                </span>
                                <span class="px-2 py-0.5 rounded-full bg-slate-50 border border-slate-200">
                                    {{ tSettings('settings.key_pool_backup_count', '备用 Key') }}: {{ poolBackupKeyCount(entry.item) }}
                                </span>
                                <span v-if="entry.item.base_url" class="px-2 py-0.5 rounded-full bg-slate-50 border border-slate-200 max-w-full truncate">
                                    {{ entry.item.base_url }}
                                </span>
                            </div>

                            <div v-else class="space-y-3">
                                <div class="grid grid-cols-1 lg:grid-cols-8 gap-3">
                                    <div class="space-y-1">
                                        <label class="text-[11px] text-slate-500">{{ tSettings('settings.key_pool_service_label', '用途（单选）') }}</label>
                                        <select v-model="entry.item.service" class="w-full px-3 py-2 bg-white border border-slate-100 rounded-xl text-xs text-slate-700 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all">
                                            <option value="image">{{ tSettings('settings.key_pool_service_image', '绘图') }}</option>
                                            <option value="prompt">{{ tSettings('settings.key_pool_service_prompt', '提示词优化') }}</option>
                                            <option value="audio">{{ tSettings('settings.key_pool_service_audio', '音频') }}</option>
                                            <option value="video">{{ tSettings('settings.model_service_video', '视频') }}</option>
                                            <option value="digital_human">{{ tSettings('settings.key_pool_service_dh', '数字人') }}</option>
                                        </select>
                                    </div>
                                    <div class="space-y-1">
                                        <label class="text-[11px] text-slate-500">{{ tSettings('settings.key_pool_provider_label', '通道/厂商（可选）') }}</label>
                                        <select v-model="entry.item.provider" class="w-full px-3 py-2 bg-white border border-slate-100 rounded-xl text-xs text-slate-700 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all" @change="handleSystemPoolProviderChange(entry.item)">
                                            <option value="">{{ tSettings('settings.key_pool_provider_any', '不限') }}</option>
                                            <option value="vector">{{ tSettings('settings.key_pool_provider_vector', 'ReOpenInnoLab') }}</option>
                                            <option value="bailian">{{ tSettings('settings.key_pool_provider_bailian', '百炼') }}</option>
                                            <option value="ark">{{ tSettings('settings.key_pool_provider_ark', '火山方舟') }}</option>
                                            <option value="openai">{{ tSettings('settings.key_pool_provider_openai', 'GPT / OpenAI') }}</option>
                                            <option value="gemini">{{ tSettings('settings.key_pool_provider_gemini', 'Gemini') }}</option>
                                            <option value="other">{{ tSettings('settings.key_pool_provider_other', '其他') }}</option>
                                        </select>
                                    </div>
                                    <div class="space-y-1 lg:col-span-2">
                                        <label class="text-[11px] text-slate-500">{{ tSettings('settings.model_id', '模型') }}</label>
                                        <input
                                            v-model="entry.item.models"
                                            :list="`system-pool-model-options-${entry.index}`"
                                            class="w-full px-3 py-2 bg-white border border-slate-100 rounded-xl text-xs text-slate-700 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all"
                                            :placeholder="tSettings('settings.key_pool_models_hint', '支持输入自定义模型 ID，多个用逗号分隔')"
                                        />
                                        <datalist :id="`system-pool-model-options-${entry.index}`">
                                            <option v-for="opt in getUserModelOptionsForService(entry.item.service)" :key="`pool-${entry.index}-${opt.value}`" :value="opt.value">{{ opt.label }}</option>
                                        </datalist>
                                    </div>
                                    <div class="space-y-1 lg:col-span-3">
                                        <label class="text-[11px] text-slate-500">{{ tSettings('settings.key_pool_key', 'API 密钥') }}</label>
                                        <input v-model="entry.item.key" type="password" class="w-full px-3 py-2 bg-white border border-slate-100 rounded-xl text-xs text-slate-700 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all" placeholder="sk-***" />
                                    </div>
                                    <div class="space-y-1">
                                        <label class="text-[11px] text-slate-500">{{ tSettings('settings.model_priority', '优先级') }}</label>
                                        <input
                                            v-model.number="entry.item.priority"
                                            type="number"
                                            min="1"
                                            class="w-full px-3 py-2 bg-white border border-slate-100 rounded-xl text-xs text-slate-700 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all"
                                        />
                                    </div>
                                </div>
                                <div class="grid grid-cols-1 lg:grid-cols-6 gap-3">
                                    <div class="space-y-1 lg:col-span-3">
                                        <label class="text-[11px] text-slate-500">{{ tSettings('settings.key_pool_base_url', '接口地址（可选）') }}</label>
                                        <input v-model="entry.item.base_url" type="text" class="w-full px-3 py-2 bg-white border border-slate-100 rounded-xl text-xs text-slate-700 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all" :placeholder="tSettings('settings.base_url_placeholder', '可选，例如 https://api.xxx.com')" />
                                    </div>
                                    <div class="space-y-1 lg:col-span-2">
                                        <label class="text-[11px] text-slate-500">{{ tSettings('settings.model_backup_keys', '备用 Key') }}</label>
                                        <textarea
                                            v-model="entry.item.backup_keys"
                                            rows="3"
                                            class="w-full px-3 py-2 bg-white border border-slate-100 rounded-xl text-xs text-slate-700 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all resize-y"
                                            :placeholder="tSettings('settings.key_pool_backup_keys_placeholder', '备用 Key（可选，换行分隔）')"
                                        ></textarea>
                                    </div>
                                    <div class="space-y-1">
                                        <label class="text-[11px] text-slate-500">{{ tSettings('settings.key_pool_enabled', '启用') }}</label>
                                        <label class="flex items-center gap-2 text-xs text-slate-600 mt-2">
                                            <input type="checkbox" v-model="entry.item.enabled" class="rounded text-indigo-600 focus:ring-indigo-500" />
                                            {{ tSettings('settings.key_pool_enabled', '启用') }}
                                        </label>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="bg-white/80 backdrop-blur-xl border border-white/60 rounded-[24px] p-8 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300 space-y-6">
                    <div class="flex justify-between items-center mb-4 pb-4 border-b border-slate-100/70">
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 rounded-2xl bg-gradient-to-br from-amber-50 to-orange-50 border border-white/70 shadow-inner flex items-center justify-center icon-md">🧩</div>
                            <div>
                                <h3 class="typo-card-title">{{ tSettings('settings.model_config_title', '模型配置') }}</h3>
                                <p class="typo-page-subtitle">{{ tSettings('settings.model_config_desc', '配置模型名称、平台、Key 与消耗积分') }}</p>
                            </div>
                        </div>
                        <div class="flex items-center gap-2">
                            <button @click="addSystemModelForActiveGroup" class="typo-button-compact text-indigo-600 bg-white/70 border border-white/70 px-3 py-1.5 rounded-lg shadow-sm hover:bg-white hover:text-indigo-700 transition-all">
                                {{ tSettings('settings.model_add', '添加模型') }}
                            </button>
                        </div>
                    </div>

                    <div class="space-y-4">
                        <div class="space-y-4 max-h-[70vh] overflow-y-auto custom-scrollbar pr-2">
                            <div class="flex flex-wrap items-center gap-3">
                                <div class="flex items-center gap-1 bg-slate-50 border border-slate-100 rounded-xl p-1">
                                    <button
                                        v-for="mode in modelViewModes"
                                        :key="mode.id"
                                        @click="modelViewMode = mode.id"
                                        class="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
                                        :class="modelViewMode === mode.id ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
                                    >
                                        {{ mode.label }}
                                    </button>
                                </div>
                                <div class="flex flex-wrap gap-2">
                                    <button
                                        v-for="group in activeModelGroups"
                                        :key="group.id"
                                        @click="activeModelGroup = group.id"
                                        class="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border"
                                        :class="activeModelGroup === group.id ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm' : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300 hover:text-indigo-600'"
                                    >
                                        {{ group.label }} <span class="ml-1 text-[10px] opacity-80">({{ group.count }})</span>
                                    </button>
                                </div>
                            </div>
                            <div v-if="!renderModelGroups.some((group) => group.items.length)" class="text-xs text-slate-400">
                                {{ tSettings('settings.model_empty', '暂无模型配置') }}
                            </div>
                            <div v-for="group in renderModelGroups" :key="group.id" class="space-y-3">
                                <div v-if="modelViewMode === 'platform' && group.items.length" class="px-2 text-xs font-semibold text-slate-500 uppercase tracking-widest">
                                    {{ group.label }}
                                </div>
                                <div v-for="entry in group.items" :key="entry.index" class="p-4 rounded-2xl border border-slate-100 bg-white/80 space-y-3 shadow-sm">
                                <div class="flex items-center justify-between gap-3">
                                    <div class="flex items-center gap-3 text-xs text-slate-400">
                                        <span>#{{ entry.index + 1 }}</span>
                                        <span class="px-2 py-0.5 rounded-full bg-amber-50 text-amber-600 border border-amber-100 text-[10px]">
                                            {{ tSettings('settings.pool_tag', '系统') }}
                                        </span>
                                        <span class="text-slate-500">{{ modelSummary(entry.item) }}</span>
                                    </div>
                                    <div class="flex items-center gap-2 text-xs">
                                        <button
                                            @click="toggleSystemModelExpand(entry.index)"
                                            class="text-indigo-500 hover:text-indigo-700"
                                        >
                                            {{ isSystemModelExpanded(entry.index) ? tSettings('settings.key_pool_collapse', '收起') : tSettings('settings.key_pool_expand', '展开') }}
                                        </button>
                                        <button @click="removeSystemModel(entry.index)" class="text-red-400 hover:text-red-600">
                                            {{ tSettings('settings.key_pool_remove', '删除') }}
                                        </button>
                                    </div>
                                </div>
                                <div v-if="!isSystemModelExpanded(entry.index)" class="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                                    <span class="px-2 py-0.5 rounded-full bg-slate-50 border border-slate-200">
                                        {{ getPlatformLabel(entry.item.platform) }}
                                    </span>
                                    <span class="px-2 py-0.5 rounded-full bg-slate-50 border border-slate-200">
                                        {{ tSettings(`settings.model_service_${entry.item.service === 'digital_human' ? 'dh' : entry.item.service}`, entry.item.service) }}
                                    </span>
                                    <span class="px-2 py-0.5 rounded-full bg-slate-50 border border-slate-200">
                                        {{ entry.item.enabled !== false ? tSettings('settings.key_pool_enabled', '启用') : tSettings('settings.key_pool_disabled', '停用') }}
                                    </span>
                                    <span class="px-2 py-0.5 rounded-full bg-slate-50 border border-slate-200 max-w-full truncate">
                                        {{ isModelConfigured(entry.item) ? tSettings('settings.key_pool_configured', 'Key 已配置') : tSettings('settings.key_pool_not_configured', 'Key 未配置') }}
                                    </span>
                                </div>
                                <div v-else class="grid grid-cols-1 lg:grid-cols-7 gap-3">
                                    <div class="space-y-1">
                                        <label class="text-[11px] text-slate-500">{{ tSettings('settings.model_platform', '平台') }}</label>
                                        <select v-model="entry.item.platform" class="w-full px-3 py-2 bg-white border border-slate-100 rounded-xl text-xs text-slate-700 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all" @change="handleSystemPlatformChange(entry.item)">
                                            <option value="vector">{{ tSettings('settings.model_platform_vector', 'ReOpenInnoLab') }}</option>
                                            <option value="bailian">{{ tSettings('settings.model_platform_bailian', '阿里百炼') }}</option>
                                            <option value="ark">{{ tSettings('settings.model_platform_ark', '火山方舟') }}</option>
                                        </select>
                                    </div>
                                    <div class="space-y-1">
                                        <label class="text-[11px] text-slate-500">{{ tSettings('settings.model_service', '用途') }}</label>
                                        <select v-model="entry.item.service" class="w-full px-3 py-2 bg-white border border-slate-100 rounded-xl text-xs text-slate-700 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all" @change="handleSystemServiceChange(entry.item)">
                                            <option value="image">{{ tSettings('settings.model_service_image', '绘图') }}</option>
                                            <option value="video">{{ tSettings('settings.model_service_video', '视频') }}</option>
                                            <option value="audio">{{ tSettings('settings.model_service_audio', '音频') }}</option>
                                            <option value="digital_human">{{ tSettings('settings.model_service_dh', '数字人') }}</option>
                                            <option value="prompt">{{ tSettings('settings.model_service_prompt', '提示词优化') }}</option>
                                        </select>
                                    </div>
                                    <div class="space-y-1 lg:col-span-2">
                                        <label class="text-[11px] text-slate-500">{{ tSettings('settings.model_id', '模型') }}</label>
                                        <input
                                            v-model="entry.item.model"
                                            :list="`system-model-options-${entry.index}`"
                                            class="w-full px-3 py-2 bg-white border border-slate-100 rounded-xl text-xs text-slate-700 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all"
                                            @change="applyModelTemplate(entry.item, entry.item.model)"
                                            :placeholder="tSettings('settings.model_id_placeholder', '支持输入自定义模型 ID')"
                                        />
                                        <datalist :id="`system-model-options-${entry.index}`">
                                            <option v-for="opt in getSystemModelOptionsForSelection(entry.item.service, entry.item.platform)" :key="`${entry.index}-${opt.value}`" :value="opt.value">{{ opt.label }}</option>
                                        </datalist>
                                        <div class="text-[10px] text-slate-400 mt-1">
                                            {{ tSettings('settings.model_platform', '平台') }}: {{ getPlatformLabel(entry.item.platform) }}
                                        </div>
                                    </div>
                                    <div class="space-y-1 lg:col-span-2">
                                        <label class="text-[11px] text-slate-500">{{ tSettings('settings.model_api_key', 'API Key') }}</label>
                                        <input v-model="entry.item.api_key" type="password" class="w-full px-3 py-2 bg-white border border-slate-100 rounded-xl text-xs text-slate-700 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all" placeholder="sk-***" />
                                        <label class="flex items-center gap-2 text-[11px] text-slate-500 mt-2">
                                            <input type="checkbox" v-model="entry.item.enabled" class="rounded text-indigo-600 focus:ring-indigo-500" />
                                            {{ tSettings('settings.model_enabled', '启用') }}
                                        </label>
                                    </div>
                                    <div class="space-y-1">
                                        <label class="text-[11px] text-slate-500">{{ tSettings('settings.model_cost', '消耗积分') }}</label>
                                        <input
                                            v-model.number="entry.item.cost"
                                            type="number"
                                            min="0"
                                            class="w-full px-3 py-2 bg-white border border-slate-100 rounded-xl text-xs text-slate-700 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 transition-all"
                                            :placeholder="tSettings('settings.model_cost_placeholder', '例如 1')"
                                        />
                                    </div>
                                </div>
                                <div v-if="isSystemModelExpanded(entry.index)" class="flex items-center gap-3 text-xs">
                                    <button
                                        @click="runModelTest(entry)"
                                        :disabled="modelTestLoading[entry.index]"
                                        class="font-semibold text-emerald-600 hover:text-emerald-700 disabled:opacity-60 disabled:cursor-not-allowed"
                                    >
                                        {{ modelTestLoading[entry.index] ? tSettings('settings.model_test_running', '测试中...') : tSettings('settings.model_test', '测试') }}
                                    </button>
                                    <button @click="clearSystemModelKey(entry.index)" class="text-red-400 hover:text-red-600">
                                        {{ tSettings('settings.model_remove', '清空Key') }}
                                    </button>
                                </div>
                                <div v-if="isSystemModelExpanded(entry.index) && modelTestStates[entry.index]" class="text-[11px] flex flex-wrap items-center gap-2">
                                    <span
                                        :class="modelTestStates[entry.index].status === 'success' ? 'text-emerald-600' : modelTestStates[entry.index].status === 'error' ? 'text-red-500' : 'text-slate-500'"
                                    >
                                        {{ modelTestStates[entry.index].message }}
                                    </span>
                                    <a
                                        v-if="modelTestStates[entry.index].url"
                                        :href="modelTestStates[entry.index].url"
                                        target="_blank"
                                        class="text-indigo-500 hover:text-indigo-700 underline"
                                    >
                                        {{ tSettings('settings.model_test_view', '查看结果') }}
                                    </a>
                                </div>
                            </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="flex items-center justify-end">
                    <button @click="handleSaveSystemConfig" class="px-6 py-3 bg-gradient-to-r from-blue-500 via-purple-500 to-orange-400 hover:from-blue-400 hover:to-orange-300 text-white rounded-xl typo-button shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40 hover:-translate-y-0.5 active:scale-95 transition-all duration-300">{{ localeStore.t('settings.save_system') }}</button>
                </div>
            </div>

             <div v-if="authStore.user.username === 'admin' && activeSettingsTab === 'users'" class="bg-white/80 backdrop-blur-xl border border-white/60 rounded-[24px] p-8 shadow-sm space-y-6">
                <div class="flex justify-between items-center mb-6 pb-5 border-b border-slate-100/70">
                    <h3 class="typo-card-title">{{ localeStore.t('settings.user_mgmt') }}</h3>
                    <button @click="fetchUsers" class="typo-button-compact text-indigo-600 bg-white/70 border border-white/70 px-3 py-1.5 rounded-lg shadow-sm hover:bg-white hover:text-indigo-700 transition-all">{{ localeStore.t('settings.refresh') }}</button>
                </div>
                <div class="bg-white/70 backdrop-blur-md rounded-2xl p-6 border border-white/60 shadow-sm">
                    <div class="flex items-center justify-between mb-4">
                        <h4 class="typo-body font-extrabold text-slate-800">{{ tSettings('settings.user_create_title', '新增用户') }}</h4>
                        <span class="text-xs text-slate-400">{{ tSettings('settings.user_create_desc', '创建新的登录账号') }}</span>
                    </div>
                    <div class="grid grid-cols-1 lg:grid-cols-4 gap-4">
                        <input v-model="newUserForm.username" type="text" class="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl typo-input text-slate-800 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10" :placeholder="tSettings('settings.user_create_username', '用户名')" />
                        <input v-model="newUserForm.password" type="password" class="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl typo-input text-slate-800 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10" :placeholder="tSettings('settings.user_create_password', '密码')" />
                        <input v-model.number="newUserForm.quota_limit" type="number" min="0" class="w-full px-4 py-3 bg-white border border-slate-200 rounded-xl typo-input text-slate-800 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10" :placeholder="tSettings('settings.user_create_quota', '额度上限')" />
                        <div class="flex items-center gap-3">
                            <label class="flex items-center gap-2 text-sm text-slate-600">
                                <input type="checkbox" v-model="newUserForm.is_pro" class="rounded text-indigo-600 focus:ring-indigo-500" />
                                {{ tSettings('settings.user_create_pro', '专业版') }}
                            </label>
                            <button @click="createUser" class="ml-auto px-4 py-2 bg-slate-900 text-white rounded-xl typo-button-compact shadow-sm hover:bg-black transition-all">{{ tSettings('settings.user_create_submit', '创建') }}</button>
                        </div>
                    </div>
                </div>
                <div class="bg-white/70 backdrop-blur-md rounded-2xl p-6 border border-white/60 shadow-sm space-y-4">
                    <div class="flex items-center justify-between">
                        <h4 class="typo-body font-extrabold text-slate-800">{{ tSettings('settings.user_batch_title', '批量导入账号') }}</h4>
                        <span class="text-xs text-slate-400">{{ tSettings('settings.user_batch_desc', '每行一个账号，格式：用户名,密码,额度,是否专业版') }}</span>
                    </div>
                    <textarea
                        v-model="batchUserImportText"
                        class="w-full h-32 px-4 py-3 bg-white border border-slate-200 rounded-xl typo-input text-slate-800 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10 resize-none"
                        :placeholder="tSettings('settings.user_batch_placeholder', 'teacher01,123456,20,false\\nteacher02,123456,50,true')"
                    ></textarea>
                    <div class="flex flex-wrap items-center gap-4">
                        <label class="flex items-center gap-2 text-sm text-slate-600">
                            <input type="checkbox" v-model="batchUserSkipExisting" class="rounded text-indigo-600 focus:ring-indigo-500" />
                            {{ tSettings('settings.user_batch_skip_existing', '跳过已存在账号') }}
                        </label>
                        <button
                            @click="importUsersBatch"
                            :disabled="batchUserImporting"
                            class="ml-auto px-4 py-2 bg-indigo-600 text-white rounded-xl typo-button-compact shadow-sm hover:bg-indigo-500 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                        >
                            {{ batchUserImporting ? tSettings('settings.user_batch_importing', '导入中...') : tSettings('settings.user_batch_submit', '开始导入') }}
                        </button>
                    </div>
                    <div v-if="batchImportResult" class="text-xs rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-slate-600">
                        {{ batchImportResult }}
                    </div>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full typo-body text-left border-collapse">
                        <thead class="typo-table-head bg-white/70">
                            <tr>
                                <th class="p-4 rounded-l-xl">{{ localeStore.t('settings.col_user') }}</th>
                                <th class="p-4">{{ localeStore.t('settings.col_role') }}</th>
                                <th class="p-4">{{ localeStore.t('settings.col_quota') }}</th>
                                <th class="p-4 rounded-r-xl">{{ localeStore.t('settings.col_action') }}</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-100">
                            <tr v-for="u in usersList" :key="u.id" class="group hover:bg-white/60 transition-colors">
                                <td class="p-4 font-bold text-slate-700">{{ u.username }}</td>
                                <td class="p-4"><span class="px-3 py-1 rounded-full typo-badge shadow-sm" :class="u.is_pro ? 'bg-purple-100 text-purple-700 border border-purple-200' : 'bg-slate-100 text-slate-500 border border-slate-200'">{{ u.is_pro ? localeStore.t('app.pro') : localeStore.t('app.basic') }}</span></td>
                                <td class="p-4">
                                    <div class="flex items-center gap-2">
                                        <span class="font-mono typo-caption-compact text-slate-500">{{ u.quota_used }}</span>
                                        <span class="text-slate-300">/</span>
                                        <input v-model.number="u.quota_limit" type="number" min="0" class="w-20 px-2 py-1 bg-white border border-slate-200 rounded-lg typo-caption-compact font-mono text-slate-600 focus:outline-none focus:border-indigo-400" />
                                    </div>
                                </td>
                                <td class="p-4">
                                    <div class="flex items-center gap-3">
                                        <button @click="toggleUserPro(u)" class="text-indigo-600 hover:text-indigo-800 typo-button-compact opacity-0 group-hover:opacity-100 transition-opacity">{{ localeStore.t('settings.toggle_role') }}</button>
                                        <button @click="saveUserQuota(u)" class="text-slate-600 hover:text-indigo-700 typo-button-compact opacity-0 group-hover:opacity-100 transition-opacity">{{ localeStore.t('settings.save') }}</button>
                                        <button @click="deleteUser(u)" class="text-red-500 hover:text-red-700 typo-button-compact opacity-0 group-hover:opacity-100 transition-opacity">{{ tSettings('settings.user_delete', '删除') }}</button>
                                    </div>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
             </div>
        </div>
      </Transition>

    </div>

    <!-- Image Detail Modal -->
    <Transition name="fade">
        <div v-if="showModal && selectedImage" class="fixed inset-0 z-[200] flex items-center justify-center bg-slate-900/80 p-4 sm:p-8 backdrop-blur-md" @click.self="closeModal">
            <div class="bg-white rounded-[32px] overflow-hidden max-w-7xl w-full h-[85vh] flex flex-col md:flex-row relative shadow-2xl animate-scale-in">
                <button @click="closeModal" class="absolute top-6 right-6 z-20 w-12 h-12 bg-black/10 hover:bg-black/20 text-slate-900 hover:text-red-500 rounded-full flex items-center justify-center transition-all icon-md backdrop-blur-sm">×</button>
                
                <!-- Image Container -->
                <div class="flex-1 checker-bg flex items-center justify-center p-8 relative overflow-hidden group">
                     <img :src="selectedImage.url" class="max-w-full max-h-full object-contain shadow-2xl rounded-lg transition-transform duration-500 hover:scale-[1.02]" />
                     <div v-if="selectedImage.urls && selectedImage.urls.length > 1" class="absolute bottom-6 left-1/2 -translate-x-1/2 flex flex-wrap gap-2 bg-white/80 backdrop-blur-sm border border-white/60 rounded-2xl p-2 shadow-lg">
                         <button v-for="(imgUrl, idx) in selectedImage.urls" :key="imgUrl" @click.stop="selectedImage.url = imgUrl" class="w-12 h-12 rounded-lg overflow-hidden border border-transparent hover:border-indigo-400 transition-all" :class="imgUrl === selectedImage.url ? 'border-indigo-500 ring-2 ring-indigo-200' : ''">
                             <img :src="imgUrl" class="w-full h-full object-cover" :alt="`seedream-${idx + 1}`" />
                         </button>
                     </div>
                </div>
                
                <!-- Info Sidebar -->
                <div class="w-full md:w-96 bg-white p-10 overflow-y-auto border-l border-slate-100 h-full flex flex-col gap-8">
                     <div>
                         <h3 class="typo-modal-title mb-2">{{ localeStore.t('image.details') }}</h3>
                         <p class="typo-page-subtitle">{{ localeStore.t('image.created_with') }} {{ selectedImage.model || 'AI' }}</p>
                     </div>
                     
                     <div class="space-y-4 flex-1">
                        <div>
                           <label class="typo-label-compact mb-2 block">{{ localeStore.t('image.prompt_label') }}</label>
                           <div class="bg-slate-50 p-5 rounded-2xl typo-body font-mono leading-relaxed select-text border border-slate-100">{{ selectedImage.enhanced_prompt || selectedImage.prompt }}</div>
                        </div>
                        
                        <div class="grid grid-cols-2 gap-4 typo-caption-compact">
                            <div class="p-4 bg-slate-50 rounded-2xl text-center border border-slate-100 hover:border-indigo-200 transition-colors">
                                <div class="typo-label-compact mb-1">{{ localeStore.t('image.subject') }}</div>
                                <div class="typo-body font-black text-slate-800">{{ getSubjectLabel(selectedImage.subject) }}</div>
                            </div>
                            <div class="p-4 bg-slate-50 rounded-2xl text-center border border-slate-100 hover:border-indigo-200 transition-colors">
                                <div class="typo-label-compact mb-1">{{ localeStore.t('image.ratio') }}</div>
                                <div class="typo-body font-black text-slate-800 font-mono">{{ selectedImage.aspectRatio }}</div>
                            </div>
                        </div>
                     </div>
                     
                     <div class="pt-6 flex flex-col gap-3 shrink-0">
                         <button @click="jumpToVideo(selectedImage)" class="w-full py-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-2xl font-bold shadow-lg hover:shadow-xl text-center transition-all flex items-center justify-center gap-2">
                            <Video class="w-4 h-4" />
                            <span>{{ localeStore.t('image.to_video') || '生成视频' }}</span>
                         </button>
                         <a :href="selectedImage.url" download class="w-full py-4 bg-slate-900 hover:bg-black text-white rounded-2xl font-bold shadow-lg hover:shadow-xl text-center transition-all flex items-center justify-center gap-2">
                            <span>⬇️</span> {{ localeStore.t('image.download') }}
                         </a>
                         <button @click="copyPrompt" class="w-full py-4 bg-white border-2 border-slate-100 hover:border-slate-300 text-slate-600 font-bold rounded-2xl transition-all hover:bg-slate-50">
                            {{ localeStore.t('image.copy_prompt') }}
                         </button>
                     </div>
                 </div>
            </div>
        </div>
    </Transition>
    
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive, watch, nextTick } from 'vue'
import { NPopselect, useMessage, NUpload } from 'naive-ui'
import { Wand2, Image as ImageIcon, Bot, Zap, Download, RefreshCw, Maximize2, Video } from 'lucide-vue-next'
import api from '../services/api'
import { fetchModelCatalog, clearModelCatalogCache } from '../services/modelCatalog'
import { useAuthStore } from '../stores/auth'
import { useLocaleStore } from '../stores/locale'
import { readUserKeyPools, saveUserKeyPools, buildLegacyPools, selectUserPoolWithFallback } from '../utils/userKeyPools'
import { loadLocalHistory, prependLocalHistory, mergeLocalHistory } from '../utils/localHistory'
import DigitalHumanPanel from '../components/DigitalHumanPanel.vue'
import { voiceCatalog } from '../data/voiceCatalog'

const props = defineProps(['activeTab'])
const emit = defineEmits(['update-tab'])

const authStore = useAuthStore()
const localeStore = useLocaleStore()
const message = useMessage()
const uploadAction = import.meta.env.VITE_PUBLIC_UPLOAD_URL || '/api/upload'
const IMAGE_HISTORY_KEY = 'nbs_history_image'
const VIDEO_SEED_KEY = 'nbs_seed_video_from_image'

// --- State ---
const loginForm = reactive({ username: '', password: '' })
const authLoading = ref(false)

const inputText = ref('')
const processing = ref(false)
const optimizing = ref(false)
const singleTasks = ref([])
const currentDisplayImage = ref(null)
const batchQueue = ref([])
const batchUploadImagesCache = ref({ ts: 0, items: [] })
const batchRunning = ref(false)
const batchStopRequested = ref(false)
const batchDownloading = ref(false)
const refImageUrls = ref([])
const quickRefineText = ref('')
const galleryImages = ref([]) 
const galleryFilter = ref('all')
const showFeaturedOnly = ref(false)
const showMyImages = ref(false)
const showModal = ref(false)
const selectedImage = ref(null)
const userKeyPools = ref([])
const expandedUserPools = reactive(new Set())
const userPoolsDirty = ref(false)
const userPoolsDirtyLocked = ref(false)

// Admin
const usersList = ref([])
const batchUserImportText = ref('')
const batchUserSkipExisting = ref(true)
const batchUserImporting = ref(false)
const batchImportResult = ref('')
const systemImageKey = ref('')
const systemImageBackupKeysInput = ref('')
const systemImageBaseUrl = ref('')
const systemTtsKey = ref('')
const systemTtsBackupKeysInput = ref('')
const systemTtsBaseUrl = ref('')
const systemVideoKey = ref('')
const systemVideoBackupKeysInput = ref('')
const systemVideoBaseUrl = ref('')
const systemKeyPools = ref([])
const expandedPools = reactive(new Set())
const expandedSystemModels = reactive(new Set())
const systemConfigDirty = ref(false)
const systemModels = ref([])
const modelCatalog = ref([])
const modelCatalogLoaded = ref(false)
const promptHealthLoading = ref(false)
const promptHealth = ref(null)
const promptConfigErrors = ref([])
const promptConfigWarnings = ref([])

const withUserPoolsDirtyLock = (fn) => {
    userPoolsDirtyLocked.value = true
    try {
        fn()
    } finally {
        nextTick(() => {
            userPoolsDirtyLocked.value = false
        })
    }
}

watch(
    userKeyPools,
    () => {
        if (userPoolsDirtyLocked.value) return
        userPoolsDirty.value = true
    },
    { deep: true }
)

watch(
    systemKeyPools,
    () => {
        systemConfigDirty.value = true
    },
    { deep: true }
)

watch(
    systemModels,
    () => {
        systemConfigDirty.value = true
    },
    { deep: true }
)

const MODEL_PLATFORM_BASE_URLS = {
    vector: 'https://api.vectorengine.ai',
    bailian: 'https://dashscope.aliyuncs.com/api/v1',
    ark: 'https://ark.cn-beijing.volces.com/api/v3'
}

const SYSTEM_PROVIDER_BASE_URLS = {
    ...MODEL_PLATFORM_BASE_URLS,
    openai: 'https://api.openai.com/v1',
    gemini: 'https://generativelanguage.googleapis.com/v1beta'
}

const USER_PROVIDER_BASE_URLS = MODEL_PLATFORM_BASE_URLS
const PROMPT_CHANNEL_KEYS = ['google', 'bytedance', 'aliyun']
const PROMPT_CHANNEL_DEFAULTS = {
    google: ['gemini-3.1-pro-preview', 'claude-sonnet-4-6', 'gpt-5.2-chat', 'kimi-k2.5'],
    bytedance: ['gemini-3.1-pro-preview', 'claude-sonnet-4-6', 'gpt-5.2-chat', 'kimi-k2.5'],
    aliyun: ['gemini-3.1-pro-preview', 'claude-sonnet-4-6', 'gpt-5.2-chat', 'kimi-k2.5']
}

const clonePromptDefaults = () => ({
    google: { enabled: true, models: [...PROMPT_CHANNEL_DEFAULTS.google] },
    bytedance: { enabled: true, models: [...PROMPT_CHANNEL_DEFAULTS.bytedance] },
    aliyun: { enabled: true, models: [...PROMPT_CHANNEL_DEFAULTS.aliyun] }
})

const promptChannelsDraft = reactive(clonePromptDefaults())

watch(
    promptChannelsDraft,
    () => {
        systemConfigDirty.value = true
    },
    { deep: true }
)

const normalizePromptChannelValue = (value) => {
    const text = String(value || '').trim().toLowerCase()
    if (text === 'byte') return 'bytedance'
    if (PROMPT_CHANNEL_KEYS.includes(text)) return text
    return ''
}

const normalizePromptChannelDraft = (raw = {}) => {
    const next = clonePromptDefaults()
    const src = raw && typeof raw === 'object' ? raw : {}
    PROMPT_CHANNEL_KEYS.forEach((channel) => {
        const item = src[channel] || src[channel === 'bytedance' ? 'byte' : channel] || {}
        next[channel].enabled = item?.enabled !== false
        const values = Array.isArray(item?.models)
            ? item.models.map((v) => String(v || '').trim()).filter(Boolean)
            : String(item?.models || '')
                .split(/[,\n;]/)
                .map((v) => v.trim())
                .filter(Boolean)
        const dedup = []
        values.forEach((value) => {
            if (!value || dedup.includes(value)) return
            dedup.push(value)
        })
        next[channel].models = [...(dedup.length ? dedup : PROMPT_CHANNEL_DEFAULTS[channel])]
        while (next[channel].models.length < 4) next[channel].models.push('')
        next[channel].models = next[channel].models.slice(0, 4)
    })
    return next
}

const assignPromptChannelDraft = (raw = {}) => {
    const normalized = normalizePromptChannelDraft(raw)
    PROMPT_CHANNEL_KEYS.forEach((channel) => {
        promptChannelsDraft[channel].enabled = normalized[channel].enabled
        promptChannelsDraft[channel].models = [...normalized[channel].models]
    })
}

const normalizePlatform = (value) => {
    if (!value) return ''
    const text = String(value).trim().toLowerCase()
    if (['向量', 'vector', 'vectorengine', 'reopeninnolab'].includes(text)) return 'vector'
    if (['阿里', '百炼', 'bailian', 'aliyun', 'dashscope'].includes(text)) return 'bailian'
    if (['火山', '方舟', 'ark', 'volc', 'volcengine', '豆包', 'doubao'].includes(text)) return 'ark'
    return text
}

const getPlatformBaseUrl = (platform) => MODEL_PLATFORM_BASE_URLS[normalizePlatform(platform)] || ''

const inferPlatformFromBaseUrl = (value) => {
    const text = String(value || '').trim().toLowerCase()
    if (!text) return ''
    if (text.includes('vectorengine.ai')) return 'vector'
    if (text.includes('dashscope.aliyuncs.com')) return 'bailian'
    if (text.includes('ark.cn-beijing') || text.includes('volcengine')) return 'ark'
    return ''
}

const normalizeModelPlatform = (item) => {
    const direct = normalizePlatform(item?.platform)
    if (direct) return direct
    const inferred = inferPlatformFromBaseUrl(item?.base_url)
    return inferred || ''
}

const normalizeModelItem = (item) => {
    const model = String(item?.model || item?.id || item?.value || '').trim()
    const service = String(item?.service || item?.type || 'image').trim().toLowerCase()
    const costValue = item?.cost
    const backupKeys = Array.isArray(item?.backup_keys)
        ? item.backup_keys.join('\n')
        : (item?.backup_keys || '')
    return {
        model,
        label: String(item?.label || item?.name || model).trim(),
        service: ['image', 'video', 'audio', 'digital_human', 'prompt'].includes(service) ? service : 'image',
        platform: normalizePlatform(item?.platform || item?.provider),
        api_key: String(item?.api_key || item?.key || '').trim(),
        base_url: String(item?.base_url || '').trim(),
        cost: Number.isFinite(Number(costValue)) ? Number(costValue) : null,
        enabled: item?.enabled !== false,
        backup_keys: backupKeys
    }
}

const serializeSystemModels = () => {
    return (systemModels.value || [])
        .map((item) => {
            const platform = normalizePlatform(item.platform)
            const baseUrl = getPlatformBaseUrl(platform) || String(item.base_url || '').trim()
            return {
                model: String(item.model || '').trim(),
                label: String(item.label || '').trim(),
                service: String(item.service || 'image').trim().toLowerCase(),
                platform,
                api_key: String(item.api_key || '').trim(),
                backup_keys: parseKeyList(item.backup_keys || ''),
                base_url: baseUrl,
                cost: Number.isFinite(Number(item.cost)) ? Number(item.cost) : null,
                enabled: item.enabled !== false
            }
        })
        .filter((item) => item.model)
}

const applyModelTemplate = (item, modelValue) => {
    const template = modelCatalog.value.find((m) => m?.model === modelValue)
        || systemModels.value.find((m) => m?.model === modelValue)
    if (!template) return
    const platform = normalizePlatform(template.platform) || inferPlatformFromBaseUrl(template.base_url) || item.platform
    item.model = template.model
    item.label = template.label || template.model
    item.service = template.service || item.service
    item.platform = platform || item.platform
    item.cost = Number.isFinite(Number(template.cost)) ? Number(template.cost) : item.cost
}

const getSystemModelOptionsForSelection = (service, platform) => {
    const normalizedService = String(service || '').trim().toLowerCase()
    const normalizedPlatform = normalizePlatform(platform)
    return systemModelOptions.value.filter((opt) => {
        const matchesService = !normalizedService || String(opt.service || '').trim().toLowerCase() === normalizedService
        const optPlatform = normalizePlatform(opt.platform)
        const matchesPlatform = !normalizedPlatform || !optPlatform || optPlatform === normalizedPlatform
        return matchesService && matchesPlatform
    })
}

const resetSystemModelSelection = (item) => {
    item.model = ''
    item.label = ''
    item.cost = null
}

const handleSystemServiceChange = (item) => {
    const options = getSystemModelOptionsForSelection(item.service, item.platform)
    const match = options.find((opt) => opt.value === item.model)
    if (match) applyModelTemplate(item, match.value)
}

const handleSystemPlatformChange = (item) => {
    const options = getSystemModelOptionsForSelection(item.service, item.platform)
    const match = options.find((opt) => opt.value === item.model)
    if (match) applyModelTemplate(item, match.value)
}

const getDefaultTemplateForGroup = () => {
    const list = modelCatalog.value || []
    if (modelViewMode.value === 'platform') {
        const platform = normalizePlatform(activeModelGroup.value)
        return list.find((m) => normalizePlatform(m.platform) === platform) || list[0]
    }
    const service = String(activeModelGroup.value || '').trim().toLowerCase()
    return list.find((m) => String(m.service || '').trim().toLowerCase() === service) || list[0]
}

const addSystemModel = (defaults = {}) => {
    const template = getDefaultTemplateForGroup()
    const platform = normalizePlatform(defaults.platform) || normalizePlatform(template?.platform) || 'vector'
    const service = String(defaults.service || template?.service || 'image').trim().toLowerCase()
    systemModels.value.push({
        model: template?.model || '',
        label: template?.label || template?.model || '',
        service: ['image', 'video', 'audio', 'digital_human', 'prompt'].includes(service) ? service : 'image',
        platform,
        api_key: '',
        backup_keys: '',
        base_url: '',
        cost: Number.isFinite(Number(template?.cost)) ? Number(template.cost) : null,
        enabled: true
    })
}

const addSystemModelForActiveGroup = () => {
    if (modelViewMode.value === 'platform') {
        addSystemModel({ platform: activeModelGroup.value })
    } else {
        addSystemModel({ service: activeModelGroup.value })
    }
}

const clearSystemModelKey = (idx) => {
    const item = systemModels.value[idx]
    if (!item) return
    item.api_key = ''
    item.backup_keys = ''
    systemConfigDirty.value = true
}

const isSystemModelExpanded = (idx) => expandedSystemModels.has(idx)

const toggleSystemModelExpand = (idx) => {
    if (expandedSystemModels.has(idx)) expandedSystemModels.delete(idx)
    else expandedSystemModels.add(idx)
}

const modelSummary = (item) => {
    const model = String(item?.model || '').trim() || '—'
    const cost = Number.isFinite(Number(item?.cost)) ? `${Number(item.cost)}${tSettings('settings.model_cost_unit', '积分')}` : '—'
    const keyStatus = isModelConfigured(item)
        ? tSettings('settings.key_pool_configured', 'Key 已配置')
        : tSettings('settings.key_pool_not_configured', 'Key 未配置')
    return `${model} · ${tSettings('settings.model_cost', '消耗积分')}:${cost} · ${keyStatus}`
}

const isModelConfigured = (item) => {
    if (String(item?.api_key || '').trim()) return true
    const backupKeys = Array.isArray(item?.backup_keys)
        ? item.backup_keys
        : String(item?.backup_keys || '').split('\n')
    return backupKeys.some((value) => String(value || '').trim())
}

const removeSystemModel = (idx) => {
    const item = systemModels.value[idx]
    if (!item) return
    const promptText = localeStore.t('settings.model_delete_confirm')
    const fallback = promptText === 'settings.model_delete_confirm'
        ? `确认删除模型：${item.model || '#'+(idx + 1)}`
        : promptText
    if (!window.confirm(fallback)) return
    systemModels.value.splice(idx, 1)
    const nextExpanded = new Set()
    expandedSystemModels.forEach((value) => {
        if (value < idx) nextExpanded.add(value)
        if (value > idx) nextExpanded.add(value - 1)
    })
    expandedSystemModels.clear()
    nextExpanded.forEach((value) => expandedSystemModels.add(value))
    const reindexState = (stateObj) => {
        const next = {}
        Object.keys(stateObj).forEach((key) => {
            const index = Number(key)
            if (!Number.isInteger(index) || index === idx) return
            const target = index > idx ? index - 1 : index
            next[target] = stateObj[key]
        })
        Object.keys(stateObj).forEach((key) => {
            delete stateObj[key]
        })
        Object.keys(next).forEach((key) => {
            stateObj[key] = next[key]
        })
    }
    reindexState(modelTestStates)
    reindexState(modelTestLoading)
    systemConfigDirty.value = true
}

const loadModelCatalog = async () => {
    try {
        modelCatalog.value = await fetchModelCatalog()
        modelCatalogLoaded.value = true
    } catch (e) {
        modelCatalogLoaded.value = false
    }
}

// --- Settings ---
const settings = ref({
    subject: 'general', 
    grade: 'general', 
    aspectRatio: '1:1', 
    quality: 'standard',
    imageProvider: 'google',
    model: '',
    promptChannel: 'google',
    seedreamGroup: false,
    seedreamMaxImages: 4
})

const batchType = ref('image')
const batchDefaults = reactive({
    image: {
        subject: settings.value.subject,
        grade: settings.value.grade,
        aspectRatio: settings.value.aspectRatio,
        quality: settings.value.quality,
        imageProvider: settings.value.imageProvider,
        model: '',
        promptChannel: settings.value.promptChannel,
        optimize: true,
        seedreamGroup: false,
        seedreamMaxImages: 4
    },
    video: {
        mode: 'text',
        model: '',
        aspectRatio: '16:9',
        resolution: '720p',
        durationSeconds: 8,
        imageUrl: ''
    },
    audio: {
        model: '',
        voice: 'Cherry',
        language_type: 'Auto',
        instructions: '',
        optimize_instructions: true
    },
    digital_human: {
        model: '',
        avatarUrl: '',
        resolution: 480,
        style: 'speech',
        provider: 'auto'
    }
})

// Options
const seedreamModelText = computed(() => String(settings.value.model || '').toLowerCase())
const isSeedreamGroupModel = computed(() => seedreamModelText.value.includes('seedream-4'))
const batchSeedreamModelText = computed(() => String(batchDefaults.image.model || '').toLowerCase())
const isBatchSeedreamGroupModel = computed(() => batchSeedreamModelText.value.includes('seedream-4'))

watch(
    () => settings.value.seedreamMaxImages,
    (value) => {
        const num = Number(value)
        if (!Number.isFinite(num)) {
            settings.value.seedreamMaxImages = 4
            return
        }
        if (num < 1) settings.value.seedreamMaxImages = 1
        if (num > 15) settings.value.seedreamMaxImages = 15
    }
)

watch(
    seedreamModelText,
    (value) => {
        if (!String(value || '').includes('seedream-4')) {
            settings.value.seedreamGroup = false
        }
    }
)

watch(
    () => batchDefaults.image.seedreamMaxImages,
    (value) => {
        const num = Number(value)
        if (!Number.isFinite(num)) {
            batchDefaults.image.seedreamMaxImages = 4
            return
        }
        if (num < 1) batchDefaults.image.seedreamMaxImages = 1
        if (num > 15) batchDefaults.image.seedreamMaxImages = 15
    }
)

watch(
    batchSeedreamModelText,
    (value) => {
        if (!String(value || '').includes('seedream-4')) {
            batchDefaults.image.seedreamGroup = false
        }
    }
)

const formatCatalogLabel = (item, withCost = false) => {
    const name = item?.label || item?.model || ''
    const costValue = Number.isFinite(Number(item?.cost)) ? Number(item.cost) : null
    if (withCost && costValue !== null) return `${name}（${costValue}积分）`
    return name
}

const buildCatalogOptions = (service, withCost = false) => {
    const items = modelCatalog.value.filter((m) => m?.service === service)
    return items.map((item) => ({
        label: formatCatalogLabel(item, withCost),
        value: item.model,
        cost: Number.isFinite(Number(item?.cost)) ? Number(item.cost) : null
    }))
}

const systemModelOptions = computed(() => {
    const merged = []
    const seen = new Set()
    const pushItem = (item) => {
        const model = item?.model
        if (!model || seen.has(model)) return
        seen.add(model)
        merged.push({
            label: formatCatalogLabel(item, true),
            value: model,
            service: item.service,
            platform: item.platform,
            cost: item.cost
        })
    }
    ;(modelCatalog.value || []).forEach(pushItem)
    ;(systemModels.value || []).forEach(pushItem)
    return merged
})

const modelOptions = computed(() => buildCatalogOptions('image', true))
const promptModelOptions = computed(() => buildCatalogOptions('prompt'))

const IMAGE_PROVIDER_KEYS = ['google', 'bytedance', 'aliyun', 'openai']
const IMAGE_PROVIDER_MODEL_PRIORITY = {
    google: ['gemini-3.1-flash-image-preview', 'gemini-3-pro-image-preview'],
    bytedance: ['doubao-seedream-5-0-260128', 'doubao-seedream-4-5-251128'],
    aliyun: ['z-image-turbo'],
    openai: ['gpt-image-1.5-all', 'gpt-image-1.5']
}
const IMAGE_GLOBAL_MODEL_FALLBACK = [
    'gemini-3.1-flash-image-preview',
    'gemini-3-pro-image-preview',
    'doubao-seedream-5-0-260128',
    'doubao-seedream-4-5-251128',
    'z-image-turbo',
    'gpt-image-1.5-all',
    'gpt-image-1.5'
]
const normalizeImageProvider = (value) => {
    const text = String(value || '').trim().toLowerCase()
    if (!text) return 'google'
    if (text === 'byte') return 'bytedance'
    if (['ali', 'aliyun'].includes(text)) return 'aliyun'
    if (['openai', 'gpt', 'chatgpt'].includes(text)) return 'openai'
    if (IMAGE_PROVIDER_KEYS.includes(text)) return text
    return 'google'
}
const inferImageProviderFromModel = (model) => {
    const text = String(model || '').toLowerCase()
    if (!text) return 'google'
    if (text.includes('gemini')) return 'google'
    if (text.includes('doubao') || text.includes('seedream') || text.includes('seededit')) return 'bytedance'
    if (text.includes('z-image') || text.includes('wanx') || text.includes('ali')) return 'aliyun'
    if (text.includes('gpt-image') || text.includes('dall-e')) return 'openai'
    return 'google'
}
const imageProviderOptions = computed(() => [
    { label: 'Google', value: 'google' },
    { label: 'Bytedance', value: 'bytedance' },
    { label: '阿里', value: 'aliyun' },
    { label: 'OpenAI', value: 'openai' }
])
const getImageProviderLabel = (value) => {
    const normalized = normalizeImageProvider(value)
    const matched = imageProviderOptions.value.find((item) => item.value === normalized)
    return matched?.label || 'Google'
}
const getImageModelChainByProvider = (provider, preferredModel = '') => {
    const normalizedProvider = normalizeImageProvider(provider)
    const available = modelOptions.value.map((opt) => String(opt.value || '').trim()).filter(Boolean)
    const availableSet = new Set(available)
    const chain = [
        ...(IMAGE_PROVIDER_MODEL_PRIORITY[normalizedProvider] || []),
        String(preferredModel || '').trim(),
        ...IMAGE_GLOBAL_MODEL_FALLBACK,
        ...available
    ]
    const dedup = []
    chain.forEach((model) => {
        const text = String(model || '').trim()
        if (!text || dedup.includes(text)) return
        if (available.length && !availableSet.has(text)) return
        dedup.push(text)
    })
    return dedup
}
const ensureImageModelSelection = (target, force = false) => {
    if (!target || typeof target !== 'object') return
    const normalizedProvider = normalizeImageProvider(target.imageProvider)
    target.imageProvider = normalizedProvider
    const chain = getImageModelChainByProvider(normalizedProvider, target.model)
    const current = String(target.model || '').trim()
    if (!force && current && chain.includes(current)) return
    target.model = chain[0] || ''
}

const normalizePromptChannel = (value) => normalizePromptChannelValue(value) || 'google'
const promptChannelOptions = computed(() => [
    { label: 'Google', value: 'google' },
    { label: '字节', value: 'bytedance' },
    { label: '阿里', value: 'aliyun' }
])
const promptChannelAdminRows = computed(() => [
    { key: 'google', label: 'Google' },
    { key: 'bytedance', label: 'Bytedance' },
    { key: 'aliyun', label: '阿里' }
])
const promptChannelModelOptions = computed(() => {
    const merged = []
    const seen = new Set()
    const pushItem = (item) => {
        if (String(item?.service || '').trim().toLowerCase() !== 'prompt') return
        const model = String(item?.model || '').trim()
        if (!model || seen.has(model)) return
        seen.add(model)
        merged.push({
            label: item?.label || model,
            value: model,
            enabled: item?.enabled !== false
        })
    }
    ;(systemModels.value || []).forEach(pushItem)
    ;(modelCatalog.value || []).forEach(pushItem)
    return merged
})
const promptChannelPrimaryModel = {
    google: 'gemini-3.1-pro-preview',
    bytedance: 'gemini-3.1-pro-preview',
    aliyun: 'gemini-3.1-pro-preview'
}
const promptModelHintsByChannel = {
    google: ['gemini-3.1-pro-preview', 'gemini', 'claude-sonnet-4-6', 'gpt-5.2-chat', 'kimi-k2.5'],
    bytedance: ['gemini-3.1-pro-preview', 'gemini', 'claude-sonnet-4-6', 'gpt-5.2-chat', 'kimi-k2.5'],
    aliyun: ['gemini-3.1-pro-preview', 'gemini', 'claude-sonnet-4-6', 'gpt-5.2-chat', 'kimi-k2.5']
}
const resolvePromptModel = (channel, fallbackModel = '') => {
    const normalizedChannel = normalizePromptChannel(channel)
    const primary = promptChannelPrimaryModel[normalizedChannel]
    const options = promptModelOptions.value || []
    if (!options.length) return primary || fallbackModel || ''
    const models = options.map((opt) => String(opt.value || '').trim()).filter(Boolean)
    const hints = promptModelHintsByChannel[normalizedChannel] || []
    for (const hint of hints) {
        const matched = models.find((model) => model.toLowerCase().includes(hint))
        if (matched) return matched
    }
    return primary || models[0] || fallbackModel || ''
}
const ensurePromptChannelDraftModels = () => {
    const optionValues = promptChannelModelOptions.value.map((opt) => opt.value)
    if (!optionValues.length) return
    PROMPT_CHANNEL_KEYS.forEach((channel) => {
        const draft = promptChannelsDraft[channel] || {}
        const current = Array.isArray(draft.models) ? draft.models : []
        const next = []
        current.forEach((model) => {
            const text = String(model || '').trim()
            if (!text || next.includes(text)) return
            if (!optionValues.includes(text)) return
            next.push(text)
        })
        const defaults = PROMPT_CHANNEL_DEFAULTS[channel] || []
        defaults.forEach((model) => {
            if (next.length >= 4) return
            if (!optionValues.includes(model) || next.includes(model)) return
            next.push(model)
        })
        optionValues.forEach((model) => {
            if (next.length >= 4) return
            if (next.includes(model)) return
            next.push(model)
        })
        while (next.length < 4) next.push('')
        promptChannelsDraft[channel].models = next.slice(0, 4)
    })
}
const promptHealthStatusText = (status) => {
    if (status === 'green') return tSettings('settings.prompt_health_green', '主模型可用')
    if (status === 'yellow') return tSettings('settings.prompt_health_yellow', '回退可用')
    if (status === 'red') return tSettings('settings.prompt_health_red', '不可用')
    return tSettings('settings.prompt_health_unknown', '未检测')
}
const promptHealthBadgeClass = (status) => {
    if (status === 'green') return 'text-emerald-700 border-emerald-200 bg-emerald-50'
    if (status === 'yellow') return 'text-amber-700 border-amber-200 bg-amber-50'
    if (status === 'red') return 'text-red-700 border-red-200 bg-red-50'
    return 'text-slate-500 border-slate-200 bg-slate-50'
}
const getPromptHealthChannel = (channel) => {
    return promptHealth.value?.channels?.[normalizePromptChannel(channel)] || null
}
const parseInlineList = (value) => {
    if (!value) return []
    if (Array.isArray(value)) return value.map((item) => String(item || '').trim()).filter(Boolean)
    return String(value)
        .split(/[,\n;]/)
        .map((item) => item.trim())
        .filter(Boolean)
}
const serializePromptChannels = () => {
    const output = {}
    PROMPT_CHANNEL_KEYS.forEach((channel) => {
        const raw = promptChannelsDraft[channel] || {}
        const dedup = []
        ;(raw.models || []).forEach((model) => {
            const text = String(model || '').trim()
            if (!text || dedup.includes(text)) return
            dedup.push(text)
        })
        output[channel] = {
            enabled: raw.enabled !== false,
            models: dedup.slice(0, 4)
        }
    })
    return output
}
const promptDraftChannelPreview = computed(() => {
    const preview = {}
    const promptModelMap = new Map()
    ;(systemModels.value || []).forEach((item) => {
        if (String(item?.service || '').trim().toLowerCase() !== 'prompt') return
        const model = String(item?.model || '').trim()
        if (!model) return
        promptModelMap.set(model.toLowerCase(), item)
    })
    const normalizedPools = (systemKeyPools.value || [])
        .filter((pool) => pool?.enabled !== false && String(pool?.service || '').trim().toLowerCase() === 'prompt')
        .map((pool) => ({
            models: parseInlineList(pool.models).map((item) => item.toLowerCase()),
            keys: [String(pool.key || '').trim(), ...parseInlineList(pool.backup_keys)].filter(Boolean)
        }))
    const channels = serializePromptChannels()
    Object.entries(channels).forEach(([channel, payload]) => {
        let count = 0
        ;(payload.models || []).forEach((model) => {
            const text = String(model || '').trim()
            if (!text) return
            const item = promptModelMap.get(text.toLowerCase())
            if (item) {
                const modelKeys = [String(item.api_key || '').trim(), ...parseInlineList(item.backup_keys)].filter(Boolean)
                count += modelKeys.length
            }
            normalizedPools.forEach((pool) => {
                if (!pool.keys.length) return
                if (pool.models.length && !pool.models.includes(text.toLowerCase())) return
                count += pool.keys.length
            })
        })
        preview[channel] = { candidate_count: count }
    })
    return preview
})
const validatePromptChannelsDraft = () => {
    const errors = []
    const warnings = []
    const channels = serializePromptChannels()
    const promptModelMap = new Map()
    ;(systemModels.value || []).forEach((item) => {
        if (String(item?.service || '').trim().toLowerCase() !== 'prompt') return
        const model = String(item?.model || '').trim()
        if (!model) return
        promptModelMap.set(model.toLowerCase(), item)
    })
    Object.entries(channels).forEach(([channel, payload]) => {
        const models = payload.models || []
        if (payload.enabled !== true) errors.push(`${channel} 通道未启用`)
        if (models.length < 2) errors.push(`${channel} 通道至少需要 2 个模型`)
        let hasCandidate = false
        models.forEach((model) => {
            const item = promptModelMap.get(String(model || '').toLowerCase())
            if (!item) {
                errors.push(`${channel} 通道模型未配置: ${model}`)
                return
            }
            if (item.enabled === false) {
                errors.push(`${channel} 通道模型未启用: ${model}`)
            }
            const candidateCount = promptDraftChannelPreview.value[channel]?.candidate_count || 0
            if (candidateCount > 0) hasCandidate = true
            else warnings.push(`${channel} 通道模型 ${model} 未发现可用 Key`)
        })
        if (!hasCandidate) errors.push(`${channel} 通道没有可用 Key 候选链`)
    })
    return { errors, warnings }
}
const refreshPromptHealth = async () => {
    if (authStore.user.username !== 'admin') return
    if (promptHealthLoading.value) return
    promptHealthLoading.value = true
    try {
        const res = await api.get('/api/admin/prompt_health', {
            headers: authStore.token ? { Authorization: `Bearer ${authStore.token}` } : {}
        })
        promptHealth.value = res?.data || null
        const warn = res?.data?.warnings || []
        if (Array.isArray(warn) && warn.length) promptConfigWarnings.value = warn
    } catch (e) {
        const detail = e?.response?.data?.detail || e?.message || ''
        message.error(`${tSettings('settings.model_test_failed', '测试失败')}: ${detail}`)
    } finally {
        promptHealthLoading.value = false
    }
}
const subjectOptions = computed(() => [
  { label: localeStore.t('image.subjects.general'), value: 'general' },
  { label: localeStore.t('image.subjects.textbook'), value: 'textbook' },
  { label: localeStore.t('image.subjects.sketchnote'), value: 'sketchnote' },
  { label: localeStore.t('image.subjects.3d_model'), value: '3d_model' }
])
const ratioOptions = computed(() => [
  { label: localeStore.t('image.options.ratio_1_1'), value: '1:1' },
  { label: localeStore.t('image.options.ratio_16_9'), value: '16:9' },
  { label: localeStore.t('image.options.ratio_9_16'), value: '9:16' },
  { label: localeStore.t('image.options.ratio_4_3'), value: '4:3' },
  { label: localeStore.t('image.options.ratio_3_4'), value: '3:4' }
])
const qualityOptions = computed(() => [
  { label: localeStore.t('image.options.quality_standard'), value: 'standard' },
  { label: localeStore.t('image.options.quality_2k'), value: '2k' },
  { label: localeStore.t('image.options.quality_4k'), value: '4k' }
])

const ttsModelOptions = computed(() => buildCatalogOptions('audio'))

const videoModelOptionsAll = computed(() => buildCatalogOptions('video', true))
const defaultVideoModel = computed(() => {
    const options = videoModelOptionsAll.value || []
    const nonSora = options.find((option) => !String(option.value).toLowerCase().includes('sora'))
    return nonSora?.value || ''
})
const digitalHumanModelOptions = computed(() => buildCatalogOptions('digital_human', true))
const batchVideoModelOptions = computed(() => {
  const mode = batchDefaults.video.mode || 'text'
  const options = videoModelOptionsAll.value || []
  if (mode === 'image') return options
  return options.filter((option) => !String(option.value).toLowerCase().includes('sora'))
})

const voiceOptions = computed(() => voiceCatalog.map((voice) => ({
    label: voice.label,
    value: voice.value
})))

watch(
    modelOptions,
    () => {
        ensureImageModelSelection(settings.value)
        ensureImageModelSelection(batchDefaults.image)
    },
    { immediate: true }
)

watch(
    () => settings.value.imageProvider,
    () => {
        ensureImageModelSelection(settings.value, true)
    },
    { immediate: true }
)

watch(
    () => batchDefaults.image.imageProvider,
    () => {
        ensureImageModelSelection(batchDefaults.image, true)
    },
    { immediate: true }
)

watch(
    promptChannelModelOptions,
    () => {
        ensurePromptChannelDraftModels()
    },
    { immediate: true, deep: true }
)

watch(
    () => settings.value.promptChannel,
    (value) => {
        const normalized = normalizePromptChannel(value)
        if (normalized !== value) settings.value.promptChannel = normalized
    },
    { immediate: true }
)

watch(
    () => batchDefaults.image.promptChannel,
    (value) => {
        const normalized = normalizePromptChannel(value)
        if (normalized !== value) batchDefaults.image.promptChannel = normalized
    },
    { immediate: true }
)

watch(
    ttsModelOptions,
    (options) => {
        const list = options || []
        if (!list.length) {
            batchDefaults.audio.model = ''
            return
        }
        if (!list.some((o) => o.value === batchDefaults.audio.model)) batchDefaults.audio.model = list[0].value
    },
    { immediate: true }
)

watch(
    videoModelOptionsAll,
    (options) => {
        const list = options || []
        if (!list.length) {
            batchDefaults.video.model = ''
            return
        }
        if (!list.some((o) => o.value === batchDefaults.video.model)) batchDefaults.video.model = list[0].value
    },
    { immediate: true }
)

watch(
    digitalHumanModelOptions,
    (options) => {
        const list = options || []
        if (!list.length) {
            batchDefaults.digital_human.model = ''
            return
        }
        if (!list.some((o) => o.value === batchDefaults.digital_human.model)) batchDefaults.digital_human.model = list[0].value
    },
    { immediate: true }
)

watch(
    modelCatalog,
    () => {
        ensureUserPoolModelDefaults(true)
    },
    { immediate: true }
)

const batchTypeOptions = computed(() => [
    { label: localeStore.t('batch.type_image'), value: 'image' },
    { label: localeStore.t('batch.type_audio'), value: 'audio' },
    { label: localeStore.t('batch.type_video'), value: 'video' },
    { label: localeStore.t('batch.type_digital_human'), value: 'digital_human' }
])

const digitalHumanResolutionOptions = [
    { label: '480P', value: 480 }
]

const digitalHumanProviderOptions = computed(() => [
    { label: localeStore.t('batch.dh_provider_auto'), value: 'auto' },
    { label: localeStore.t('batch.dh_provider_dashscope'), value: 'dashscope' }
])

const digitalHumanStyleOptions = computed(() => [
    { label: localeStore.t('batch.dh_style_speech'), value: 'speech' },
    { label: localeStore.t('batch.dh_style_sing'), value: 'sing' },
    { label: localeStore.t('batch.dh_style_performance'), value: 'performance' }
])

const getSubjectLabel = (v) => subjectOptions.value.find(o=>o.value===v)?.label || v
const getQualityLabel = (v) => qualityOptions.value.find(o=>o.value===v)?.label || v
const tSettings = (key, fallback) => {
    const val = localeStore.t(key)
    return val === key ? fallback : val
}
const getPlatformLabel = (platform) => {
    const value = String(platform || '').trim().toLowerCase()
    if (value === 'vector') return tSettings('settings.model_platform_vector', 'ReOpenInnoLab')
    if (value === 'bailian') return tSettings('settings.model_platform_bailian', '阿里百炼')
    if (value === 'ark') return tSettings('settings.model_platform_ark', '火山方舟')
    return value || '—'
}

const modelViewModes = computed(() => [
    { id: 'service', label: tSettings('settings.model_view_service', '按功能') },
    { id: 'platform', label: tSettings('settings.model_view_platform', '按平台') }
])

const modelServiceGroups = computed(() => [
    { id: 'image', label: tSettings('settings.model_service_image', '绘图') },
    { id: 'video', label: tSettings('settings.model_service_video', '视频') },
    { id: 'audio', label: tSettings('settings.model_service_audio', '音频') },
    { id: 'digital_human', label: tSettings('settings.model_service_dh', '数字人') },
    { id: 'prompt', label: tSettings('settings.model_service_prompt', '提示词优化') }
])

const systemPoolServiceGroups = computed(() => [
    { id: 'image', label: tSettings('settings.key_pool_service_image', '绘图') },
    { id: 'prompt', label: tSettings('settings.key_pool_service_prompt', '提示词优化') },
    { id: 'audio', label: tSettings('settings.key_pool_service_audio', '音频') },
    { id: 'video', label: tSettings('settings.model_service_video', '视频') },
    { id: 'digital_human', label: tSettings('settings.key_pool_service_dh', '数字人') }
])

const modelPlatformGroups = computed(() => [
    { id: 'vector', label: tSettings('settings.model_platform_vector', 'ReOpenInnoLab') },
    { id: 'bailian', label: tSettings('settings.model_platform_bailian', '阿里百炼') },
    { id: 'ark', label: tSettings('settings.model_platform_ark', '火山方舟') }
])

const modelViewMode = ref('service')
const activeModelGroup = ref('image')
const activeSystemPoolService = ref('image')

watch(
    modelViewMode,
    (mode) => {
        activeModelGroup.value = mode === 'platform' ? 'vector' : 'image'
    },
    { immediate: true }
)

const buildGroupStats = (groups, type) => {
    const list = systemModels.value || []
    return (groups || []).map((group) => {
        const count = list.filter((item) => {
            if (type === 'platform') return normalizeModelPlatform(item) === group.id
            return String(item?.service || 'image').trim().toLowerCase() === group.id
        }).length
        return { ...group, count }
    })
}

const activeModelGroups = computed(() => (
    modelViewMode.value === 'platform'
        ? buildGroupStats(modelPlatformGroups.value, 'platform')
        : buildGroupStats(modelServiceGroups.value, 'service')
))

const systemModelsWithIndex = computed(() => (systemModels.value || []).map((item, index) => ({ item, index })))
const systemKeyPoolsWithIndex = computed(() => (systemKeyPools.value || []).map((item, index) => ({ item, index })))

const filteredSystemKeyPools = computed(() => {
    const service = String(activeSystemPoolService.value || 'image').trim().toLowerCase()
    return systemKeyPoolsWithIndex.value.filter(({ item }) => String(item?.service || 'image').trim().toLowerCase() === service)
})

const systemPoolStats = computed(() => {
    const pools = systemKeyPools.value || []
    const total = pools.length
    const enabled = pools.filter((pool) => pool?.enabled !== false).length
    const unconfigured = pools.filter((pool) => !isPoolCompleted(pool)).length
    return { total, enabled, unconfigured }
})

const renderModelGroups = computed(() => {
    const list = systemModelsWithIndex.value
    if (modelViewMode.value === 'platform') {
        const platform = normalizePlatform(activeModelGroup.value)
        const filtered = list.filter(({ item }) => normalizeModelPlatform(item) === platform)
        return modelServiceGroups.value.map((group) => ({
            id: group.id,
            label: group.label,
            items: filtered.filter(({ item }) => String(item?.service || 'image').trim().toLowerCase() === group.id)
        }))
    }
    const service = String(activeModelGroup.value || '').trim().toLowerCase()
    const label = modelServiceGroups.value.find((group) => group.id === service)?.label || service
    return [
        {
            id: service,
            label,
            items: list.filter(({ item }) => String(item?.service || 'image').trim().toLowerCase() === service)
        }
    ]
})

const modelTestStates = reactive({})
const modelTestLoading = reactive({})
const DEFAULT_MODEL_TEST_IMAGE_URL = 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/0b/Portrait_of_a_woman_%28cropped%29.jpg/1024px-Portrait_of_a_woman_%28cropped%29.jpg'
const DEFAULT_MODEL_TEST_AUDIO_URL = 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3'

const normalizeTestUrl = (url) => {
    if (!url) return ''
    if (url.startsWith('http://') || url.startsWith('https://')) return url
    return `${window.location.origin}${url.startsWith('/') ? '' : '/'}${url}`
}

const buildModelTestPayload = (entry) => {
    const item = entry?.item || {}
    return {
        service: item.service || 'image',
        model: item.model,
        platform: item.platform,
        api_key: item.api_key,
        backup_keys: Array.isArray(item.backup_keys)
            ? item.backup_keys
            : String(item.backup_keys || '')
                .split('\n')
                .map((v) => v.trim())
                .filter(Boolean),
        base_url: item.base_url
    }
}

const runModelTest = async (entry) => {
    const item = entry?.item || {}
    const model = String(item.model || '').trim()
    if (!model) {
        message.warning(tSettings('settings.model_id_required', '请填写 Model ID'))
        return
    }
    if (modelTestLoading[entry.index]) return
    modelTestLoading[entry.index] = true
    modelTestStates[entry.index] = {
        status: 'running',
        message: tSettings('settings.model_test_running', '测试中...')
    }

    try {
        if (!authStore.token) {
            throw new Error(tSettings('auth.login_required', '登录已过期，请重新登录'))
        }
        const payload = buildModelTestPayload(entry)
        const service = payload.service
        const modelLower = String(model || '').toLowerCase()
        const videoNeedsImage = service === 'video' && (modelLower.includes('sora') || modelLower.includes('i2v') || modelLower.includes('wanx') || modelLower.includes('wan2.'))
        if (service === 'digital_human') {
            payload.image_url = DEFAULT_MODEL_TEST_IMAGE_URL
            payload.audio_url = DEFAULT_MODEL_TEST_AUDIO_URL
        } else if (videoNeedsImage) {
            payload.image_url = DEFAULT_MODEL_TEST_IMAGE_URL
            payload.prompt = tSettings('settings.model_test_prompt_default', '测试生成内容')
        } else {
            payload.prompt = service === 'audio'
                ? tSettings('settings.model_test_prompt_audio_default', '这是一次模型连通性测试')
                : tSettings('settings.model_test_prompt_default', '测试生成内容')
        }

        const authHeaders = authStore.token ? { Authorization: `Bearer ${authStore.token}` } : {}
        const res = await api.post('/api/admin/model_test', payload, { headers: authHeaders })
        const data = res?.data || {}
        let messageText = tSettings('settings.model_test_success', '测试成功')
        let url = ''
        if (data?.result?.url) {
            url = normalizeTestUrl(data.result.url)
            messageText = tSettings('settings.model_test_success', '测试成功')
        } else if (data?.result?.task_id || data?.result?.taskId) {
            const taskId = data.result.task_id || data.result.taskId
            messageText = `${tSettings('settings.model_test_submitted', '已提交任务')}: ${taskId}`
        } else if (data?.result?.text) {
            messageText = `${tSettings('settings.model_test_success', '测试成功')}: ${data.result.text.slice(0, 60)}`
        }
        modelTestStates[entry.index] = {
            status: 'success',
            message: messageText,
            url
        }
    } catch (e) {
        const detail = e?.response?.data?.detail || e?.message || tSettings('settings.model_test_failed', '测试失败')
        modelTestStates[entry.index] = {
            status: 'error',
            message: `${tSettings('settings.model_test_failed', '测试失败')}: ${detail}`
        }
    } finally {
        modelTestLoading[entry.index] = false
    }
}

const getVideoCreditCost = (model) => {
    if (!model) return 0
    const match = modelCatalog.value.find((item) => item?.service === 'video' && item?.model === model)
    if (match && Number.isFinite(Number(match.cost))) return Number(match.cost)
    const text = String(model || '').trim().toLowerCase()
    if (text.includes('veo')) return 10
    if (text.includes('sora')) return 10
    if (text.includes('doubao') || text.includes('seedance')) return 5
    return 5
}

const formatVideoCostHint = (cost) => {
    const template = localeStore.t('video.cost_hint')
    if (template === 'video.cost_hint') return `本次生成预计消耗 ${cost} 积分`
    return template.replace('{cost}', cost)
}

const batchVideoCostHint = computed(() => formatVideoCostHint(getVideoCreditCost(batchDefaults.video.model)))
const batchVideoRequiresImage = computed(() => {
    const mode = batchDefaults.video.mode || 'text'
    const model = String(batchDefaults.video.model || '').trim().toLowerCase()
    return mode === 'image' || model.includes('sora') || model.includes('i2v') || model.includes('wanx') || model.includes('wan2.')
})
watch(
    () => [batchDefaults.video.mode, batchDefaults.video.model],
    ([mode, model]) => {
        if (mode !== 'image' && String(model || '').toLowerCase().includes('sora')) {
            batchDefaults.video.model = defaultVideoModel.value
        }
        if (mode !== 'image' && (String(model || '').toLowerCase().includes('i2v') || String(model || '').toLowerCase().includes('wanx') || String(model || '').toLowerCase().includes('wan2.'))) {
            batchDefaults.video.mode = 'image'
        }
    }
)

const showAudioSettings = computed(() => batchType.value === 'audio')

const reversedBatchQueue = computed(() => [...batchQueue.value].reverse())
const pendingCount = computed(() => batchQueue.value.filter((t) => t.status === 'pending' || t.status === 'draft').length)
const processingCount = computed(() => batchQueue.value.filter((t) => t.status === 'processing').length)
const doneCount = computed(() => batchQueue.value.filter((t) => t.status === 'done').length)
const failedCount = computed(() => batchQueue.value.filter((t) => t.status === 'failed').length)
const hasPending = computed(() => batchQueue.value.some(t => t.status === 'draft' || t.status === 'pending'))
const hasDone = computed(() => batchQueue.value.some(t => t.status === 'done'))
const hasDownloadable = computed(() => batchQueue.value.some((t) => {
    if (t.status !== 'done') return false
    if (Array.isArray(t.resultUrls) && t.resultUrls.some((url) => isLocalResultUrl(url))) return true
    return isLocalResultUrl(t.resultUrl)
}))
const recentHistory = computed(() => galleryImages.value.filter(i => i.is_mine).slice(0, 10))

const settingsTabs = computed(() => {
    const labelUser = localeStore.t('settings.tab_user')
    const labelModels = localeStore.t('settings.tab_models')
    const labelUsers = localeStore.t('settings.tab_users')
    const tabs = [{ id: 'user', label: labelUser === 'settings.tab_user' ? '用户设置' : labelUser }]
    if (authStore.user.username === 'admin') {
        tabs.push({ id: 'models', label: labelModels === 'settings.tab_models' ? '模型配置' : labelModels })
        tabs.push({ id: 'users', label: labelUsers === 'settings.tab_users' ? '用户管理' : labelUsers })
    }
    return tabs
})
const activeSettingsTab = ref('user')

const filteredGallery = computed(() => {
    let imgs = galleryImages.value
    if (galleryFilter.value !== 'all') imgs = imgs.filter(i => i.subject === galleryFilter.value)
    if (showMyImages.value) imgs = imgs.filter(i => i.is_mine)
    if (showFeaturedOnly.value) imgs = imgs.filter(i => i.featured)
    return imgs
})

// --- Auth ---
const handleAuthAction = async () => {
    if (!loginForm.username || !loginForm.password) return
    authLoading.value = true
    try {
        await authStore.login(loginForm.username, loginForm.password)
        message.success('Welcome')
        fetchHistory()
    } catch(e) { message.error('Auth failed') }
    finally { authLoading.value = false }
}
const handleGuestAccess = () => {
    authStore.enableGuestMode()
    fetchHistory()
}

const openUserSettings = () => {
    emit('update-tab', 'settings')
    activeSettingsTab.value = 'user'
}

// --- Actions ---
const resetSettings = () => {
    settings.value = {
        subject: 'general',
        grade: 'general',
        aspectRatio: '1:1',
        quality: 'standard',
        imageProvider: 'google',
        model: '',
        promptChannel: 'google',
        seedreamGroup: false,
        seedreamMaxImages: 4
    }
    ensureImageModelSelection(settings.value, true)
    refImageUrls.value = []
}

const applyUserPoolHeaders = (headers, service, model) => {
    let pool = selectUserPoolWithFallback(service, model)
    if ((!pool || !pool.key) && service === 'digital_human') {
        // Backward compatibility: existing DH keys may be stored under video service.
        pool = selectUserPoolWithFallback('video', model)
    }
    if (!pool?.key) return headers
    if (service === 'audio') {
        headers['x-tts-key'] = pool.key
        return headers
    }
    if (service === 'video' || service === 'digital_human') {
        headers['x-video-key'] = pool.key
        if (pool.base_url) headers['x-video-base-url'] = pool.base_url
        return headers
    }
    headers['x-model-key'] = pool.key
    if (pool.base_url) headers['x-model-base-url'] = pool.base_url
    return headers
}

const buildModelHeaders = (model) => {
    const headers = {}
    if (authStore.isLoggedIn && authStore.token) headers.Authorization = `Bearer ${authStore.token}`
    return applyUserPoolHeaders(headers, 'image', model)
}

const buildPromptHeaders = (model) => {
    const headers = {}
    if (authStore.isLoggedIn && authStore.token) headers.Authorization = `Bearer ${authStore.token}`
    return applyUserPoolHeaders(headers, 'prompt', model)
}

const buildTtsHeaders = (model) => {
    const headers = {}
    if (authStore.isLoggedIn && authStore.token) headers.Authorization = `Bearer ${authStore.token}`
    return applyUserPoolHeaders(headers, 'audio', model)
}

const buildVideoHeaders = (model, service = 'video') => {
    const headers = {}
    if (authStore.isLoggedIn && authStore.token) headers.Authorization = `Bearer ${authStore.token}`
    return applyUserPoolHeaders(headers, service, model)
}

const resolveImageSize = (ratio, model) => {
    const normalized = (model || '').toLowerCase()
    const isGpt = normalized.includes('gpt-image-1.5')
    if (isGpt) {
        if (ratio === '16:9') return '1536x1024'
        if (ratio === '9:16') return '1024x1536'
        if (ratio === '4:3') return '1536x1152'
        if (ratio === '3:4') return '1152x1536'
        return '1024x1024'
    }
    if (normalized.includes('seededit')) return 'adaptive'
    if (normalized.includes('seedream-4')) {
        if (ratio === '16:9') return '2560x1440'
        if (ratio === '9:16') return '1440x2560'
        if (ratio === '4:3') return '2304x1728'
        if (ratio === '3:4') return '1728x2304'
        return '2048x2048'
    }
    if (normalized.includes('seedream-3')) {
        if (ratio === '16:9') return '1280x720'
        if (ratio === '9:16') return '720x1280'
        if (ratio === '4:3') return '1152x864'
        if (ratio === '3:4') return '864x1152'
        return '1024x1024'
    }
    if (ratio === '16:9') return '1792x1024'
    if (ratio === '9:16') return '1024x1792'
    if (ratio === '4:3') return '1536x1152'
    if (ratio === '3:4') return '1152x1536'
    return '1024x1024'
}

const resolvePromptChannelByImageProvider = (provider) => {
    const normalized = normalizeImageProvider(provider)
    if (normalized === 'bytedance') return 'bytedance'
    if (normalized === 'aliyun') return 'aliyun'
    return 'google'
}

const requestOptimizedPrompt = async (
    prompt,
    subject,
    imageModel,
    imageProvider = settings.value.imageProvider,
    preferredPromptChannel = ''
) => {
    const channelHint = preferredPromptChannel || resolvePromptChannelByImageProvider(imageProvider)
    const normalizedChannel = normalizePromptChannel(channelHint)
    const promptModel = resolvePromptModel(normalizedChannel, imageModel)
    if (!promptModel) {
        throw new Error(tSettings('settings.model_required_prompt', '请先在模型配置中添加提示词优化模型'))
    }
    const res = await api.post(
        '/api/optimize_prompt',
        { prompt, subject, model: promptModel, channel: normalizedChannel },
        { headers: buildPromptHeaders(promptModel) }
    )
    if (!res?.data?.optimized_prompt) {
        throw new Error(res?.data?.detail || 'Optimization failed')
    }
    return res.data.optimized_prompt
}

const handleOptimizePrompt = async () => {
    if (!inputText.value.trim()) {
        message.warning('请输入提示词')
        return
    }
    optimizing.value = true
    const loadingMsg = message.loading('正在润色...', { duration: 0 })
    try {
        const original = inputText.value
        const optimized = await requestOptimizedPrompt(
            original,
            settings.value.subject,
            settings.value.model,
            settings.value.imageProvider,
            settings.value.promptChannel
        )
        if (optimized && optimized !== original) {
            inputText.value = optimized
            message.success('润色完成', { duration: 2000 })
        } else {
            message.info('润色无改动', { duration: 2000 })
        }
    } catch(e) {
        const detail = e?.response?.data?.detail || e?.message || '优化失败'
        message.error(`润色失败: ${detail}`, { duration: 3000 })
    }
    finally {
        loadingMsg.destroy()
        optimizing.value = false
    }
}

const buildSeedreamPayloadByModel = (model, cfg) => {
    const normalized = String(model || '').toLowerCase()
    if (!normalized.includes('seedream-4')) return {}
    return {
        seedream_group: !!cfg.seedreamGroup,
        seedream_max_images: cfg.seedreamMaxImages
    }
}

const generateImageWithFallback = async ({ prompt, cfg, referenceImageUrls = [] }) => {
    const normalizedProvider = normalizeImageProvider(cfg.imageProvider || settings.value.imageProvider)
    const modelChain = getImageModelChainByProvider(normalizedProvider, cfg.model)
    if (!modelChain.length) {
        throw new Error(tSettings('settings.model_required_image', '请先在模型配置中添加绘图模型'))
    }
    const failures = []
    for (const model of modelChain) {
        try {
            const payload = {
                prompt,
                size: resolveImageSize(cfg.aspectRatio, model),
                quality: cfg.quality,
                subject: cfg.subject,
                grade: cfg.grade,
                model,
                reference_image_urls: referenceImageUrls,
                ...buildSeedreamPayloadByModel(model, cfg)
            }
            const res = await api.post('/api/generate/single', payload, { headers: buildModelHeaders(model) })
            if (res?.data?.url || (Array.isArray(res?.data?.urls) && res.data.urls.length)) {
                return { data: res.data, model }
            }
            throw new Error(res?.data?.detail || 'Generation failed')
        } catch (e) {
            const detail = e?.response?.data?.detail || e?.message || 'Generation failed'
            failures.push(`${model}: ${detail}`)
        }
    }
    throw new Error(failures[failures.length - 1] || 'Generation failed')
}

const handleGenerateSingle = async () => {
    if (!inputText.value.trim()) return
    ensureImageModelSelection(settings.value)
    if (!settings.value.model) {
        message.warning(tSettings('settings.model_required_image', '请先在模型配置中添加绘图模型'))
        return
    }
    processing.value = true
    try {
        const result = await generateImageWithFallback({
            prompt: inputText.value,
            cfg: settings.value,
            referenceImageUrls: refImageUrls.value
        })
        settings.value.model = result.model
        currentDisplayImage.value = { ...result.data, is_mine: true, prompt: inputText.value, model: result.model }
        if (!authStore.isLoggedIn) {
            persistLocalImage({
                id: result.data?.id || `local_${Date.now()}`,
                url: result.data?.url || result.data?.urls?.[0],
                urls: Array.isArray(result.data?.urls) ? result.data.urls : undefined,
                prompt: inputText.value,
                enhanced_prompt: result.data?.enhanced_prompt,
                subject: settings.value.subject,
                grade: settings.value.grade,
                aspectRatio: settings.value.aspectRatio,
                imageProvider: settings.value.imageProvider,
                model: result.model,
                time: Date.now(),
                is_mine: true
            })
        }
        message.success('Generated')
        fetchHistory()
        authStore.checkAuth()
    } catch(e) {
        const status = e?.response?.status
        const detail = e?.response?.data?.detail || e?.message || 'Generation failed'
        if (status === 403 && /联系管理员/.test(detail)) {
            message.error(detail)
            return
        }
        if (status === 403 && /quota|余额|quota exceeded/i.test(detail)) {
            message.error(tSettings('settings.quota_exceeded', '余额不足，请联系管理员调整额度或配置模型 Key'))
            openUserSettings()
            return
        }
        if (status === 401) {
            message.error(detail || '未授权，请联系管理员')
            openUserSettings()
            return
        }
        message.error(`Generation failed: ${detail}`)
    }
    finally { processing.value = false }
}

const getLocalImageKey = (item) => item?.id || item?.url

const persistLocalImage = (entry) => {
    const normalized = {
        ...entry,
        id: entry?.id || `local_${Date.now()}`,
        url: entry?.url,
        thumbnail_url: entry?.thumbnail_url || entry?.url,
        is_mine: true
    }
    const updated = prependLocalHistory(IMAGE_HISTORY_KEY, normalized, { idResolver: getLocalImageKey })
    galleryImages.value = mergeLocalHistory(updated, galleryImages.value, { idResolver: getLocalImageKey })
}

const fetchHistory = async () => {
    if (!authStore.isLoggedIn && !authStore.isGuest) return
    try {
        const headers = authStore.isLoggedIn && authStore.token ? { Authorization: `Bearer ${authStore.token}` } : {}
        const res = await api.get('/api/gallery', { headers })
        const remoteImages = Array.isArray(res.data) ? res.data : []
        if (!authStore.isLoggedIn) {
            const localImages = loadLocalHistory(IMAGE_HISTORY_KEY)
            galleryImages.value = mergeLocalHistory(localImages, remoteImages, { idResolver: getLocalImageKey })
            return
        }
        galleryImages.value = remoteImages
    } catch(e) {}
}

const handleHistorySelect = (img) => currentDisplayImage.value = img
const openImage = (img) => {
    if (!img) return
    const urls = Array.isArray(img.urls) ? [...img.urls] : undefined
    selectedImage.value = { ...img, ...(urls ? { urls } : {}) }
    showModal.value = true
}
const closeModal = () => showModal.value = false
const copyPrompt = () => {
    const promptText = selectedImage.value?.enhanced_prompt || selectedImage.value?.prompt || ''
    if (!promptText) return
    navigator.clipboard.writeText(promptText)
    message.success(localeStore.t('image.copy_success'))
}
const openBatchImage = (task) => {
    if (!task?.resultUrl) return
    openImage({
        url: task.resultUrl,
        urls: task.resultUrls || undefined,
        prompt: task.prompt,
        subject: task.settings?.image?.subject || 'general',
        aspectRatio: task.settings?.image?.aspectRatio || '1:1',
        model: task.settings?.image?.model
    })
}

const handleDownload = () => {
    const img = currentDisplayImage.value
    if (!img?.url) return
    const link = document.createElement('a')
    link.href = img.url
    link.download = img.filename || `generated_${Date.now()}.png`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
}

const handleRedraw = () => {
    const img = currentDisplayImage.value
    if (!img) return
    inputText.value = img.prompt || inputText.value
    if (img.url) {
        refImageUrls.value = [img.url]
    }
    message.info(localeStore.t('image.redraw_hint') || 'Ready to redraw. Modify prompt and click Generate.')
}

const handleQuickRefine = async () => {
    if (!quickRefineText.value.trim() || !currentDisplayImage.value) return
    ensureImageModelSelection(settings.value)
    if (!settings.value.model) {
        message.warning(tSettings('settings.model_required_image', '请先在模型配置中添加绘图模型'))
        return
    }
    processing.value = true
    try {
        const result = await generateImageWithFallback({
            prompt: quickRefineText.value,
            cfg: settings.value,
            referenceImageUrls: [currentDisplayImage.value.url]
        })
        settings.value.model = result.model
        currentDisplayImage.value = { ...result.data, is_mine: true, prompt: quickRefineText.value, model: result.model }
        if (!authStore.isLoggedIn) {
            persistLocalImage({
                id: result.data?.id || `local_${Date.now()}`,
                url: result.data?.url || result.data?.urls?.[0],
                urls: Array.isArray(result.data?.urls) ? result.data.urls : undefined,
                prompt: quickRefineText.value,
                enhanced_prompt: result.data?.enhanced_prompt,
                subject: settings.value.subject,
                grade: settings.value.grade,
                aspectRatio: settings.value.aspectRatio,
                imageProvider: settings.value.imageProvider,
                model: result.model,
                time: Date.now(),
                is_mine: true
            })
        }
        
        // Sync to main editor
        inputText.value = quickRefineText.value
        if (result.data.url) {
            refImageUrls.value = [result.data.url]
        }

        quickRefineText.value = '' // Clear input
        message.success(localeStore.t('image.generated') || 'Generated')
        fetchHistory()
        authStore.checkAuth()
    } catch(e) {
        const detail = e?.response?.data?.detail || e?.message || 'Refine failed'
        message.error(`Refine failed: ${detail}`)
    } finally {
        processing.value = false
    }
}

const jumpToVideo = (img) => {
    if (!img?.url) return
    const basePrompt = img.prompt || img.enhanced_prompt || ''
    const defaultVideoPrompt = localeStore.t('image.to_video_prompt') || '在该图基础上做轻微镜头运动'
    const mergedPrompt = basePrompt ? `${basePrompt}。${defaultVideoPrompt}` : defaultVideoPrompt
    const payload = {
        image_url: img.url,
        prompt: mergedPrompt,
        aspect_ratio: img.aspectRatio || '',
        model: img.model || ''
    }
    try {
        localStorage.setItem(VIDEO_SEED_KEY, JSON.stringify(payload))
    } catch (e) {}
    emit('update-tab', 'video')
}

// Batch
const makeBatchId = () => {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
    return `${Date.now()}_${Math.random().toString(16).slice(2)}`
}
const cloneDeep = (value) => JSON.parse(JSON.stringify(value))
const isLocalResultUrl = (url) => typeof url === 'string' && url.startsWith('/static/')
const normalizeAvatarFilename = (value) => {
    const raw = String(value || '').trim()
    if (!raw) return ''
    let cleaned = raw.split('#')[0].split('?')[0].trim()
    try {
        cleaned = decodeURIComponent(cleaned)
    } catch (e) {}
    const normalized = cleaned.replace(/\\/g, '/')
    const parts = normalized.split('/').filter(Boolean)
    return (parts[parts.length - 1] || '').trim()
}
const normalizeAvatarInputUrl = (value) => {
    const raw = String(value || '').trim()
    if (!raw) return ''
    if (/^(https?:)?\/\//i.test(raw)) return raw
    if (raw.startsWith('/static/uploads/')) {
        const filename = normalizeAvatarFilename(raw)
        return filename ? `/static/uploads/${encodeURIComponent(filename)}` : raw
    }
    if (raw.startsWith('/')) return raw
    const filename = normalizeAvatarFilename(raw)
    return `/static/uploads/${encodeURIComponent(filename || raw)}`
}
const getUploadsImageList = async (force = false) => {
    const now = Date.now()
    if (!force && now - Number(batchUploadImagesCache.value?.ts || 0) < 30000) {
        return Array.isArray(batchUploadImagesCache.value?.items) ? batchUploadImagesCache.value.items : []
    }
    try {
        const res = await api.get('/api/uploads')
        const items = Array.isArray(res?.data?.images) ? res.data.images : []
        batchUploadImagesCache.value = { ts: now, items }
        return items
    } catch (e) {
        return Array.isArray(batchUploadImagesCache.value?.items) ? batchUploadImagesCache.value.items : []
    }
}
const extractFilenameFromUrl = (url) => {
    if (!url) return ''
    return normalizeAvatarFilename(url)
}
const resolveAvatarUrlForTask = (value, uploadedImages = [], fallbackAvatarUrl = '') => {
    const normalized = normalizeAvatarInputUrl(value)
    if (!normalized) return ''
    if (/^(https?:)?\/\//i.test(normalized)) return normalized
    if (!normalized.startsWith('/static/uploads/')) return normalized
    const targetName = extractFilenameFromUrl(normalized)
    if (!targetName) return normalized
    const match = uploadedImages.find((item) => {
        const itemName = String(item?.name || '').trim()
        if (itemName && itemName === targetName) return true
        const urlName = extractFilenameFromUrl(item?.url || '')
        return urlName && urlName === targetName
    })
    if (match?.url) return match.url
    const fallback = normalizeAvatarInputUrl(fallbackAvatarUrl)
    if (fallback) return fallback
    return normalized
}
const normalizeBatchType = (value) => {
    const normalized = String(value || '').trim().toLowerCase().replace(/[-\s]/g, '_')
    if (normalized === 'digitalhuman' || normalized === 'dh') return 'digital_human'
    if (['image', 'audio', 'video', 'digital_human'].includes(normalized)) return normalized
    return batchType.value
}

const inferBatchTypeFromRaw = (raw) => {
    if (!raw || typeof raw !== 'object') return ''
    if (raw.digital_human || raw.avatarUrl || raw.avatar_url || raw.audio_model) return 'digital_human'
    if (
        raw.video ||
        raw.image_url ||
        raw.imageUrl ||
        raw.duration_seconds ||
        raw.durationSeconds ||
        raw.aspect_ratio ||
        raw.aspectRatio ||
        raw.mode ||
        raw.resolution ||
        raw.video_model ||
        raw.videoModel
    ) return 'video'
    if (raw.audio || raw.voice || raw.language_type || raw.instructions) return 'audio'
    return ''
}

const buildBatchTask = (raw) => {
    const baseSettings = {
        image: cloneDeep(batchDefaults.image),
        video: cloneDeep(batchDefaults.video),
        audio: cloneDeep(batchDefaults.audio),
        digital_human: cloneDeep(batchDefaults.digital_human)
    }

    let prompt = ''
    let type = batchType.value
    let explicitType = ''

    if (typeof raw === 'string') {
        prompt = raw
    } else if (raw && typeof raw === 'object') {
        if (raw.type) {
            explicitType = normalizeBatchType(raw.type)
            type = explicitType
        }
        const inferredType = inferBatchTypeFromRaw(raw)
        if (!explicitType && inferredType) type = inferredType
        prompt = raw.prompt || raw.text || ''

        if (raw.image && typeof raw.image === 'object') Object.assign(baseSettings.image, raw.image)
        if (raw.video && typeof raw.video === 'object') Object.assign(baseSettings.video, raw.video)
        if (raw.audio && typeof raw.audio === 'object') Object.assign(baseSettings.audio, raw.audio)
        if (raw.digital_human && typeof raw.digital_human === 'object') Object.assign(baseSettings.digital_human, raw.digital_human)

        const imageKeys = ['subject', 'grade', 'aspectRatio', 'quality', 'imageProvider', 'model', 'promptChannel', 'optimize', 'seedreamGroup', 'seedreamMaxImages']
        imageKeys.forEach((key) => {
            if (raw[key] !== undefined && raw[key] !== null) baseSettings.image[key] = raw[key]
        })
        const imageSnakeMap = {
            aspect_ratio: 'aspectRatio',
            seedream_group: 'seedreamGroup',
            seedream_max_images: 'seedreamMaxImages'
        }
        Object.entries(imageSnakeMap).forEach(([fromKey, toKey]) => {
            if (raw[fromKey] !== undefined && raw[fromKey] !== null) baseSettings.image[toKey] = raw[fromKey]
            if (raw.image && raw.image[fromKey] !== undefined && raw.image[fromKey] !== null) baseSettings.image[toKey] = raw.image[fromKey]
        })
        if (!baseSettings.image.imageProvider && baseSettings.image.model) {
            baseSettings.image.imageProvider = inferImageProviderFromModel(baseSettings.image.model)
        }
        baseSettings.image.imageProvider = normalizeImageProvider(baseSettings.image.imageProvider)
        ensureImageModelSelection(baseSettings.image)
        baseSettings.image.promptChannel = normalizePromptChannel(baseSettings.image.promptChannel)

        if (type === 'audio') {
            const audioKeys = ['voice', 'model', 'language_type', 'instructions', 'optimize_instructions']
            audioKeys.forEach((key) => {
                if (raw[key] !== undefined && raw[key] !== null) baseSettings.audio[key] = raw[key]
            })
        }
        if (type === 'digital_human') {
            const audioKeys = ['voice', 'language_type', 'instructions', 'optimize_instructions']
            audioKeys.forEach((key) => {
                if (raw[key] !== undefined && raw[key] !== null) baseSettings.audio[key] = raw[key]
            })
            if (raw.audio_model !== undefined && raw.audio_model !== null) {
                baseSettings.audio.model = raw.audio_model
            }
        }

        if (type === 'video') {
            const videoKeys = ['mode', 'model', 'aspectRatio', 'resolution', 'durationSeconds', 'imageUrl']
            videoKeys.forEach((key) => {
                if (raw[key] !== undefined && raw[key] !== null) baseSettings.video[key] = raw[key]
            })
            const snakeMap = {
                aspect_ratio: 'aspectRatio',
                duration_seconds: 'durationSeconds',
                image_url: 'imageUrl'
            }
            Object.entries(snakeMap).forEach(([fromKey, toKey]) => {
                if (raw[fromKey] !== undefined && raw[fromKey] !== null) baseSettings.video[toKey] = raw[fromKey]
                if (raw.video && raw.video[fromKey] !== undefined && raw.video[fromKey] !== null) baseSettings.video[toKey] = raw.video[fromKey]
            })
        }

        if (type === 'digital_human') {
            const dhKeys = ['avatarUrl', 'resolution', 'style', 'model', 'provider']
            dhKeys.forEach((key) => {
                if (raw[key] !== undefined && raw[key] !== null) baseSettings.digital_human[key] = raw[key]
            })
            const dhSnakeMap = {
                avatar_url: 'avatarUrl'
            }
            Object.entries(dhSnakeMap).forEach(([fromKey, toKey]) => {
                if (raw[fromKey] !== undefined && raw[fromKey] !== null) baseSettings.digital_human[toKey] = raw[fromKey]
                if (raw.digital_human && raw.digital_human[fromKey] !== undefined && raw.digital_human[fromKey] !== null) {
                    baseSettings.digital_human[toKey] = raw.digital_human[fromKey]
                }
            })
            if (baseSettings.digital_human.avatarUrl) {
                baseSettings.digital_human.avatarUrl = normalizeAvatarInputUrl(baseSettings.digital_human.avatarUrl)
            }
        }
    }

    if (!prompt || !prompt.trim()) return null

    return {
        id: makeBatchId(),
        type,
        prompt: prompt.trim(),
        status: 'draft',
        settings: baseSettings,
        resultUrl: '',
        resultType: '',
        resultMime: '',
        error: '',
        optimizedPrompt: '',
        optimizationError: '',
        phase: ''
    }
}

const getBatchTypeLabel = (type) => {
    if (type === 'audio') return localeStore.t('batch.type_audio')
    if (type === 'video') return localeStore.t('batch.type_video')
    if (type === 'digital_human') return localeStore.t('batch.type_digital_human')
    return localeStore.t('batch.type_image')
}

const formatDigitalHumanStyle = (value) => {
    if (value === 'speech') return localeStore.t('batch.dh_style_speech')
    if (value === 'sing') return localeStore.t('batch.dh_style_sing')
    if (value === 'performance') return localeStore.t('batch.dh_style_performance')
    return value || localeStore.t('batch.dh_style_speech')
}

const formatDigitalHumanProvider = (value) => {
    if (!value || value === 'auto') return localeStore.t('batch.dh_provider_auto')
    if (value === 'dashscope') return localeStore.t('batch.dh_provider_dashscope')
    return value
}

const getBatchPhaseLabel = (task) => {
    if (!task || task.type !== 'digital_human' || task.status !== 'processing') return ''
    if (task.phase === 'tts') return '阶段 1/3：生成音频'
    if (task.phase === 'submit') return '阶段 2/3：提交数字人'
    if (task.phase === 'render') return '阶段 3/3：渲染视频'
    return ''
}

const getBatchTags = (task) => {
    if (task.type === 'audio') {
        return [
            task.settings?.audio?.voice || 'Voice',
            task.settings?.audio?.model || 'TTS'
        ]
    }
    if (task.type === 'video') {
        const tags = []
        const mode = task.settings?.video?.mode === 'image'
            ? localeStore.t('video.image_mode')
            : localeStore.t('video.text_mode')
        tags.push(mode)
        if (task.settings?.video?.aspectRatio) tags.push(task.settings.video.aspectRatio)
        if (task.settings?.video?.durationSeconds) tags.push(`${task.settings.video.durationSeconds}s`)
        return tags
    }
    if (task.type === 'digital_human') {
        const tags = []
        tags.push(formatDigitalHumanProvider(task.settings?.digital_human?.provider))
        if (task.settings?.digital_human?.resolution) tags.push(`${task.settings.digital_human.resolution}P`)
        tags.push(formatDigitalHumanStyle(task.settings?.digital_human?.style))
        if (task.settings?.audio?.voice) tags.push(task.settings.audio.voice)
        return tags
    }
    const tags = [
        task.settings?.image?.aspectRatio || '1:1',
        getSubjectLabel(task.settings?.image?.subject || 'general')
    ]
    const imageModel = String(task.settings?.image?.model || '').toLowerCase()
    if (imageModel.includes('seedream-4') && task.settings?.image?.seedreamGroup) {
        const maxImages = task.resultUrls?.length || task.settings?.image?.seedreamMaxImages
        const label = tSettings('settings.seedream_group', 'Seedream 组图')
        tags.push(maxImages ? `${label}×${maxImages}` : label)
    }
    return tags
}

const handleJsonUpload = (e) => {
    const file = e.target.files[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
        try {
            const data = JSON.parse(ev.target.result)
            const items = Array.isArray(data) ? data : (Array.isArray(data?.tasks) ? data.tasks : [])
            if (!items.length) {
                message.error('Invalid JSON')
                return
            }
            const tasks = items.map(buildBatchTask).filter(Boolean)
            if (tasks.length) {
                batchQueue.value.push(...tasks)
                message.success(`Added ${tasks.length} tasks`)
            }
        } catch (err) {
            message.error('Invalid JSON')
        }
    }
    reader.readAsText(file)
}

const downloadTemplate = () => {
    let template = []
    if (batchType.value === 'audio') {
        template = [
            {
                type: 'audio',
                prompt: '示例音频文案：大家好，今天我们学习分数加减法。',
                audio: {
                    voice: 'Cherry',
                    model: batchDefaults.audio.model || '',
                    language_type: 'Auto'
                }
            },
            {
                type: 'audio',
                prompt: '示例音频文案：请完成第 3 页到第 5 页练习题。',
                audio: {
                    voice: 'Cherry',
                    model: batchDefaults.audio.model || '',
                    language_type: 'Auto',
                    instructions: '语速稍慢，语气亲切',
                    optimize_instructions: true
                }
            }
        ]
    } else if (batchType.value === 'video') {
        const fallbackVideoModel = batchDefaults.video.model || defaultVideoModel.value || ''
        const soraOption = (videoModelOptionsAll.value || []).find((option) => String(option.value).toLowerCase().includes('sora'))
        template = [
            {
                type: 'video',
                prompt: '示例视频提示词：清晨校园航拍，阳光穿过树叶，慢速推镜。',
                video: {
                    mode: 'text',
                    model: fallbackVideoModel,
                    aspectRatio: '16:9',
                    resolution: '720p',
                    durationSeconds: 8
                }
            },
            {
                type: 'video',
                prompt: '示例图生视频提示词：让画面中的人物微笑并轻轻抬手致意。',
                video: {
                    mode: 'image',
                    model: fallbackVideoModel,
                    aspectRatio: '16:9',
                    resolution: '720p',
                    durationSeconds: 8,
                    imageUrl: 'https://your-domain.com/static/uploads/your_reference.png'
                }
            }
        ]
        if (soraOption?.value) {
            template.push({
                type: 'video',
                prompt: 'Sora 示例：在原图基础上添加轻微运镜与自然光变化。',
                video: {
                    mode: 'image',
                    model: soraOption.value,
                    aspectRatio: '9:16',
                    resolution: '1080p',
                    durationSeconds: 10,
                    imageUrl: 'https://your-domain.com/static/uploads/your_reference.png'
                }
            })
        }
    } else if (batchType.value === 'digital_human') {
        template = [
            {
                type: 'digital_human',
                prompt: '示例数字人脚本：大家好，我是今天的讲解员，让我们开始吧。'
            },
            {
                type: 'digital_human',
                prompt: '示例数字人脚本：今天我们学习闭环控制在机器人抓取中的应用。'
            }
        ]
    } else {
        const imageProvider = normalizeImageProvider(batchDefaults.image.imageProvider || settings.value.imageProvider)
        const imageModel = getImageModelChainByProvider(imageProvider, batchDefaults.image.model || settings.value.model)[0] || ''
        const isSeedreamTemplate = String(imageModel || '').toLowerCase().includes('seedream-4')
        const imageTemplate = {
            subject: 'math',
            aspectRatio: '1:1',
            quality: 'standard',
            imageProvider,
            model: imageModel,
            optimize: true
        }
        if (isSeedreamTemplate) {
            imageTemplate.seedreamGroup = false
            imageTemplate.seedreamMaxImages = 4
        }
        template = [
            {
                type: 'image',
                prompt: '示例图片提示词',
                image: imageTemplate
            }
        ]
    }
    const data = JSON.stringify(template, null, 2)
    const blob = new Blob([data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `batch_${batchType.value}_template.json`
    a.click()
}

const requestTtsAudio = async (text, audioSettings) => {
    if (!audioSettings?.model) {
        throw new Error(tSettings('settings.model_required_audio', '请先在模型配置中添加音频模型'))
    }
    const payload = {
        text: text.trim(),
        voice: audioSettings.voice,
        model: audioSettings.model,
        language_type: audioSettings.language_type || 'Auto'
    }
    if (audioSettings.instructions && audioSettings.instructions.trim()) {
        payload.instructions = audioSettings.instructions.trim()
        payload.optimize_instructions = audioSettings.optimize_instructions !== false
    }
    const res = await api.post('/api/audio/tts', payload, { headers: buildTtsHeaders(audioSettings.model) })
    if (!res?.data?.success) {
        throw new Error(res?.data?.detail || 'TTS failed')
    }
    return { url: res.data.url, type: res.data.type || 'audio/wav', duration: res.data.duration }
}

const runImageTask = async (task) => {
    const cfg = task.settings?.image || batchDefaults.image
    ensureImageModelSelection(cfg)
    if (!cfg.model) {
        throw new Error(tSettings('settings.model_required_image', '请先在模型配置中添加绘图模型'))
    }
    let promptToUse = task.prompt
    if (cfg.optimize) {
        try {
            promptToUse = await requestOptimizedPrompt(
                task.prompt,
                cfg.subject,
                cfg.model,
                cfg.imageProvider || settings.value.imageProvider,
                cfg.promptChannel || settings.value.promptChannel
            )
            task.optimizedPrompt = promptToUse
        } catch (e) {
            task.optimizationError = e?.response?.data?.detail || e?.message || ''
        }
    }
    const result = await generateImageWithFallback({ prompt: promptToUse, cfg })
    cfg.model = result.model
    task.resultUrl = result.data.url || result.data.urls?.[0] || ''
    task.resultUrls = Array.isArray(result.data.urls) && result.data.urls.length > 1 ? result.data.urls : null
    if (!task.resultUrl) throw new Error(result.data?.detail || 'Image generation failed')
    task.resultType = 'image'
}

const runAudioTask = async (task) => {
    const audio = await requestTtsAudio(task.prompt, task.settings?.audio || batchDefaults.audio)
    task.resultUrl = audio.url
    task.resultType = 'audio'
    task.resultMime = audio.type
    authStore.checkAuth()
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const pollDigitalHumanStatus = async (taskId, model) => {
    const maxAttempts = 60
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
        if (attempt > 0) await sleep(5000)
        const res = await api.get(`/api/digital_human/status/${taskId}`, {
            params: { model },
            headers: buildVideoHeaders(model, 'digital_human')
        })
        const data = res?.data?.data || {}
        const status = data.status
        if (status === 'done' && data.video_url) return data.video_url
        if (status === 'expired' && !data.error_message) {
            throw new Error('任务ID无效或已过期，请重新提交任务。')
        }
        if (status === 'failed' || status === 'expired') {
            throw new Error(data.error_message || 'Digital human failed')
        }
    }
    throw new Error('Digital human timeout')
}

const pollVideoStatus = async (taskId, model) => {
    const maxAttempts = 60
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
        if (attempt > 0) await sleep(10000)
        const res = await api.get('/api/video/status', {
            params: { task_id: taskId },
            headers: buildVideoHeaders(model)
        })
        const data = res?.data?.data || {}
        const status = data.status
        if (status === 'done' && data.video_url) return data.video_url
        if (status === 'failed' || status === 'expired') {
            throw new Error(data.error_message || 'Video failed')
        }
    }
    throw new Error('Video timeout')
}

const runVideoTask = async (task) => {
    const videoSettings = task.settings?.video || batchDefaults.video
    if (!videoSettings.model) {
        throw new Error(tSettings('settings.model_required_video', '请先在模型配置中添加视频模型'))
    }
    const mode = videoSettings.mode || 'text'
    const isSoraModel = String(videoSettings.model || '').trim().toLowerCase().includes('sora')
    const needsImage = mode === 'image' || isSoraModel
    if (needsImage && !videoSettings.imageUrl) {
        throw new Error(localeStore.t('batch.error_missing_video_image'))
    }
    const durationSeconds = Number.isFinite(Number(videoSettings.durationSeconds))
        ? Number(videoSettings.durationSeconds)
        : undefined
    const payload = {
        mode,
        prompt: task.prompt,
        model: videoSettings.model,
        aspect_ratio: videoSettings.aspectRatio,
        resolution: videoSettings.resolution,
        duration_seconds: durationSeconds,
        image_url: needsImage ? videoSettings.imageUrl : null
    }
    const res = await api.post('/api/video/generate', payload, { headers: buildVideoHeaders(videoSettings.model) })
    const taskId = res?.data?.data?.task_id
    if (!taskId) throw new Error(res?.data?.detail || 'Video task failed')
    task.remoteTaskId = taskId
    authStore.checkAuth()
    const videoUrl = await pollVideoStatus(taskId, videoSettings.model)
    task.resultUrl = videoUrl
    task.resultType = 'video'
}

const runDigitalHumanTask = async (task) => {
    const dhSettings = task.settings?.digital_human || batchDefaults.digital_human
    const rawAvatarUrl = String(dhSettings.avatarUrl || '').trim()
    if (!rawAvatarUrl) {
        throw new Error(localeStore.t('batch.error_missing_avatar'))
    }
    if (!dhSettings.model) {
        throw new Error(tSettings('settings.model_required_dh', '请先在模型配置中添加数字人模型'))
    }
    const fallbackAvatarUrl = String(batchDefaults.digital_human?.avatarUrl || '').trim()
    const uploadedImages = await getUploadsImageList()
    const avatarUrl = resolveAvatarUrlForTask(rawAvatarUrl, uploadedImages, fallbackAvatarUrl)
    if (avatarUrl.startsWith('/static/uploads/')) {
        const targetName = extractFilenameFromUrl(avatarUrl)
        let exists = uploadedImages.some((item) => {
            const itemName = String(item?.name || '').trim()
            if (itemName && itemName === targetName) return true
            const urlName = extractFilenameFromUrl(item?.url || '')
            return urlName && urlName === targetName
        })
        if (!exists) {
            const latestUploads = await getUploadsImageList(true)
            exists = latestUploads.some((item) => {
                const itemName = String(item?.name || '').trim()
                if (itemName && itemName === targetName) return true
                const urlName = extractFilenameFromUrl(item?.url || '')
                return urlName && urlName === targetName
            })
        }
        if (!exists) {
            throw new Error(`找不到任务头像文件：${targetName}。请先上传该头像后再执行。`)
        }
    }

    task.phase = 'tts'
    const audio = await requestTtsAudio(task.prompt, task.settings?.audio || batchDefaults.audio)
    task.audioUrl = audio.url

    task.phase = 'submit'
    const submitRes = await api.post('/api/digital_human/submit', {
        image_url: avatarUrl,
        audio_url: audio.url,
        audio_duration: audio.duration,
        model: dhSettings.model,
        resolution: dhSettings.resolution,
        style: dhSettings.style
    }, { headers: buildVideoHeaders(dhSettings.model, 'digital_human') })
    const taskId = submitRes?.data?.data?.task_id
    if (!taskId) throw new Error(submitRes?.data?.message || 'Digital human task failed')

    task.remoteTaskId = taskId
    authStore.checkAuth()
    task.phase = 'render'
    const videoUrl = await pollDigitalHumanStatus(taskId, dhSettings.model)
    task.resultUrl = videoUrl
    task.resultType = 'video'
    task.phase = 'done'
}

const executeBatchTask = async (task) => {
    if (task.type === 'audio') return runAudioTask(task)
    if (task.type === 'video') return runVideoTask(task)
    if (task.type === 'digital_human') return runDigitalHumanTask(task)
    return runImageTask(task)
}

const startBatchProcessing = async () => {
    if (batchRunning.value) return
    const pending = batchQueue.value.filter((t) => t.status === 'draft' || t.status === 'pending')
    if (!pending.length) return
    batchStopRequested.value = false
    batchRunning.value = true
    pending.forEach((t) => {
        if (t.status === 'draft') t.status = 'pending'
    })

    for (const task of pending) {
        if (batchStopRequested.value) break
        task.status = 'processing'
        task.error = ''
        task.optimizedPrompt = ''
        task.optimizationError = ''
        task.phase = ''
        try {
            await executeBatchTask(task)
            task.status = 'done'
        } catch (e) {
            task.status = 'failed'
            task.error = e?.response?.data?.detail || e?.response?.data?.message || e?.response?.data?.error || e?.message || 'Failed'
        }
    }
    batchRunning.value = false
}

const pauseBatchProcessing = () => {
    if (!batchRunning.value) return
    batchStopRequested.value = true
}

const downloadBatchResults = async () => {
    if (batchDownloading.value) return
    const localUrls = batchQueue.value
        .filter((t) => t.status === 'done')
        .flatMap((t) => (Array.isArray(t.resultUrls) && t.resultUrls.length ? t.resultUrls : [t.resultUrl]))
        .filter((url) => isLocalResultUrl(url))
    if (!localUrls.length) {
        message.error(localeStore.t('batch.error_no_downloadable'))
        return
    }
    batchDownloading.value = true
    const loadingMsg = message.loading('正在打包下载，请稍候...', { duration: 0 })
    try {
        const filenames = [...new Set(localUrls.map((url) => decodeURIComponent(url.split('/').pop())))]
        const res = await api.post('/api/download/batch', { filenames }, { responseType: 'blob' })
        const blob = new Blob([res.data], { type: 'application/zip' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `batch_${Date.now()}.zip`
        a.click()
        setTimeout(() => URL.revokeObjectURL(url), 1500)
        message.success(`下载已开始（${filenames.length} 个文件）`)

        const skipped = batchQueue.value.filter((t) => {
            if (t.status !== 'done') return false
            const urls = Array.isArray(t.resultUrls) && t.resultUrls.length ? t.resultUrls : [t.resultUrl]
            return !urls.some((url) => isLocalResultUrl(url))
        })
        if (skipped.length) message.info(localeStore.t('batch.download_partial'))
    } catch (e) {
        let detail = e?.message || 'Download failed'
        const data = e?.response?.data
        if (data && typeof Blob !== 'undefined' && data instanceof Blob) {
            try {
                const text = await data.text()
                const parsed = text ? JSON.parse(text) : null
                detail = parsed?.detail || parsed?.message || detail
            } catch (_) {}
        } else if (data && typeof data === 'object') {
            detail = data.detail || data.message || detail
        }
        message.error(detail)
    } finally {
        loadingMsg.destroy()
        batchDownloading.value = false
    }
}

const handleBatchAvatarUpload = ({ event }) => {
    try {
        const res = JSON.parse(event.target.response)
        if (res.success) {
            batchDefaults.digital_human.avatarUrl = normalizeAvatarInputUrl(res.url)
            batchUploadImagesCache.value.ts = 0
            // Keep pending/draft digital-human tasks in sync with latest default avatar.
            batchQueue.value.forEach((task) => {
                if (task?.type !== 'digital_human') return
                if (!['draft', 'pending'].includes(task.status)) return
                if (!task.settings?.digital_human) task.settings = { ...(task.settings || {}), digital_human: {} }
                task.settings.digital_human.avatarUrl = normalizeAvatarInputUrl(res.url)
            })
        }
    } catch (e) {}
}

const handleBatchVideoImageUpload = ({ event }) => {
    try {
        const res = JSON.parse(event.target.response)
        if (res.success) batchDefaults.video.imageUrl = res.url
    } catch (e) {}
}

// Uploads
const handleUploadFinishWithStore = ({ file, event }) => {
    try {
        const res = JSON.parse(event.target.response)
        if (res.success) refImageUrls.value.push(res.url)
    } catch(e) {}
}

// User Pools
const normalizeUserPoolItem = (pool) => {
    const ordered = ['image', 'audio', 'video', 'digital_human', 'prompt']
    const service = pool?.service
        || ordered.find((item) => pool?.services?.includes?.(item))
        || 'image'
    const provider = (pool?.provider || '').toString().trim().toLowerCase()
    return {
        key: pool?.key || '',
        base_url: pool?.base_url || '',
        models: Array.isArray(pool?.models) ? pool.models.join(', ') : (pool?.models || ''),
        priority: Number.isFinite(pool?.priority) ? pool.priority : 100,
        enabled: pool?.enabled !== false,
        service,
        provider
    }
}

const loadUserKeyPools = () => {
    let pools = readUserKeyPools()
    if (!pools.length) {
        const legacy = buildLegacyPools()
        if (legacy.length) {
            saveUserKeyPools(legacy)
            pools = readUserKeyPools()
        }
    }
    const ordered = [...pools].sort((a, b) => (a.priority || 100) - (b.priority || 100))
    withUserPoolsDirtyLock(() => {
        userKeyPools.value = ordered.map(normalizeUserPoolItem)
        expandedUserPools.clear()
        if (userKeyPools.value.length) reorderUserKeyPools(false)
        userPoolsDirty.value = false
        ensureUserPoolModelDefaults(true)
    })
}

const addUserKeyPool = () => {
    userKeyPools.value.push({
        key: '',
        base_url: '',
        models: '',
        priority: 100,
        enabled: true,
        service: 'image',
        provider: ''
    })
    reorderUserKeyPools()
    userPoolsDirty.value = true
}

const getUserModelOptionsForService = (service) => {
    const normalized = String(service || '').trim().toLowerCase()
    const items = modelCatalog.value || []
    return items
        .filter((item) => !normalized || String(item?.service || '').trim().toLowerCase() === normalized)
        .map((item) => ({
            label: formatCatalogLabel(item, true),
            value: item.model
        }))
}

const handleUserServiceChange = (pool) => {
    const options = getUserModelOptionsForService(pool.service)
    if (!options.length) {
        return
    }
    const current = String(pool.models || '').trim()
    if (!current) {
        pool.models = options[0].value
    }
}

function ensureUserPoolModelDefaults(silent = false) {
    if (!userKeyPools.value.length) return
    const applyDefaults = () => {
        userKeyPools.value.forEach((pool) => {
            const options = getUserModelOptionsForService(pool.service)
            if (!options.length) return
            const current = String(pool.models || '').trim()
            if (!current) {
                pool.models = options[0].value
            }
        })
    }
    if (silent) {
        withUserPoolsDirtyLock(applyDefaults)
    } else {
        applyDefaults()
    }
}

const handleUserProviderChange = (pool) => {
    if (!pool) return
    const provider = normalizePlatform(pool.provider)
    const defaultUrl = USER_PROVIDER_BASE_URLS[provider]
    if (!defaultUrl) return
    const current = String(pool.base_url || '').trim()
    if (!current) {
        pool.base_url = defaultUrl
    }
}

const removeUserKeyPool = (idx) => {
    if (!confirmRemovePool(idx)) return
    userKeyPools.value.splice(idx, 1)
    expandedUserPools.delete(idx)
    const next = new Set()
    userKeyPools.value.forEach((_, i) => {
        if (expandedUserPools.has(i + 1)) next.add(i)
        if (expandedUserPools.has(i)) next.add(i)
    })
    expandedUserPools.clear()
    next.forEach((i) => expandedUserPools.add(i))
    reorderUserKeyPools()
    userPoolsDirty.value = true
}

const reorderUserKeyPools = (markDirty = true) => {
    userKeyPools.value.forEach((pool, index) => {
        pool.priority = (index + 1) * 10
    })
    if (markDirty) userPoolsDirty.value = true
}

const moveUserKeyPool = (idx, delta) => {
    const target = idx + delta
    if (target < 0 || target >= userKeyPools.value.length) return
    const list = userKeyPools.value
    const temp = list[idx]
    list[idx] = list[target]
    list[target] = temp
    const hasIdx = expandedUserPools.has(idx)
    const hasTarget = expandedUserPools.has(target)
    if (hasIdx || hasTarget) {
        expandedUserPools.delete(idx)
        expandedUserPools.delete(target)
        if (hasIdx) expandedUserPools.add(target)
        if (hasTarget) expandedUserPools.add(idx)
    }
    reorderUserKeyPools()
    userPoolsDirty.value = true
}

const toggleUserPoolExpand = (idx) => {
    if (expandedUserPools.has(idx)) expandedUserPools.delete(idx)
    else expandedUserPools.add(idx)
}

const serializeUserKeyPools = () => {
    const normalizeModels = (value) => {
        if (!value) return []
        if (Array.isArray(value)) return value.map(v => String(v).trim()).filter(Boolean)
        return String(value)
            .split(/[;,]/)
            .map(v => v.trim())
            .filter(Boolean)
    }
    return userKeyPools.value.map((pool) => ({
        key: (pool.key || '').trim(),
        base_url: (pool.base_url || '').trim(),
        models: normalizeModels(pool.models),
        priority: Number.isFinite(Number(pool.priority)) ? Number(pool.priority) : 100,
        enabled: pool.enabled !== false,
        services: [pool.service || 'image'],
        provider: (pool.provider || '').trim()
    })).filter((pool) => pool.key)
}

const handleSaveUserPools = () => {
    saveUserKeyPools(serializeUserKeyPools())
    userPoolsDirty.value = false
    message.success(localeStore.t('settings.save_success'))
    clearModelCatalogCache()
    loadModelCatalog()
}

// Admin
const parseKeyList = (value) => value.split('\n').map(v => v.trim()).filter(Boolean)
const normalizePoolItem = (pool) => {
    const ordered = ['image', 'audio', 'video', 'digital_human', 'prompt']
    const service = pool?.service
        || ordered.find((item) => pool?.services?.includes?.(item))
        || 'image'
    const provider = (pool?.provider || '').toString().trim().toLowerCase()
    const backupKeys = Array.isArray(pool?.backup_keys)
        ? pool.backup_keys.join('\n')
        : (pool?.backup_keys || '')
    return {
        key: pool?.key || '',
        base_url: pool?.base_url || '',
        models: Array.isArray(pool?.models) ? pool.models.join(', ') : (pool?.models || ''),
        priority: Number.isFinite(pool?.priority) ? pool.priority : 100,
        enabled: pool?.enabled !== false,
        service,
        provider,
        backup_keys: backupKeys
    }
}
const addKeyPool = () => {
    systemKeyPools.value.push({
        key: '',
        base_url: '',
        models: '',
        priority: 100,
        enabled: true,
        service: activeSystemPoolService.value || 'image',
        provider: '',
        backup_keys: ''
    })
    expandedPools.add(systemKeyPools.value.length - 1)
    reorderKeyPools()
    systemConfigDirty.value = true
}

const duplicateKeyPool = (idx) => {
    const source = systemKeyPools.value[idx]
    if (!source) return
    const copy = {
        key: source.key || '',
        base_url: source.base_url || '',
        models: source.models || '',
        priority: Number.isFinite(Number(source.priority)) ? Number(source.priority) : 100,
        enabled: source.enabled !== false,
        service: source.service || 'image',
        provider: source.provider || '',
        backup_keys: source.backup_keys || ''
    }
    systemKeyPools.value.splice(idx + 1, 0, copy)
    const next = new Set()
    expandedPools.forEach((i) => {
        next.add(i >= idx + 1 ? i + 1 : i)
    })
    next.add(idx + 1)
    expandedPools.clear()
    next.forEach((i) => expandedPools.add(i))
    reorderKeyPools()
    systemConfigDirty.value = true
}
const removeKeyPool = (idx) => {
    if (!confirmRemovePool(idx)) return
    systemKeyPools.value.splice(idx, 1)
    expandedPools.delete(idx)
    const next = new Set()
    systemKeyPools.value.forEach((_, i) => {
        if (expandedPools.has(i + 1)) next.add(i)
        if (expandedPools.has(i)) next.add(i)
    })
    expandedPools.clear()
    next.forEach((i) => expandedPools.add(i))
    reorderKeyPools()
    systemConfigDirty.value = true
}
const reorderKeyPools = () => {
    systemKeyPools.value.forEach((pool, index) => {
        pool.priority = (index + 1) * 10
    })
    systemConfigDirty.value = true
}
const moveKeyPool = (idx, delta) => {
    const target = idx + delta
    if (target < 0 || target >= systemKeyPools.value.length) return
    const list = systemKeyPools.value
    const temp = list[idx]
    list[idx] = list[target]
    list[target] = temp
    const hasIdx = expandedPools.has(idx)
    const hasTarget = expandedPools.has(target)
    if (hasIdx || hasTarget) {
        expandedPools.delete(idx)
        expandedPools.delete(target)
        if (hasIdx) expandedPools.add(target)
        if (hasTarget) expandedPools.add(idx)
    }
    reorderKeyPools()
    systemConfigDirty.value = true
}
const serializeKeyPools = () => {
    const normalizeModels = (value) => {
        if (!value) return []
        if (Array.isArray(value)) return value.map(v => String(v).trim()).filter(Boolean)
        return String(value)
            .split(/[;,]/)
            .map(v => v.trim())
            .filter(Boolean)
    }
    const normalizeKeyList = (value) => {
        if (!value) return []
        if (Array.isArray(value)) return value.map(v => String(v).trim()).filter(Boolean)
        return String(value)
            .split(/[\n,;]/)
            .map(v => v.trim())
            .filter(Boolean)
    }
    return systemKeyPools.value.map((pool) => ({
        key: (pool.key || '').trim(),
        base_url: (pool.base_url || '').trim(),
        models: normalizeModels(pool.models),
        backup_keys: normalizeKeyList(pool.backup_keys),
        priority: Number.isFinite(Number(pool.priority)) ? Number(pool.priority) : 100,
        enabled: pool.enabled !== false,
        services: [pool.service || 'image'],
        provider: (pool.provider || '').trim()
    })).filter((pool) => pool.key)
}

const handleSystemPoolProviderChange = (pool) => {
    if (!pool) return
    const provider = normalizePlatform(pool.provider)
    pool.provider = provider
    const defaultUrl = SYSTEM_PROVIDER_BASE_URLS[provider]
    if (defaultUrl) pool.base_url = defaultUrl
    systemConfigDirty.value = true
}

const togglePoolExpand = (idx) => {
    if (expandedPools.has(idx)) expandedPools.delete(idx)
    else expandedPools.add(idx)
}

const isPoolCompleted = (pool) => {
    return (pool?.key || '').trim().length > 0
}

const poolBackupKeyCount = (pool) => {
    return parseInlineList(pool?.backup_keys).length
}

const poolSummary = (pool) => {
    const modelText = (pool.models || '').toString().trim()
    const models = modelText ? modelText.split(/[;,]/).map(v => v.trim()).filter(Boolean) : []
    const serviceValue = pool.service || 'image'
    const serviceLabel = serviceValue === 'audio'
        ? tSettings('settings.key_pool_service_audio', '音频')
        : serviceValue === 'video'
            ? tSettings('settings.key_pool_service_video', '视频')
            : serviceValue === 'digital_human'
                ? tSettings('settings.key_pool_service_dh', '数字人')
            : serviceValue === 'prompt'
                ? tSettings('settings.key_pool_service_prompt', '提示词优化')
                : tSettings('settings.key_pool_service_image', '绘图')
    const providerValue = (pool.provider || '').toString().trim().toLowerCase()
    const providerLabel = providerValue === 'vector'
        ? tSettings('settings.key_pool_provider_vector', 'ReOpenInnoLab')
        : providerValue === 'bailian'
            ? tSettings('settings.key_pool_provider_bailian', '百炼')
            : providerValue === 'ark'
                ? tSettings('settings.key_pool_provider_ark', '火山方舟')
                : providerValue === 'gemini'
                    ? tSettings('settings.key_pool_provider_gemini', 'Gemini')
                    : providerValue === 'openai'
                        ? tSettings('settings.key_pool_provider_openai', 'GPT / OpenAI')
                        : providerValue === 'other'
                            ? tSettings('settings.key_pool_provider_other', '其他')
                            : tSettings('settings.key_pool_provider_any', '不限')
    const usageTextLabel = `用途:${serviceLabel}`
    const providerTextLabel = `通道:${providerLabel}`
    const modelTextLabel = models.length ? `模型:${models.join(',')}` : '模型:通用'
    return `${usageTextLabel} · ${providerTextLabel} · ${modelTextLabel}`
}

const confirmRemovePool = (idx) => {
    const promptText = localeStore.t('settings.key_pool_remove_confirm')
    const fallback = promptText === 'settings.key_pool_remove_confirm' ? '确认删除该账号池' : promptText
    return window.confirm(`${fallback} #${idx + 1}`)
}

const fetchSystemConfig = async () => {
    if (authStore.user.username !== 'admin') return
    try {
        const res = await api.get('/api/admin/system_config', {
            headers: authStore.token ? { Authorization: `Bearer ${authStore.token}` } : {}
        })
        systemImageKey.value = res.data.image?.api_key || ''
        systemImageBackupKeysInput.value = (res.data.image?.backup_keys || []).join('\n')
        systemImageBaseUrl.value = res.data.image?.base_url || ''
        systemTtsKey.value = res.data.tts?.api_key || ''
        systemTtsBackupKeysInput.value = (res.data.tts?.backup_keys || []).join('\n')
        systemTtsBaseUrl.value = res.data.tts?.base_url || ''
        systemVideoKey.value = res.data.video?.api_key || ''
        systemVideoBackupKeysInput.value = (res.data.video?.backup_keys || []).join('\n')
        systemVideoBaseUrl.value = res.data.video?.base_url || ''
        systemKeyPools.value = (res.data.key_pools || []).map(normalizePoolItem)
        systemModels.value = (res.data.models || []).map(normalizeModelItem)
        assignPromptChannelDraft(res.data.prompt_channels || {})
        promptHealth.value = res.data.prompt_health || null
        promptConfigErrors.value = []
        promptConfigWarnings.value = []
        expandedPools.clear()
        expandedSystemModels.clear()
        if (systemKeyPools.value.length) reorderKeyPools()
        ensurePromptChannelDraftModels()
        systemConfigDirty.value = false
    } catch (e) {
        message.error('加载系统配置失败')
    }
}

const handleSaveSystemConfig = async () => {
    if (authStore.user.username !== 'admin') return
    const hasEmptyModel = (systemModels.value || []).some((item) => !String(item?.model || '').trim())
    if (hasEmptyModel) {
        message.error(tSettings('settings.model_id_required', '请填写 Model ID'))
        return
    }
    try {
        const res = await api.post(
            '/api/admin/system_config',
            {
                image: {
                    api_key: systemImageKey.value,
                    backup_keys: parseKeyList(systemImageBackupKeysInput.value),
                    base_url: systemImageBaseUrl.value
                },
                tts: {
                    api_key: systemTtsKey.value,
                    backup_keys: parseKeyList(systemTtsBackupKeysInput.value),
                    base_url: systemTtsBaseUrl.value
                },
                video: {
                    api_key: systemVideoKey.value,
                    backup_keys: parseKeyList(systemVideoBackupKeysInput.value),
                    base_url: systemVideoBaseUrl.value
                },
                key_pools: serializeKeyPools(),
                models: serializeSystemModels(),
                prompt_channels: serializePromptChannels()
            },
            { headers: authStore.token ? { Authorization: `Bearer ${authStore.token}` } : {} }
        )
        promptHealth.value = res?.data?.prompt_health || null
        if (Array.isArray(res?.data?.warnings)) {
            promptConfigWarnings.value = res.data.warnings
        }
        promptConfigErrors.value = []
        message.success('系统配置已保存')
        systemConfigDirty.value = false
        clearModelCatalogCache()
        loadModelCatalog()
    } catch (e) {
        const detail = e?.response?.data?.detail
        if (detail?.code === 'PROMPT_CONFIG_INVALID') {
            promptConfigErrors.value = Array.isArray(detail.errors) ? detail.errors : []
            promptConfigWarnings.value = Array.isArray(detail.warnings) ? detail.warnings : []
            const firstError = promptConfigErrors.value[0] || tSettings('settings.prompt_config_invalid', '提示词通道配置未通过校验')
            message.error(firstError)
            return
        }
        message.error(`保存系统配置失败${detail ? `: ${typeof detail === 'string' ? detail : ''}` : ''}`)
    }
}

const fetchUsers = async () => {
    try {
        const res = await api.get('/api/admin/users', {
            headers: authStore.token ? { Authorization: `Bearer ${authStore.token}` } : {}
        })
        usersList.value = res.data
    } catch(e) {}
}
const toggleUserPro = async (u) => {
    try {
        await updateUserQuota(u, !u.is_pro, u.quota_limit)
        u.is_pro = !u.is_pro
        message.success(localeStore.t('settings.update_success'))
    } catch(e) { message.error(localeStore.t('settings.update_failed')) }
}

const saveUserQuota = async (u) => {
    try {
        await updateUserQuota(u, u.is_pro, u.quota_limit)
        message.success(localeStore.t('settings.update_success'))
    } catch(e) { message.error(localeStore.t('settings.update_failed')) }
}

const updateUserQuota = async (u, isPro, quotaLimit) => {
    return api.post(
        '/api/admin/update_user',
        { user_id: u.id, is_pro: isPro, quota_limit: Math.max(0, Number(quotaLimit) || 0) },
        { headers: authStore.token ? { Authorization: `Bearer ${authStore.token}` } : {} }
    )
}

const newUserForm = reactive({
    username: '',
    password: '',
    is_pro: false,
    quota_limit: 20
})

const parseBatchUserLine = (line) => {
    const normalized = String(line || '').trim()
    if (!normalized || normalized.startsWith('#')) return null
    const parts = normalized.includes(',')
        ? normalized.split(',')
        : normalized.split(/\s+/)
    const fields = parts.map((item) => String(item || '').trim()).filter(Boolean)
    if (fields.length < 2) return null
    const username = fields[0]
    const password = fields[1]
    const quotaRaw = fields.length >= 3 ? fields[2] : ''
    const roleRaw = fields.length >= 4 ? fields[3].toLowerCase() : ''
    const quota_limit = quotaRaw === '' ? 20 : Math.max(0, Number(quotaRaw) || 0)
    const is_pro = ['1', 'true', 'yes', 'y', 'pro', 'vip'].includes(roleRaw)
    return { username, password, quota_limit, is_pro }
}

const createUser = async () => {
    if (!newUserForm.username || !newUserForm.password) {
        message.warning(tSettings('settings.user_create_missing', '请输入用户名和密码'))
        return
    }
    try {
        await api.post(
            '/api/admin/users',
            {
                username: newUserForm.username,
                password: newUserForm.password,
                is_pro: newUserForm.is_pro,
                quota_limit: Math.max(0, Number(newUserForm.quota_limit) || 0)
            },
            { headers: authStore.token ? { Authorization: `Bearer ${authStore.token}` } : {} }
        )
        newUserForm.username = ''
        newUserForm.password = ''
        newUserForm.is_pro = false
        newUserForm.quota_limit = 20
        message.success(tSettings('settings.user_create_success', '用户创建成功'))
        fetchUsers()
    } catch (e) {
        const detail = e?.response?.data?.detail || tSettings('settings.user_create_failed', '创建用户失败')
        message.error(detail)
    }
}

const importUsersBatch = async () => {
    const lines = String(batchUserImportText.value || '').split(/\r?\n/)
    const users = lines
        .map((line) => parseBatchUserLine(line))
        .filter((item) => item && item.username && item.password)
    if (!users.length) {
        message.warning(tSettings('settings.user_batch_empty', '请先填写导入内容'))
        return
    }
    batchUserImporting.value = true
    batchImportResult.value = ''
    try {
        const res = await api.post(
            '/api/admin/users/batch',
            {
                users,
                skip_existing: batchUserSkipExisting.value !== false,
            },
            { headers: authStore.token ? { Authorization: `Bearer ${authStore.token}` } : {} }
        )
        const data = res?.data || {}
        const createdCount = Number(data.created_count || 0)
        const skippedCount = Number(data.skipped_count || 0)
        const failedCount = Number(data.failed_count || 0)
        batchImportResult.value = `导入完成：新增 ${createdCount}，跳过 ${skippedCount}，失败 ${failedCount}`
        if (failedCount > 0 && Array.isArray(data.failed) && data.failed.length) {
            const sample = data.failed.slice(0, 3).map((item) => `${item.username}: ${item.reason}`).join('；')
            message.warning(`部分账号导入失败：${sample}`)
        } else {
            message.success(tSettings('settings.user_batch_success', '批量导入完成'))
        }
        batchUserImportText.value = ''
        fetchUsers()
    } catch (e) {
        const detail = e?.response?.data?.detail || tSettings('settings.user_batch_failed', '批量导入失败')
        message.error(detail)
    } finally {
        batchUserImporting.value = false
    }
}

const deleteUser = async (u) => {
    if (!u?.id) return
    const confirmText = tSettings('settings.user_delete_confirm', '确认删除用户')
    if (!window.confirm(`${confirmText} ${u.username} ?`)) return
    try {
        await api.delete(`/api/admin/users/${u.id}`, {
            headers: authStore.token ? { Authorization: `Bearer ${authStore.token}` } : {}
        })
        message.success(tSettings('settings.user_delete_success', '用户已删除'))
        fetchUsers()
    } catch (e) {
        const detail = e?.response?.data?.detail || tSettings('settings.user_delete_failed', '删除用户失败')
        message.error(detail)
    }
}

onMounted(() => {
    loadUserKeyPools()
    loadModelCatalog()
    if (authStore.isLoggedIn || authStore.isGuest) fetchHistory()
    if (props.activeTab === 'settings' && authStore.user.username === 'admin') {
        if (activeSettingsTab.value === 'models') fetchSystemConfig()
        if (activeSettingsTab.value === 'users') fetchUsers()
    }
})

watch(
    () => props.activeTab,
    (tab) => {
        if (tab === 'gallery') fetchHistory()
        if (tab === 'settings' && authStore.user.username === 'admin') {
            if (activeSettingsTab.value === 'models') fetchSystemConfig()
            if (activeSettingsTab.value === 'users') fetchUsers()
        }
    }
)

watch(
    () => authStore.user.username,
    () => {
        const ids = settingsTabs.value.map((t) => t.id)
        if (!ids.includes(activeSettingsTab.value)) activeSettingsTab.value = ids[0] || 'user'
    },
    { immediate: true }
)

watch(
    () => activeSettingsTab.value,
    (tab) => {
        if (tab === 'user') loadUserKeyPools()
        if (authStore.user.username !== 'admin') return
        if (tab === 'models') fetchSystemConfig()
        if (tab === 'users') fetchUsers()
    }
)
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.list-enter-active, .list-leave-active { transition: all 0.4s ease; }
.list-enter-from, .list-leave-to { opacity: 0; transform: translateY(20px); }

/* Custom Scrollbar for inner elements */
.custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }

.checker-bg {
  background-color: #f8fafc;
  background-image:
    linear-gradient(
      45deg,
      rgba(148, 163, 184, 0.2) 25%,
      transparent 25%,
      transparent 75%,
      rgba(148, 163, 184, 0.2) 75%,
      rgba(148, 163, 184, 0.2)
    ),
    linear-gradient(
      45deg,
      rgba(148, 163, 184, 0.2) 25%,
      transparent 25%,
      transparent 75%,
      rgba(148, 163, 184, 0.2) 75%,
      rgba(148, 163, 184, 0.2)
    );
  background-size: 20px 20px;
  background-position: 0 0, 10px 10px;
}
</style>
