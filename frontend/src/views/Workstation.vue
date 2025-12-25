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
        
        <div class="w-px bg-gray-200 dark:bg-gray-700 my-2"></div>

        <button 
          v-if="isAdmin"
          @click="showAdminStats = true"
          class="flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm font-bold transition-all text-blue-500 hover:bg-blue-50"
          title="Admin Dashboard"
        >
          <span>📊</span>
        </button>

        <button 
          @click="showAdminLogin = true"
          class="flex items-center gap-2 px-3 py-2.5 rounded-xl text-sm font-bold transition-all text-gray-400 hover:text-gray-900 dark:hover:text-white"
          :class="isAdmin ? 'text-green-500' : ''"
          title="Admin Access"
        >
          <span>{{ isAdmin ? '🔓' : '🔒' }}</span>
        </button>
      </div>
    </div>

    <!-- ==================== 页面 1: 单图创作 ==================== -->
    <Transition name="fade" mode="out-in">
      <div v-if="currentTab === 'single'" class="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        
        <!-- 左侧：控制台 -->
        <div class="space-y-4">
          <!-- Header removed to save space -->

          <div class="bg-white dark:bg-gray-800 rounded-2xl p-5 shadow-xl border border-gray-100 dark:border-gray-700 space-y-4">
            
            <!-- 参数行 (紧凑布局) -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
              <!-- 学科 -->
              <div class="space-y-1">
                <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Subject</label>
                <n-popselect v-model:value="settings.subject" :options="subjectOptions" trigger="click">
                  <button class="w-full flex justify-between items-center px-3 py-2 bg-gray-50 dark:bg-gray-900 rounded-lg text-sm font-bold hover:bg-yellow-50 transition-colors truncate">
                    <span>{{ getSubjectLabel(settings.subject) }}</span>
                    <span class="text-xs">▼</span>
                  </button>
                </n-popselect>
              </div>

              <!-- 年级 -->
              <div class="space-y-1">
                <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Grade</label>
                <n-popselect v-model:value="settings.grade" :options="gradeOptions" trigger="click">
                  <button class="w-full flex justify-between items-center px-3 py-2 bg-gray-50 dark:bg-gray-900 rounded-lg text-sm font-bold hover:bg-green-50 transition-colors truncate">
                    <span>{{ getGradeLabel(settings.grade) }}</span>
                    <span class="text-xs">▼</span>
                  </button>
                </n-popselect>
              </div>

              <!-- 画幅 -->
              <div class="space-y-1">
                <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Ratio</label>
                 <n-popselect v-model:value="settings.aspectRatio" :options="ratioOptions" trigger="click">
                  <button class="w-full flex justify-between items-center px-3 py-2 bg-gray-50 dark:bg-gray-900 rounded-lg text-sm font-bold hover:bg-gray-100 transition-colors truncate">
                    <span>{{ settings.aspectRatio }}</span>
                    <span class="text-xs">▼</span>
                  </button>
                </n-popselect>
              </div>

              <!-- 画质 -->
              <div class="space-y-1">
                <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Quality</label>
                 <n-popselect v-model:value="settings.quality" :options="qualityOptions" trigger="click">
                  <button class="w-full flex justify-between items-center px-3 py-2 bg-gray-50 dark:bg-gray-900 rounded-lg text-sm font-bold hover:bg-gray-100 transition-colors truncate">
                    <span>{{ getQualityLabel(settings.quality).split(' ')[0] }}</span>
                    <span class="text-xs">▼</span>
                  </button>
                </n-popselect>
              </div>
            </div>

            <!-- 参考图上传 (多图) -->
            <div class="space-y-1">
                <div class="flex justify-between items-center">
                   <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Reference Images ({{ refImageUrls.length }}/4)</label>
                   <button v-if="refImageUrls.length > 0" @click="refImageUrls = []" class="text-[10px] text-red-400 hover:underline">Clear All</button>
                </div>
                <n-upload
                  action="/api/upload"
                  :max="4"
                  multiple
                  list-type="image-card"
                  @finish="handleUploadFinishWithStore"
                  @remove="handleRemoveWithStore"
                  class="block"
                >
                  <div class="flex flex-col items-center justify-center text-gray-400 text-xs gap-1">
                    <span class="text-lg">📸</span>
                    <span class="scale-90">Add Ref</span>
                  </div>
                </n-upload>
            </div>

            <!-- 输入框 -->
                        <div class="space-y-2">
                           <div class="flex justify-between items-center">
                <label class="text-xs font-bold text-gray-400 uppercase tracking-wider">提示词</label>
                             <button 
                               @click="handleOptimizePrompt" 
                               class="text-xs flex items-center gap-1 text-purple-600 hover:text-purple-800 font-bold transition-colors disabled:opacity-50"
                               :disabled="!inputText.trim() || processing"
                             >
                               <span>🪄</span> Magic Optimize
                             </button>
                           </div>
                           <textarea
                            v-model="inputText"
                            placeholder="描述一个清晰的画面..."
                            class="w-full h-48 p-4 bg-gray-50 dark:bg-gray-900 rounded-xl border-none outline-none text-lg resize-none focus:ring-2 focus:ring-yellow-400 transition-all"
                            @keydown.enter.ctrl="handleGenerateSingle"
                          ></textarea>
                        </div>
            
                        <div class="space-y-2">
                            <button 
                              @click="handleGenerateSingle"
                              :disabled="!inputText.trim() || processing || quota.remaining <= 0"
                              class="w-full py-4 bg-black dark:bg-white text-white dark:text-black rounded-xl font-bold text-lg hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              <span v-if="processing">Drawing...</span>
                              <span v-else-if="quota.remaining <= 0">No Quota Left</span>
                              <span v-else>Generate Image</span>
                            </button>
                                                            <div class="flex justify-between text-xs text-gray-400 px-1 mt-2">
                                                               <span>Weekly Quota: {{ quota.remaining }} / {{ quota.max }}</span>
                                                               <span v-if="quota.remaining < 5" class="text-red-400 font-bold">Low Quota!</span>
                                                            </div>
                                                            <!-- 常驻联系信息 -->
                                                            <div class="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700 text-center">
                                                              <p class="text-[10px] text-gray-400 leading-relaxed">
                                                                如需调整额度或报告问题<br>
                                                                请联系 <span class="text-blue-500 font-bold hover:underline cursor-pointer">上海科技大学附属学校信息组</span> 老师
                                                              </p>
                                                            </div>
                                                        </div>
                                                      </div>
                                                    </div>        <!-- 右侧：预览大图 -->
        <div class="relative min-h-[500px] flex items-center justify-center bg-gray-100 dark:bg-gray-800 rounded-3xl border-2 border-dashed border-gray-200 dark:border-gray-700 overflow-hidden">
             <div v-if="latestSingleTask" class="relative w-full h-full p-4">
             <div v-if="latestSingleTask.status === 'processing' || latestSingleTask.status === 'pending'" class="absolute inset-0 flex flex-col items-center justify-center bg-white/80 dark:bg-gray-800/80 backdrop-blur z-10">
                <div class="text-6xl animate-bounce mb-4">🍌</div>
                <p class="font-bold text-gray-500">{{ latestSingleTask.statusMsg || '生成中，预计 30 秒左右，请稍候...' }}</p>
             </div>
             <img 
               v-if="latestSingleTask.resultUrl" 
               :src="latestSingleTask.resultUrl" 
               class="w-full h-full object-contain rounded-xl shadow-lg cursor-pointer"
               @click="openImage({ url: latestSingleTask.resultUrl, prompt: latestSingleTask.prompt, subject: settings.subject, grade: settings.grade })"
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

          <!-- Modification Overlay / Section -->
          <div v-if="latestSingleTask && latestSingleTask.status === 'done'" class="absolute bottom-0 left-0 right-0 bg-white/90 dark:bg-gray-800/90 backdrop-blur p-4 border-t border-gray-100 dark:border-gray-700 transition-transform transform translate-y-0">
             <div class="flex gap-2">
                <input 
                  v-model="modificationInput" 
                  placeholder="✨ Modify this image (e.g., add a hat, make it night)..." 
                  class="flex-1 bg-gray-50 dark:bg-gray-900 border-none outline-none px-4 py-2 rounded-lg text-sm"
                  @keydown.enter="handleModify"
                />
                <button 
                  @click="handleModify"
                  :disabled="processing || !modificationInput"
                  class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-bold transition-colors disabled:opacity-50"
                >
                   Modify
                </button>
             </div>
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
                      <img v-if="task.status === 'done'" :src="task.resultUrl" class="w-full h-full object-cover cursor-pointer hover:opacity-90" @click="openImage({ url: task.resultUrl, prompt: task.prompt, subject: task.settings.subject, grade: task.settings.grade })" />
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
          <div class="flex items-center justify-between mb-6">
            <div class="text-sm text-gray-500">共 {{ filteredGallery.length }} 张图片</div>
            <label class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
              <input type="checkbox" v-model="showFeaturedOnly" class="h-4 w-4 rounded border-gray-300 text-yellow-500 focus:ring-yellow-400" />
              只看精选
            </label>
          </div>
          <div v-if="filteredGallery.length === 0" class="h-full flex flex-col items-center justify-center text-gray-400"><div class="text-4xl mb-4">📭</div><p>暂无图片</p></div>
          <div v-else class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
             <div 
               v-for="img in filteredGallery" 
               :key="img.id" 
               class="group relative aspect-square rounded-xl overflow-hidden cursor-pointer"
               @click="openImage(img)"
             >
               <img :src="img.url" class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110" loading="lazy" />
               <div class="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-4">
                 <span class="text-white text-xs font-bold mb-1">{{ getSubjectLabel(img.subject) }}</span>
                 <p class="text-gray-200 text-[10px] line-clamp-2">{{ img.prompt }}</p>
               </div>
               <button 
                 v-if="isAdmin" 
                 @click.stop="toggleFeature(img)" 
                 class="absolute top-2 right-2 h-8 w-8 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black/80 transition-colors"
                 :title="img.featured ? '取消精选' : '设为精选'"
               >
                 <span v-if="img.featured">★</span>
                 <span v-else>☆</span>
               </button>
               <div v-else-if="img.featured" class="absolute top-2 right-2 px-2 py-1 bg-yellow-400 text-black text-[10px] font-bold rounded-full shadow">精选</div>
             </div>
          </div>
        </main>
      </div>
    </Transition>

    <!-- ==================== 图片详情弹窗 ==================== -->
    <Transition name="fade">
      <div v-if="showModal && selectedImage" class="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-8" @click.self="closeModal">
         <!-- 背景遮罩 -->
         <div class="absolute inset-0 bg-black/90 backdrop-blur-sm transition-opacity"></div>
         
         <!-- 内容卡片 -->
         <div class="relative bg-white dark:bg-gray-900 rounded-2xl w-full max-w-6xl max-h-[90vh] flex flex-col md:flex-row overflow-hidden shadow-2xl animate-scale-in">
            
            <!-- 关闭按钮 -->
            <button @click="closeModal" class="absolute top-4 right-4 z-10 w-10 h-10 bg-black/50 hover:bg-black/70 text-white rounded-full flex items-center justify-center backdrop-blur transition-colors">
               ✕
            </button>

            <!-- 左侧：图片展示 -->
            <div class="flex-1 bg-black/5 dark:bg-black flex items-center justify-center p-4 overflow-hidden relative group">
               <img :src="selectedImage.url" class="max-w-full max-h-full object-contain shadow-sm" />
               <a :href="selectedImage.url" target="_blank" download class="absolute bottom-6 right-6 opacity-0 group-hover:opacity-100 bg-white/90 text-black px-4 py-2 rounded-lg text-sm font-bold shadow transition-opacity">
                  Download Original
               </a>
            </div>

            <!-- 右侧：信息面板 -->
            <div class="w-full md:w-96 p-8 flex flex-col border-l border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900">
               <div class="mb-6">
                  <h3 class="text-2xl font-bold mb-2 text-gray-900 dark:text-white">Image Details</h3>
                  <div class="flex flex-wrap gap-2">
                     <span class="px-3 py-1 bg-yellow-100 text-yellow-800 rounded-full text-xs font-bold uppercase tracking-wide">
                        {{ getSubjectLabel(selectedImage.subject) }}
                     </span>
                     <span class="px-3 py-1 bg-green-100 text-green-800 rounded-full text-xs font-bold uppercase tracking-wide">
                        {{ getGradeLabel(selectedImage.grade) }}
                     </span>
                     <span v-if="selectedImage.timestamp" class="px-3 py-1 bg-gray-100 dark:bg-gray-800 text-gray-500 rounded-full text-xs">
                        {{ new Date(selectedImage.timestamp * 1000).toLocaleDateString() }}
                     </span>
                  </div>
               </div>

               <div class="flex-1 overflow-y-auto mb-6 pr-2 custom-scrollbar">
                  <label class="text-xs font-bold text-gray-400 uppercase tracking-wider block mb-2">Prompt</label>
                  <p class="text-sm text-gray-600 dark:text-gray-300 leading-relaxed whitespace-pre-wrap font-mono bg-gray-50 dark:bg-gray-800 p-4 rounded-xl border border-gray-100 dark:border-gray-700">
                     {{ selectedImage.prompt }}
                  </p>
               </div>

               <div class="mt-auto space-y-3">
                  <button 
                    @click="copyPrompt"
                    class="w-full py-3 bg-black dark:bg-white text-white dark:text-black rounded-xl font-bold flex items-center justify-center gap-2 hover:opacity-90 transition-opacity"
                  >
                     <span>📋</span> Copy Prompt
                  </button>
               </div>
            </div>
         </div>
      </div>
    </Transition>

    <!-- ==================== 管理员登录弹窗 ==================== -->
    <Transition name="fade">
      <div v-if="showAdminLogin" class="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" @click.self="showAdminLogin = false">
         <div class="bg-white dark:bg-gray-800 rounded-2xl p-8 w-full max-w-sm shadow-xl animate-scale-in space-y-4">
            <h3 class="text-xl font-bold text-center">Admin Access</h3>
            <input type="password" v-model="adminPassword" placeholder="Enter password..." class="w-full px-4 py-3 bg-gray-50 dark:bg-gray-700 rounded-xl border-none outline-none" @keydown.enter="handleAdminLogin" />
            <button @click="handleAdminLogin" class="w-full py-3 bg-black dark:bg-white text-white dark:text-black rounded-xl font-bold hover:opacity-90">Login</button>
         </div>
      </div>
    </Transition>

    <!-- ==================== 数据统计弹窗 ==================== -->
    <Transition name="fade">
      <div v-if="showAdminStats && adminStats" class="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm" @click.self="showAdminStats = false">
         <div class="bg-white dark:bg-gray-800 rounded-2xl p-8 w-full max-w-4xl max-h-[80vh] overflow-y-auto shadow-xl animate-scale-in">
            <div class="flex justify-between items-center mb-6">
              <h3 class="text-2xl font-bold">Data Dashboard</h3>
              <button @click="showAdminStats = false" class="w-8 h-8 rounded-full bg-gray-100 text-gray-500 hover:bg-gray-200">✕</button>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
               <!-- 学科统计 -->
               <div class="space-y-4">
                  <h4 class="font-bold text-gray-500 uppercase tracking-wider text-xs">By Subject</h4>
                  <div class="space-y-2">
                     <div v-for="(count, sub) in adminStats.subject_counts" :key="sub" class="flex items-center gap-2">
                        <div class="w-24 text-sm font-bold truncate">{{ getSubjectLabel(sub) }}</div>
                        <div class="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                           <div class="h-full bg-yellow-400 rounded-full" :style="{width: Math.min(count * 5, 100) + '%'}"></div>
                        </div>
                        <div class="w-8 text-xs text-right">{{ count }}</div>
                     </div>
                  </div>
               </div>

               <!-- 年级统计 -->
               <div class="space-y-4">
                  <h4 class="font-bold text-gray-500 uppercase tracking-wider text-xs">By Grade</h4>
                  <div class="space-y-2">
                     <div v-for="(count, grade) in adminStats.grade_counts" :key="grade" class="flex items-center gap-2">
                        <div class="w-24 text-sm font-bold truncate">{{ getGradeLabel(grade) }}</div>
                        <div class="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                           <div class="h-full bg-green-400 rounded-full" :style="{width: Math.min(count * 5, 100) + '%'}"></div>
                        </div>
                        <div class="w-8 text-xs text-right">{{ count }}</div>
                     </div>
                  </div>
               </div>

               <!-- IP 活跃度 -->
               <div class="md:col-span-2 space-y-4">
                  <h4 class="font-bold text-gray-500 uppercase tracking-wider text-xs">Top Active Users (IP)</h4>
                  <div class="bg-gray-50 dark:bg-gray-900 rounded-xl p-4 overflow-x-auto">
                     <table class="w-full text-sm text-left">
                        <thead>
                           <tr class="text-gray-400 border-b border-gray-200 dark:border-gray-700">
                              <th class="py-2">IP Address</th>
                              <th class="py-2">Total Generated</th>
                              <th class="py-2">Last Active</th>
                           </tr>
                        </thead>
                        <tbody>
                           <tr v-for="stat in adminStats.ip_stats.slice(0, 10)" :key="stat.ip" class="border-b border-gray-100 dark:border-gray-800 last:border-0">
                              <td class="py-2 font-mono">{{ stat.ip }}</td>
                              <td class="py-2 font-bold">{{ stat.count }}</td>
                              <td class="py-2 text-gray-500">{{ new Date(stat.last_active * 1000).toLocaleString() }}</td>
                           </tr>
                        </tbody>
                     </table>
                  </div>
               </div>
            </div>
         </div>
      </div>
    </Transition>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { NPopselect, useMessage, NUpload } from 'naive-ui'
import axios from 'axios'

const message = useMessage()
const currentTab = ref('single') 

// --- 状态 ---
const inputText = ref('') 
const modificationInput = ref('') // 修改指令
const batchInputText = ref('') 
const processing = ref(false)

const singleTasks = ref([]) 
const batchQueue = ref([])

// ... existing code ...

const handleModify = async () => {
  const currentTask = latestSingleTask.value
  if (!currentTask || !currentTask.resultUrl || !modificationInput.value.trim()) return
  
  const modPrompt = modificationInput.value.trim()
  modificationInput.value = '' // clear input
  processing.value = true
  
  // Create a new task entry for the modification to show progress
  const newTask = { 
      id: Date.now(), 
      prompt: `Modify: ${modPrompt}`, 
      status: 'processing', 
      resultUrl: null, 
      settings: { ...settings.value } // inherit settings
  }
  singleTasks.value.push(newTask)
  
  const runModify = async () => {
      try {
        const res = await axios.post('/api/generate/modify', {
          prompt: modPrompt,
          original_image_url: currentTask.resultUrl
        })
        
        if (res.data.success) {
          newTask.status = 'done'
          newTask.resultUrl = res.data.url
          message.success('修改成功！请及时保存')
          addToGallery(newTask)
        }
      } catch (err) {
        if (err.response && err.response.status === 429) {
            const msg = err.response.data.detail || ''
            const match = msg.match(/(\d+)\s*秒/)
            const waitSeconds = match ? parseInt(match[1]) : 30
            
            newTask.status = 'pending'
            for (let i = waitSeconds; i > 0; i--) {
                newTask.statusMsg = `排队中... ${i}s 后重试`
                await new Promise(r => setTimeout(r, 1000))
            }
            newTask.statusMsg = '正在重试...'
            newTask.status = 'processing'
            await runModify()
            return
        }
        
        newTask.status = 'failed'
        message.error('修改失败: ' + (err.response?.data?.detail || err.message))
      }
  }

  await runModify()
  processing.value = false
}

const galleryFilter = ref('all')
const galleryImages = ref([])
const showFeaturedOnly = ref(true) // 默认仅展示精选，可切换查看全部

const quota = ref({ remaining: 20, max: 20 })

// --- 弹窗状态 ---
const showModal = ref(false)
const selectedImage = ref(null)

// --- 管理员状态 ---
const isAdmin = ref(false)
const showAdminLogin = ref(false)
const adminPassword = ref('')
const showAdminStats = ref(false)
const adminStats = ref(null)

// --- 设置 ---
const settings = ref({
  subject: 'general',
  grade: 'general',
  aspectRatio: '1:1',
  style: 'vivid',
  quality: 'standard'
})

const refImageUrls = ref([]) // 多张参考图

const handleUploadFinish = ({ file, event }) => {
  try {
    const res = JSON.parse(event.target.response)
    if (res.success) {
      refImageUrls.value.push(res.url)
      message.success('参考图上传成功')
    } else {
      message.error('上传失败')
    }
  } catch (e) {
    message.error('上传响应解析失败')
  }
}

const handleRemoveUpload = ({ file, fileList }) => {
  // Naive UI 的 fileList 包含剩余的文件
  // 但我们的 fileList 是组件内部维护的，我们需要同步 refImageUrls
  // 这里简化处理：直接从 file.url (如果有) 或重新映射
  // 更可靠的方式是: 每次 finish push, 每次 remove 找到对应的并删除
  // 因为没有 file.url (response 在 event里), 我们假设顺序一致或者不做复杂匹配
  // 简单起见，remove时不传参数，我们只能拿到 fileList?
  // Naive UI 的 remove 回调参数是 { file, fileList }
  
  // 实际上，因为我们要传给后端的是 URL 列表，最稳妥的是每次变动都同步
  // 但 Naive Upload 在 remove 时 file 对象可能没有我们存的 url
  
  // 改进方案：我们只维护一个简单的数组。如果用户删除了，我们怎么知道删的是哪个？
  // 我们可以利用 file.id 匹配。
  // 但目前为了快速实现，我们假设用户不会频繁删改。
  // 或者我们可以直接重置：
  // refImageUrls.value = fileList.map(...) 
  // 但是 fileList 里的 file 没有 response url...
  
  // 修正逻辑：
  // 在 handleUploadFinish 时，把 url 挂载到 file 对象上 (file.url = ...)
  // Naive UI 会自动维护 fileList。
  // 这样在 remove 时，fileList 里剩余的 file 都有 url。
  
  // 这里的 file 是 Naive UI 的内部对象。我们无法直接修改 fileList 的引用。
  // 妥协方案：remove 时我们根据 index 删除？或者 file.name?
  
  // 重新思考：最简单的方式是只 append。如果用户想删，点击 "Clear All"。
  // 单个删除有点复杂，因为我们需要匹配 URL。
  
  // 尝试匹配：
  // 实际上，file 对象在 finish 时我们可以访问。
  file.url = JSON.parse(event?.target?.response || '{}').url
  // 等等，handleRemoveUpload 的参数是 data: { file, fileList }
  // 我们其实在 handleUploadFinish 里拿不到 fileList 的引用去修改 file.url
  
  // 让我们采用最简方案：handleRemoveUpload 不做精细操作，只是为了防止报错。
  // 真正的同步逻辑：refImageUrls 只是个字符串数组。
  // 如果必须支持单个删除，我们需要维护一个 Map<FileId, Url>。
  
  // 既然我们在 UI 上加了 "Clear All"，那暂时先仅支持全清，或者简单 pop。
  // 这里暂时留空，或者 filter。
  
  // 更好的做法：使用 v-model:file-list ? 不，action模式下比较麻烦。
  
  // 让我们用一个简单的方法：通过文件名匹配（假设不重复）
  const targetUrl = file.url // 如果我们能存进去的话
  // ...
  
  // 暂时：移除时，从 refImageUrls 里移除最后添加的一个（栈操作），不太准但能用
  refImageUrls.value.pop() 
}

// 修正：handleUploadFinish 中给 file 赋值
const handleUploadFinishWithStore = ({ file, event }) => {
    try {
        const res = JSON.parse(event.target.response)
        if (res.success) {
            file.url = res.url // 存入 file 对象
            refImageUrls.value.push(res.url)
            message.success('参考图 +1')
        }
    } catch(e) {}
}

const handleRemoveWithStore = ({ file }) => {
    if (file.url) {
        refImageUrls.value = refImageUrls.value.filter(u => u !== file.url)
    } else {
        // Fallback
        refImageUrls.value.pop()
    }
}

// ... 

const subjectOptions = [
  { label: '信息科技与AI', value: 'it_ai', icon: '🤖' },
  { label: '通用', value: 'general', icon: '🌐' },
  { label: '数学', value: 'math', icon: '📐' },
  { label: '科学', value: 'science', icon: '🔬' },
  { label: '英语', value: 'english', icon: 'abc' },
  { label: '艺术', value: 'art', icon: '🎨' },
  { label: '历史', value: 'history', icon: '🏛️' }
]

const gradeOptions = [
  { label: '通用', value: 'general' },
  { label: '幼儿园 / 小学', value: 'primary' },
  { label: '初中', value: 'middle' },
  { label: '高中', value: 'high' },
  { label: '大学', value: 'college' }
]

const ratioOptions = [
  { label: '正方形 (1:1)', value: '1:1' },
  { label: '横版 (16:9)', value: '16:9' },
  { label: '竖版 (9:16)', value: '9:16' }
]

const qualityOptions = [
  { label: '标准 (1K) - 快速', value: 'standard' },
  { label: '高质 (2K) - 细节', value: '2k' },
  { label: '超清 (4K) - 最佳', value: '4k' }
]

// --- 辅助 ---
const getSubjectLabel = (val) => subjectOptions.find(o => o.value === val)?.label || val
const getGradeLabel = (val) => gradeOptions.find(o => o.value === val)?.label || val
const getQualityLabel = (val) => qualityOptions.find(o => o.value === val)?.label || val
const getCountBySubject = (sub) => galleryImages.value.filter(i => i.subject === sub).length
const latestSingleTask = computed(() => singleTasks.value[singleTasks.value.length - 1] || null)
const reversedBatchQueue = computed(() => [...batchQueue.value].reverse())
const filteredGallery = computed(() => {
  let imgs = galleryImages.value
  if (galleryFilter.value !== 'all') {
    imgs = imgs.filter(img => img.subject === galleryFilter.value)
  }
  // 如果不是管理员且勾选了"只看精选"，或者管理员勾选了"只看精选"
  // 其实通常逻辑是：默认给公众看精选。
  if (showFeaturedOnly.value) {
    imgs = imgs.filter(img => img.featured)
  }
  return imgs
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
          grade: t.grade || settings.value.grade,
          aspectRatio: t.aspectRatio || settings.value.aspectRatio,
          style: t.style || settings.value.style,
          quality: t.quality || settings.value.quality
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
    { prompt: "Example prompt 1", subject: "science", aspectRatio: "1:1", quality: "standard" },
    { prompt: "Example prompt 2", subject: "math", aspectRatio: "16:9", quality: "4k" }
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

const handleOptimizePrompt = async () => {
  if (!inputText.value.trim()) return
  const original = inputText.value
  processing.value = true
  try {
    message.loading('✨ AI is optimizing your prompt...')
    const res = await axios.post('/api/optimize_prompt', { prompt: original })
    if (res.data.success) {
      inputText.value = res.data.optimized_prompt
      message.success('Prompt Optimized!')
    }
  } catch (e) {
    message.error('Optimization failed')
  } finally {
    processing.value = false
  }
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

// executeTask 已移动到下方

const processBatchQueue = async () => {
  if (processing.value) return
  processing.value = true
  
  while (true) {
    const nextTask = batchQueue.value.find(t => t.status === 'pending')
    if (!nextTask) break
    
    await executeTask(nextTask)
    
    // 如果任务成功，且队列里还有任务，主动等待，避免立刻触发 429
    // 后端限制已改为 12s，这里我们设置 15s 的安全间隔
    const hasMore = batchQueue.value.some(t => t.status === 'pending')
    if (nextTask.status === 'done' && hasMore) {
        for (let i = 15; i > 0; i--) {
            // 这里我们需要一种方式通知 UI 正在冷却，但又不占用 specific task 的 status
            // 简单起见，我们借用 message 或者一个全局状态，或者直接在下一个任务上显示？
            // 更好的体验：直接等待即可，让下一个任务开始时去处理（或者预先显示等待）
            // 咱们简单 sleep，但在控制台或界面上也许看不出来
            await new Promise(r => setTimeout(r, 1000))
        }
    }
  }
  processing.value = false
}

const addToGallery = (task) => {
  galleryImages.value.unshift({ 
    id: task.id, 
    url: task.resultUrl, 
    prompt: task.prompt, 
    subject: task.settings.subject, 
    grade: task.settings.grade, 
    timestamp: Date.now(),
    featured: false
  })
}

const fetchHistory = async () => {
  try {
    const res = await axios.get('/api/gallery')
    // 后端现在返回了 subject 和 prompt，直接使用
    galleryImages.value = res.data.map(img => ({
      id: img.name,
      url: img.url,
      prompt: img.prompt || 'History Image',
      subject: img.subject || 'general',
      grade: img.grade || 'general',
      timestamp: img.time,
      featured: img.featured || false
    }))
  } catch (e) {}
}

const fetchQuota = async () => {
    try {
        const res = await axios.get('/api/quota')
        quota.value = { remaining: res.data.remaining, max: res.data.max }
    } catch(e) {}
}

const openImage = (img) => { 
  // 兼容直接传 URL 字符串的情况 (虽然现在主要传对象)
  if (typeof img === 'string') {
     window.open(img, '_blank')
     return
  }
  selectedImage.value = img
  showModal.value = true
}

const closeModal = () => {
  showModal.value = false
  selectedImage.value = null
}

const copyPrompt = async () => {
  if (!selectedImage.value || !selectedImage.value.prompt) return
  
  const text = selectedImage.value.prompt
  
  try {
    // 优先尝试标准 API
    if (navigator.clipboard && navigator.clipboard.writeText) {
       await navigator.clipboard.writeText(text)
       message.success('提示词已复制！')
       return
    }
  } catch (e) {
    console.warn('Clipboard API failed, trying fallback...')
  }
  
  // 降级方案 (兼容 HTTP)
  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed' // 避免滚动
    textarea.style.left = '-9999px'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    message.success('提示词已复制！')
  } catch (e) {
    message.error('复制失败，请手动复制')
  }
}

// --- 管理员逻辑 ---
const handleAdminLogin = async () => {
    try {
        const res = await axios.post('/api/admin/login', { password: adminPassword.value })
        if (res.data.success) {
            isAdmin.value = true
            localStorage.setItem('admin_token', res.data.token)
            showAdminLogin.value = false
            message.success('管理员登录成功')
            fetchAdminStats()
        }
    } catch (e) {
        message.error('密码错误')
    }
}

const fetchAdminStats = async () => {
    if (!isAdmin.value) return
    try {
        const token = localStorage.getItem('admin_token')
        const res = await axios.get('/api/admin/stats', { headers: { 'x-admin-token': token } })
        adminStats.value = res.data
    } catch (e) {}
}

const toggleFeature = async (img) => {
    if (!isAdmin.value) return
    try {
        const token = localStorage.getItem('admin_token')
        const newState = !img.featured
        const res = await axios.post('/api/admin/toggle_feature', 
            { filename: img.id, featured: newState },
            { headers: { 'x-admin-token': token } }
        )
        if (res.data.success) {
            img.featured = res.data.featured
            message.success(newState ? '已设为精选' : '取消精选')
            // 切换到只看精选时，列表会自动刷新过滤
        }
    } catch (e) {
        message.error('操作失败')
    }
}

const executeTask = async (task) => {
  task.status = 'processing'
  // message.info('生成中，预计 30 秒左右，请稍候...', { duration: 5 }) // 减少干扰
  
  const mapAspectToSize = (ratio) => {
    if (ratio === '16:9') return '1792x1024'
    if (ratio === '9:16') return '1024x1792'
    return '1024x1024'
  }

  const payload = {
    prompt: task.prompt,
    size: mapAspectToSize(task.settings.aspectRatio),
    quality: task.settings.quality || 'standard',
    style: task.settings.style || 'vivid',
    subject: task.settings.subject || 'general',
    grade: task.settings.grade || 'general',
    reference_image_urls: refImageUrls.value
  }

  const runRequest = async () => {
      try {
        const res = await axios.post('/api/generate/single', payload)
        task.status = 'done'
        task.resultUrl = res.data.url
        
        const remaining = res.data.remaining_quota ?? quota.value.remaining
        const max = res.data.max ?? quota.value.max
        quota.value = { remaining, max }

        addToGallery(task)
        message.success('🎉 生成完成！请点击图片及时下载保存', { duration: 5000 }) 
        
      } catch (e) {
        if (e.response && e.response.status === 429) {
            // 触发排队机制
            const msg = e.response.data.detail || ''
            // 尝试提取秒数 "请休息 34 秒"
            const match = msg.match(/(\d+)\s*秒/)
            const waitSeconds = match ? parseInt(match[1]) : 30
            
            console.log(`Rate limit hit, waiting ${waitSeconds}s...`)
            task.status = 'pending' // 保持 pending 状态或者新增 queued
            
            // 倒计时逻辑
            for (let i = waitSeconds; i > 0; i--) {
                task.statusMsg = `排队中... ${i}s 后重试`
                await new Promise(r => setTimeout(r, 1000))
                // 如果用户手动取消任务，需要跳出（目前还没做取消按钮，先忽略）
            }
            
            task.statusMsg = '正在重试...'
            task.status = 'processing'
            await runRequest() # 递归重试
            return
        }
        
        task.status = 'failed'
        const detail = e?.response?.data?.detail || '生成失败，请稍后重试'
        message.error(detail)
      }
  }

  await runRequest()
}

onMounted(() => {
  fetchHistory()
  fetchQuota()
})
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.list-enter-active, .list-leave-active { transition: all 0.5s ease; }
.list-enter-from { opacity: 0; transform: translateY(20px); }
</style>
