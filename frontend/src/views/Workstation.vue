<template>
  <div class="space-y-8 relative min-h-[80vh]">

    <!-- 登录/注册遮罩 -->
    <Transition name="fade">
      <div v-if="!authStore.isLoggedIn && !authStore.isGuest" class="absolute inset-0 z-[500] flex items-center justify-center bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm">
        <div class="w-full max-w-md bg-white dark:bg-gray-800 rounded-3xl p-8 shadow-2xl border border-gray-100 dark:border-gray-700 animate-scale-in">
          <div class="text-center mb-8">
            <h2 class="text-3xl font-bold mb-2">Welcome Back</h2>
            <p class="text-gray-500">请登录以继续使用智绘工坊</p>
          </div>

          <div class="space-y-4">
            <div>
              <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">Username</label>
              <input v-model="loginForm.username" type="text" class="w-full px-4 py-3 bg-gray-50 dark:bg-gray-700 rounded-xl outline-none focus:ring-2 focus:ring-black dark:focus:ring-white transition-all" placeholder="输入用户名" @keyup.enter="handleAuthAction" />
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">Password</label>
              <input v-model="loginForm.password" type="password" class="w-full px-4 py-3 bg-gray-50 dark:bg-gray-700 rounded-xl outline-none focus:ring-2 focus:ring-black dark:focus:ring-white transition-all" placeholder="输入密码" @keyup.enter="handleAuthAction" />
            </div>

            <button 
              @click="handleAuthAction" 
              class="w-full py-4 bg-black dark:bg-white text-white dark:text-black rounded-xl font-bold text-lg hover:scale-[1.02] active:scale-[0.98] transition-all"
              :disabled="authLoading"
            >
              <span v-if="authLoading">Processing...</span>
              <span v-else>登录 (Login)</span>
            </button>

            <button 
              @click="handleGuestAccess" 
              class="w-full py-3 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-200 rounded-xl font-bold hover:bg-gray-200 dark:hover:bg-gray-600 transition-all border border-gray-200 dark:border-gray-600"
            >
              🔑 我没有账号 (使用 API Key)
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 主界面 (仅登录后可操作) -->
    <div v-if="authStore.isLoggedIn || authStore.isGuest" class="space-y-8">
      
      <!-- 用户状态栏 -->
      <div class="flex justify-between items-center bg-white dark:bg-gray-800 p-4 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700">
         <div class="flex items-center gap-3">
             <div class="text-xs text-gray-500">
                <span v-if="authStore.isGuest">Guest Mode (BYOK Only)</span>
                <span v-else>
                    <span v-if="authStore.user.is_pro" class="mr-2 px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded font-bold">PRO</span>
                    <span v-else class="mr-2 px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded font-bold">STD</span>
                    
                    本周额度: <span :class="{'text-red-500': authStore.user.quota_remaining < 3, 'font-bold': true}">{{ authStore.user.quota_remaining }}</span> / {{ authStore.user.quota_limit }}
                    
                    <span v-if="authStore.user.quota_remaining <= 0">
                        <span v-if="userModelKeyInput" class="ml-2 text-blue-500 font-bold">
                            ✅ 已启用自定义 Key 继续生成
                        </span>
                        <span v-else class="ml-2 text-red-500 font-bold animate-pulse cursor-pointer hover:underline" @click="showAccessKeyModal = true">
                            ⚠️ 额度已用完，请配置 Key
                        </span>
                    </span>
                </span>
             </div>
         </div>
         <div class="flex gap-4">
             <button @click="currentTab = 'settings'" class="text-sm font-bold text-gray-500 hover:text-black">API设置</button>
             <button @click="authStore.logout()" class="text-sm font-bold text-red-500 hover:text-red-700">退出登录</button>
         </div>
      </div>

      <!-- 顶部主导航栏 -->
      <div class="flex justify-center">
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

          <!-- <button 
            @click="currentTab = 'digital_human'"
            class="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold transition-all"
            :class="currentTab === 'digital_human' ? 'bg-black text-white shadow-md' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900 dark:hover:bg-gray-700 dark:hover:text-gray-200'"
          >
            <span>🗣️</span> 数字人 (Beta)
          </button> -->

          <div class="w-px bg-gray-200 dark:bg-gray-700 my-2"></div>

          <button 
            @click="currentTab = 'gallery'"
            class="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold transition-all"
            :class="currentTab === 'gallery' ? 'bg-yellow-100 text-yellow-800 shadow-sm' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900 dark:hover:bg-gray-700 dark:hover:text-gray-200'"
          >
            <span>🖼️</span> 画廊
          </button>
          
          <button 
            v-if="authStore.user.username === 'admin'"
            @click="currentTab = 'settings'"
            class="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold transition-all"
            :class="currentTab === 'settings' ? 'bg-gray-900 text-white shadow-md' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900 dark:hover:bg-gray-700 dark:hover:text-gray-200'"
          >
            <span>⚙️</span> 全局设置
          </button>
        </div>
      </div>

      <!-- ==================== 页面 1: 单图创作 ==================== -->
      <Transition name="fade" mode="out-in">
        <div v-if="currentTab === 'single'" class="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          
          <!-- 左侧：控制台 -->
          <div class="space-y-4">
            <div class="bg-white dark:bg-gray-800 rounded-2xl p-5 shadow-xl border border-gray-100 dark:border-gray-700 space-y-4">
              <!-- 参数行 -->
              <div class="grid grid-cols-2 md:grid-cols-5 gap-2">
                <div class="space-y-1">
                  <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">模型 (Model)</label>
                  <n-popselect v-model:value="settings.model" :options="modelOptions" trigger="click">
                    <button class="w-full flex justify-between items-center px-3 py-2 bg-gray-50 dark:bg-gray-900 rounded-lg text-sm font-bold hover:bg-blue-50 transition-colors truncate">
                      <span>{{ modelOptions.find(o => o.value === settings.model)?.label }}</span><span class="text-xs">▼</span>
                    </button>
                  </n-popselect>
                </div>
                <div class="space-y-1">
                  <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">学科</label>
                  <n-popselect v-model:value="settings.subject" :options="subjectOptions" trigger="click">
                    <button class="w-full flex justify-between items-center px-3 py-2 bg-gray-50 dark:bg-gray-900 rounded-lg text-sm font-bold hover:bg-yellow-50 transition-colors truncate">
                      <span>{{ getSubjectLabel(settings.subject) }}</span><span class="text-xs">▼</span>
                    </button>
                  </n-popselect>
                </div>
                <div class="space-y-1">
                  <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">年级</label>
                  <n-popselect v-model:value="settings.grade" :options="gradeOptions" trigger="click">
                    <button class="w-full flex justify-between items-center px-3 py-2 bg-gray-50 dark:bg-gray-900 rounded-lg text-sm font-bold hover:bg-green-50 transition-colors truncate">
                      <span>{{ getGradeLabel(settings.grade) }}</span><span class="text-xs">▼</span>
                    </button>
                  </n-popselect>
                </div>
                <div class="space-y-1">
                  <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">画幅</label>
                   <n-popselect v-model:value="settings.aspectRatio" :options="ratioOptions" trigger="click">
                    <button class="w-full flex justify-between items-center px-3 py-2 bg-gray-50 dark:bg-gray-900 rounded-lg text-sm font-bold hover:bg-gray-100 transition-colors truncate">
                      <span>{{ settings.aspectRatio }}</span><span class="text-xs">▼</span>
                    </button>
                  </n-popselect>
                </div>
                <div class="space-y-1">
                  <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">画质</label>
                   <n-popselect v-model:value="settings.quality" :options="qualityOptions" trigger="click">
                    <button class="w-full flex justify-between items-center px-3 py-2 bg-gray-50 dark:bg-gray-900 rounded-lg text-sm font-bold hover:bg-gray-100 transition-colors truncate">
                      <span>{{ getQualityLabel(settings.quality).split(' ')[0] }}</span><span class="text-xs">▼</span>
                    </button>
                  </n-popselect>
                </div>
              </div>

              <!-- 参考图 -->
              <div class="space-y-1">
                  <div class="flex justify-between items-center">
                     <label class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">参考图 {{ refImageUrls.length }}/4</label>
                     <button v-if="refImageUrls.length > 0" @click="refImageUrls = []" class="text-[10px] text-red-400 hover:underline">清空</button>
                  </div>
                  <n-upload action="/api/upload" :max="4" multiple list-type="image-card" @finish="handleUploadFinishWithStore" @remove="handleRemoveWithStore" class="block">
                    <div class="flex flex-col items-center justify-center text-gray-400 text-xs gap-1"><span class="text-lg">📸</span><span class="scale-90">上传</span></div>
                  </n-upload>
              </div>

              <!-- 输入框 -->
              <div class="space-y-2">
                 <div class="flex justify-between items-center">
                  <label class="text-xs font-bold text-gray-400 uppercase tracking-wider">提示词</label>
                   <button @click="handleOptimizePrompt" class="text-xs flex items-center gap-1 text-purple-600 hover:text-purple-800 font-bold transition-colors disabled:opacity-50" :disabled="!inputText.trim() || processing || optimizing">
                     <span v-if="optimizing" class="animate-spin">⏳</span><span v-else>🪄</span> 魔法润色
                   </button>
                 </div>
                 <textarea v-model="inputText" placeholder="描述一个清晰的画面..." class="w-full h-48 p-4 bg-gray-50 dark:bg-gray-900 rounded-xl border-none outline-none text-lg resize-none focus:ring-2 focus:ring-yellow-400 transition-all" @keydown.enter.ctrl="handleGenerateSingle"></textarea>
              </div>
  
              <div class="space-y-2">
                  <button @click="handleGenerateSingle" :disabled="!inputText.trim() || processing || optimizing" class="w-full py-4 bg-black dark:bg-white text-white dark:text-black rounded-xl font-bold text-lg hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed">
                    <span v-if="processing">绘制中...</span>
                    <span v-else>开始绘制</span>
                  </button>
              </div>
            </div>
          </div>
          
          <!-- 右侧：预览 -->
          <div class="flex flex-col gap-4">
              <div class="relative min-h-[500px] flex-1 flex items-center justify-center bg-gray-100 dark:bg-gray-800 rounded-3xl border-2 border-dashed border-gray-200 dark:border-gray-700 overflow-hidden group">
                   <div v-if="latestSingleTask && (latestSingleTask.status === 'processing' || latestSingleTask.status === 'pending')" class="absolute inset-0 flex flex-col items-center justify-center bg-white/80 dark:bg-gray-800/80 backdrop-blur z-20">
                      <div class="text-6xl animate-bounce mb-4">🍌</div>
                      <p class="font-bold text-gray-500">{{ latestSingleTask.statusMsg || '生成中...' }}</p>
                   </div>
                   <div v-if="currentDisplayImage" class="relative w-full h-full p-4 flex items-center justify-center">
                       <img :src="currentDisplayImage.url" class="max-w-full max-h-[600px] object-contain rounded-xl shadow-lg cursor-pointer" @click="openImage(currentDisplayImage)" />
                       <div class="absolute top-6 left-6 px-3 py-1 bg-black/60 backdrop-blur text-white text-xs rounded-full pointer-events-none">{{ getSubjectLabel(currentDisplayImage.subject) }}</div>
                   </div>
                   <div v-else-if="!processing" class="text-center text-gray-400"><div class="text-6xl mb-4">🎨</div><p>Ready to create</p></div>
                   
                   <!-- Image Modification Section Hidden Temporarily -->
                   <!--
                   <div v-if="currentDisplayImage && !processing" class="absolute bottom-0 left-0 right-0 bg-white/90 dark:bg-gray-800/90 backdrop-blur p-4 border-t border-gray-100 dark:border-gray-700 translate-y-full group-hover:translate-y-0 transition-transform duration-300">
                       <div class="flex gap-2">
                          <input v-model="modificationInput" placeholder="✨ Modify this image..." class="flex-1 bg-gray-50 dark:bg-gray-900 border-none outline-none px-4 py-2 rounded-lg text-sm" @keydown.enter="handleModify" />
                          <button @click="handleModify" :disabled="processing || !modificationInput" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-bold transition-colors disabled:opacity-50">Modify</button>
                       </div>
                    </div>
                    -->
              </div>
              <!-- 胶卷栏 -->
              <div v-if="recentHistory.length > 0" class="h-24 bg-white dark:bg-gray-800 rounded-2xl p-2 border border-gray-100 dark:border-gray-700 flex gap-2 overflow-x-auto custom-scrollbar">
                  <div v-for="img in recentHistory" :key="img.id" @click="handleHistorySelect(img)" class="relative flex-shrink-0 h-full aspect-square rounded-xl overflow-hidden cursor-pointer border-2 transition-all" :class="currentDisplayImage && currentDisplayImage.url === img.url ? 'border-black dark:border-white scale-95' : 'border-transparent hover:border-gray-300 opacity-70 hover:opacity-100'">
                     <img :src="img.thumbnail_url || img.url" class="w-full h-full object-cover" loading="lazy" />
                  </div>
              </div>
          </div>
        </div>
      </Transition>

      <!-- ==================== 页面 2: 批量工坊 ==================== -->
      <Transition name="fade" mode="out-in">
        <div v-if="currentTab === 'batch'" class="space-y-10">
          <section class="max-w-6xl mx-auto space-y-6">
             <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div class="md:col-span-1 bg-blue-50 dark:bg-gray-800 rounded-2xl p-6 border-2 border-dashed border-blue-200 dark:border-gray-600 flex flex-col justify-center items-center text-center space-y-4 hover:bg-blue-100 dark:hover:bg-gray-700 transition-colors cursor-pointer relative">
                 <input type="file" accept=".json" class="absolute inset-0 opacity-0 cursor-pointer" @change="handleJsonUpload" />
                 <div class="text-4xl">📂</div>
                 <div><h3 class="font-bold text-blue-800 dark:text-blue-300">导入 JSON</h3></div>
                 <button @click.stop="downloadTemplate" class="text-xs text-gray-500 underline hover:text-blue-600 z-10 relative">下载模板</button>
              </div>
              <!-- 右侧：文本输入区 -->
              <div class="md:col-span-2 bg-white dark:bg-gray-800 rounded-2xl shadow-xl overflow-hidden flex flex-col">
                 <div class="flex items-center gap-4 px-6 py-4 border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                    <span class="text-sm font-bold text-gray-500">默认设置:</span>
                    <n-popselect v-model:value="settings.model" :options="modelOptions"><button class="px-3 py-1 bg-white dark:bg-gray-700 rounded-md text-sm border">🤖 {{ modelOptions.find(o => o.value === settings.model)?.label }}</button></n-popselect>
                    <n-popselect v-model:value="settings.subject" :options="subjectOptions"><button class="px-3 py-1 bg-white dark:bg-gray-700 rounded-md text-sm border">🏷️ {{ getSubjectLabel(settings.subject) }}</button></n-popselect>
                    
                    <!-- Batch Reference Upload -->
                    <div class="flex-1 flex justify-end items-center gap-2">
                        <n-upload action="/api/upload" :max="4" multiple :show-file-list="false" @finish="handleBatchRefUpload" class="flex">
                            <button class="flex items-center gap-1 px-3 py-1 bg-white dark:bg-gray-700 rounded-md text-sm border hover:bg-gray-50 transition-colors">
                                <span>📸 参考图 ({{ batchRefImageUrls.length }})</span>
                            </button>
                        </n-upload>
                        <button v-if="batchRefImageUrls.length > 0" @click="batchRefImageUrls = []" class="text-xs text-red-400 hover:underline">清除</button>
                    </div>
                 </div>
                 <div class="relative flex-1">
                    <textarea v-model="batchInputText" placeholder="每行一个提示词..." class="w-full h-full min-h-[200px] p-6 bg-transparent border-none outline-none text-base resize-none font-mono"></textarea>
                    <div class="absolute bottom-6 right-6"><button @click="handleGenerateBatch" :disabled="!batchInputText.trim() || processing" class="px-8 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-full font-bold shadow-lg disabled:opacity-50">🚀 批量生成</button></div>
                 </div>
              </div>
            </div>
          </section>
          <section v-if="batchQueue.length > 0" class="max-w-[1600px] mx-auto px-6">
             <div class="flex items-center justify-between mb-6 bg-white dark:bg-gray-800 p-4 rounded-xl border border-gray-100 dark:border-gray-700 shadow-sm">
                <div class="flex items-center gap-4">
                    <h3 class="font-bold text-lg text-gray-700 dark:text-gray-200">任务队列 ({{ batchQueue.filter(t=>t.status==='done').length }}/{{ batchQueue.length }})</h3>
                    <div class="text-xs text-gray-400 bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">
                        {{ processing ? '运行中...' : '等待开始' }}
                    </div>
                </div>
                <div class="flex gap-3">
                   <button v-if="!processing && batchQueue.some(t => t.status === 'draft' || t.status === 'pending')" @click="startBatchProcessing" class="px-6 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg font-bold shadow-sm transition-all flex items-center gap-2">
                       <span>▶️</span> 开始生成
                   </button>
                   <button v-if="processing" @click="pauseBatchProcessing" class="px-6 py-2 bg-yellow-500 hover:bg-yellow-600 text-white rounded-lg font-bold shadow-sm transition-all flex items-center gap-2">
                       <span>⏸️</span> 暂停
                   </button>
                   <button v-if="batchQueue.some(t => t.status === 'done')" @click="downloadBatchResults" class="px-4 py-2 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-lg font-bold border border-blue-200 transition-all">
                       📦 打包下载
                   </button>
                   <button @click="batchQueue = []" class="px-4 py-2 bg-red-50 hover:bg-red-100 text-red-600 rounded-lg font-bold border border-red-200 transition-all">
                       🗑️ 清空
                   </button>
                </div>
             </div>
             
             <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                <TransitionGroup name="list">
                  <div v-for="task in reversedBatchQueue" :key="task.id" class="group relative bg-white dark:bg-gray-800 rounded-xl overflow-hidden border border-gray-100 dark:border-gray-700 shadow-sm hover:shadow-md transition-shadow flex flex-col">
                     <!-- Image Area -->
                     <div class="aspect-video relative bg-gray-100 dark:bg-gray-900 border-b border-gray-100 dark:border-gray-700">
                        <img v-if="task.status === 'done'" :src="task.resultUrl" class="w-full h-full object-contain cursor-pointer hover:opacity-90" @click="openImage(task)" />
                        <div v-else-if="task.status === 'pending'" class="w-full h-full flex flex-col items-center justify-center bg-yellow-50 text-yellow-600 gap-2">
                            <span class="text-2xl">⏳</span>
                            <span class="text-xs font-bold">排队中 (Pending)</span>
                        </div>
                        <div v-else-if="task.status === 'draft'" class="w-full h-full flex flex-col items-center justify-center bg-gray-50 text-gray-400 gap-2">
                            <span class="text-2xl">📝</span>
                            <span class="text-xs font-bold">草稿 (Ready)</span>
                        </div>
                        <div v-else-if="task.status === 'processing'" class="w-full h-full flex flex-col items-center justify-center bg-blue-50 text-blue-500 gap-2">
                            <div class="animate-spin text-2xl">⚡️</div>
                            <span class="text-xs font-bold">生成中...</span>
                        </div>
                        <div v-else class="w-full h-full flex flex-col items-center justify-center bg-red-50 text-red-400 gap-2">
                            <span class="text-2xl">⚠️</span>
                            <span class="text-xs">Failed</span>
                        </div>
                        
                        <!-- ID Badge -->
                        <div class="absolute top-2 left-2 px-1.5 py-0.5 bg-black/50 text-white text-[10px] rounded font-mono backdrop-blur">
                            #{{ task.id.slice(-4) }}
                        </div>
                     </div>
                     
                     <!-- Info Area -->
                     <div class="p-3 flex-1 flex flex-col gap-2">
                        <!-- Settings Tags -->
                        <div class="flex flex-wrap gap-1.5">
                            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-gray-100 text-gray-600 border border-gray-200">
                                {{ getSubjectLabel(task.settings.subject) }}
                            </span>
                            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-50 text-blue-600 border border-blue-100">
                                {{ task.settings.aspectRatio }}
                            </span>
                            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-purple-50 text-purple-600 border border-purple-100">
                                {{ getQualityLabel(task.settings.quality) }}
                            </span>
                            <span v-if="task.reference_image_urls && task.reference_image_urls.length" class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-green-50 text-green-600 border border-green-100 flex items-center gap-1">
                                📸 {{ task.reference_image_urls.length }}
                            </span>
                        </div>
                        
                        <!-- Prompt -->
                        <div class="flex items-start gap-2">
                            <p class="text-xs text-gray-600 dark:text-gray-300 line-clamp-3 leading-relaxed flex-1" :title="task.prompt">
                                {{ task.prompt }}
                            </p>
                            <button v-if="task.status === 'draft' || task.status === 'pending'" @click.stop="openEditTask(task)" class="text-xs text-blue-500 hover:bg-blue-50 p-1 rounded transition-colors" title="Edit Prompt">
                                ✏️
                            </button>
                        </div>
                     </div>
                  </div>
                </TransitionGroup>
             </div>
          </section>
        </div>
      </Transition>

      <!-- ==================== 页面 3: 数字人 (Digital Human) ==================== -->
      <!-- <Transition name="fade" mode="out-in">
        <div v-if="currentTab === 'digital_human'">
            <DigitalHumanPanel />
        </div>
      </Transition> -->

      <!-- ==================== 页面 3: 画廊 ==================== -->
      <Transition name="fade" mode="out-in">
        <div v-if="currentTab === 'gallery'" class="flex gap-8 max-w-[1600px] mx-auto min-h-[600px]">
          <aside class="w-64 flex-shrink-0 space-y-2">
            <h3 class="font-bold text-gray-400 px-4 mb-4 text-xs uppercase tracking-wider">过滤器</h3>
            <button @click="galleryFilter = 'all'" class="w-full text-left px-4 py-3 rounded-xl font-medium transition-colors flex justify-between items-center" :class="galleryFilter === 'all' ? 'bg-black text-white' : 'hover:bg-gray-100 text-gray-600'"><span>全部 (All)</span></button>
            <button v-for="sub in subjectOptions" :key="sub.value" @click="galleryFilter = sub.value" class="w-full text-left px-4 py-3 rounded-xl font-medium transition-colors flex justify-between items-center" :class="galleryFilter === sub.value ? 'bg-yellow-100 text-yellow-800' : 'hover:bg-gray-100 text-gray-600'"><span>{{ sub.icon }} {{ sub.label }}</span></button>
          </aside>
          <main class="flex-1 bg-white dark:bg-gray-800 rounded-3xl p-8 border border-gray-100 shadow-sm min-h-screen">
            <div class="flex items-center justify-between mb-6">
              <div class="text-sm text-gray-500">共 {{ filteredGallery.length }} 张图片</div>
              <div class="flex gap-4">
                  <label class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer"><input type="checkbox" v-model="showMyImages" class="h-4 w-4" /> 只看我的</label>
                  <label class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer"><input type="checkbox" v-model="showFeaturedOnly" class="h-4 w-4" /> 只看精选</label>
              </div>
            </div>
            <div v-if="filteredGallery.length === 0" class="h-full flex flex-col items-center justify-center text-gray-400"><div class="text-4xl mb-4">📭</div><p>暂无图片</p></div>
            <div v-else class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
               <div v-for="img in filteredGallery" :key="img.id" class="group relative aspect-square rounded-xl overflow-hidden cursor-pointer" @click="openImage(img)">
                 <img :src="img.thumbnail_url || img.url" class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110" loading="lazy" />
                 <div class="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-4">
                   <span class="text-white text-xs font-bold mb-1">{{ getSubjectLabel(img.subject) }}</span>
                 </div>
                 <div v-if="img.featured" class="absolute top-2 right-2 px-2 py-1 bg-yellow-400 text-black text-[10px] font-bold rounded-full shadow">精选</div>
                 <div v-if="img.is_mine" class="absolute top-2 left-2 px-2 py-1 bg-blue-500 text-white text-[10px] font-bold rounded-full shadow">ME</div>
                 <button v-if="authStore.user.username === 'admin'" @click.stop="toggleFeature(img)" class="absolute top-2 right-12 h-8 w-8 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black/80">
                     <span v-if="img.featured">★</span><span v-else>☆</span>
                 </button>
               </div>
            </div>
          </main>
        </div>
      </Transition>

      <!-- ==================== 页面 4: 设置 ==================== -->
      <Transition name="fade" mode="out-in">
        <div v-if="currentTab === 'settings'" class="max-w-4xl mx-auto space-y-8">
          
          <!-- Admin User Management Panel -->
          <div v-if="authStore.user.username === 'admin'" class="bg-white dark:bg-gray-800 rounded-3xl p-8 shadow-xl border border-gray-100 dark:border-gray-700 space-y-6">
             <div class="flex justify-between items-center">
                <h2 class="text-2xl font-bold">👤 用户管理 (Admin)</h2>
                <div class="flex gap-2">
                    <button @click="showCreateUserModal = true" class="px-4 py-2 bg-black text-white rounded-lg text-sm font-bold flex items-center gap-1">➕ 新增用户</button>
                    <button @click="fetchUsers" class="px-4 py-2 bg-gray-100 dark:bg-gray-700 rounded-lg text-sm font-bold">🔄 刷新列表</button>
                </div>
             </div>
             
             <div class="overflow-x-auto">
                <table class="w-full text-left text-sm">
                   <thead class="bg-gray-50 dark:bg-gray-700 text-gray-500 uppercase font-bold text-xs">
                      <tr>
                         <th class="px-4 py-3 rounded-l-lg">ID</th>
                         <th class="px-4 py-3">Username</th>
                         <th class="px-4 py-3">Role</th>
                         <th class="px-4 py-3">Quota (Used/Limit)</th>
                         <th class="px-4 py-3 rounded-r-lg">Actions</th>
                      </tr>
                   </thead>
                   <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
                      <tr v-for="u in usersList" :key="u.id" class="hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
                         <td class="px-4 py-3 font-mono text-gray-400">#{{ u.id }}</td>
                         <td class="px-4 py-3 font-bold">{{ u.username }}</td>
                         <td class="px-4 py-3">
                            <span v-if="u.is_pro" class="px-2 py-1 bg-purple-100 text-purple-700 rounded font-bold text-xs">PRO</span>
                            <span v-else class="px-2 py-1 bg-gray-100 text-gray-500 rounded font-bold text-xs">STD</span>
                         </td>
                         <td class="px-4 py-3">
                            <div class="flex items-center gap-2">
                               <span :class="{'text-red-500 font-bold': u.quota_used >= u.quota_limit}">{{ u.quota_used }}</span>
                               <span class="text-gray-400">/</span>
                               <input type="number" v-model="u.tempLimit" @blur="handleUpdateUser(u)" class="w-16 px-2 py-1 bg-gray-100 dark:bg-gray-900 rounded border border-transparent focus:border-blue-500 outline-none text-center" />
                            </div>
                         </td>
                         <td class="px-4 py-3">
                            <button @click="toggleUserPro(u)" class="text-xs font-bold underline" :class="u.is_pro ? 'text-red-500' : 'text-blue-500'">
                               {{ u.is_pro ? 'Demote' : 'Promote' }}
                            </button>
                         </td>
                      </tr>
                   </tbody>
                </table>
             </div>
          </div>
          
          <!-- Create User Modal -->
          <div v-if="showCreateUserModal" class="fixed inset-0 z-[600] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" @click.self="showCreateUserModal = false">
             <div class="bg-white dark:bg-gray-800 rounded-2xl p-6 w-full max-w-sm shadow-2xl animate-scale-in space-y-4">
                <h3 class="text-lg font-bold">Create New User</h3>
                <input v-model="newUserForm.username" type="text" placeholder="Username" class="w-full px-4 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg outline-none" />
                <input v-model="newUserForm.password" type="text" placeholder="Password" class="w-full px-4 py-2 bg-gray-50 dark:bg-gray-700 rounded-lg outline-none" />
                <div class="flex justify-end gap-2">
                    <button @click="showCreateUserModal = false" class="px-4 py-2 text-gray-500 hover:bg-gray-100 rounded-lg text-sm font-bold">Cancel</button>
                    <button @click="handleCreateUser" class="px-4 py-2 bg-black text-white rounded-lg text-sm font-bold" :disabled="!newUserForm.username || !newUserForm.password">Create</button>
                </div>
             </div>
          </div>

          <!-- BYOK Settings -->
          <div class="bg-white dark:bg-gray-800 rounded-3xl p-8 shadow-xl border border-gray-100 dark:border-gray-700 space-y-6">
            <h2 class="text-2xl font-bold">BYOK 设置</h2>
            <p class="text-sm text-gray-500">当额度耗尽或非Pro用户时，系统将使用以下配置调用模型。</p>
            <div class="space-y-4">
              <div>
                <label class="text-xs font-bold text-gray-400 uppercase tracking-wider block mb-2">API KEY</label>
                <input v-model="userModelKeyInput" type="password" placeholder="sk-..." class="w-full px-4 py-3 bg-gray-50 dark:bg-gray-900 rounded-xl outline-none" />
              </div>
              <div>
                <label class="text-xs font-bold text-gray-400 uppercase tracking-wider block mb-2">BASE_URL (Optional)</label>
                <input v-model="userModelBaseUrlInput" type="text" placeholder="https://..." class="w-full px-4 py-3 bg-gray-50 dark:bg-gray-900 rounded-xl outline-none" />
              </div>
            </div>
            <div class="flex justify-end">
              <button @click="handleSaveAccessKey" class="px-6 py-3 rounded-xl bg-black text-white font-bold">保存配置</button>
            </div>
          </div>
        </div>
      </Transition>

    </div>

    <!-- 弹窗：图片详情 -->
    <Transition name="fade">
      <div v-if="showModal && selectedImage" class="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-8" @click.self="closeModal">
         <div class="absolute inset-0 bg-black/90 backdrop-blur-sm"></div>
         <div class="relative bg-white dark:bg-gray-900 rounded-2xl w-full max-w-6xl max-h-[90vh] flex flex-col md:flex-row overflow-hidden shadow-2xl">
            <button @click="closeModal" class="absolute top-4 right-4 z-10 w-10 h-10 bg-black/50 hover:bg-black/70 text-white rounded-full flex items-center justify-center backdrop-blur">✕</button>
            
            <!-- Left: Image / Splitter Area -->
            <div class="flex-1 bg-black/5 dark:bg-black flex items-center justify-center p-4 overflow-hidden relative group select-none">
               
               <!-- Normal View -->
               <div v-if="!showSplitter" class="relative w-full h-full flex items-center justify-center">
                   <img :src="selectedImage.url" class="max-w-full max-h-full object-contain" />
                   <a :href="selectedImage.url" download class="absolute bottom-6 right-6 bg-white/90 text-black px-4 py-2 rounded-lg text-sm font-bold shadow">下载原图</a>
               </div>

               <!-- Splitter View -->
               <div v-else class="relative inline-block">
                   <img ref="imageRef" :src="selectedImage.url" class="max-w-full max-h-[80vh] block object-contain pointer-events-none" />
                   
                   <!-- Interaction Layer -->
                   <div 
                     class="absolute inset-0 cursor-crosshair z-10"
                     @mousedown="startCrop"
                     @mousemove="moveCrop"
                     @mouseup="endCrop"
                     @mouseleave="endCrop"
                   >
                        <!-- Existing Boxes -->
                        <div 
                            v-for="(box, idx) in cropBoxes" 
                            :key="idx"
                            class="absolute border-2 border-red-500 bg-red-500/20 z-20"
                            :style="{ left: box.x + 'px', top: box.y + 'px', width: box.w + 'px', height: box.h + 'px' }"
                        >
                            <button @click.stop="removeCrop(idx)" class="absolute -top-3 -right-3 w-5 h-5 bg-red-600 text-white rounded-full flex items-center justify-center text-xs">×</button>
                            <span class="absolute top-0 left-0 bg-red-600 text-white text-[9px] px-1">{{ idx + 1 }}</span>
                        </div>

                        <!-- Drawing Box -->
                        <div 
                            v-if="currentBox"
                            class="absolute border-2 border-yellow-400 bg-yellow-400/20 z-20"
                            :style="{ left: currentBox.x + 'px', top: currentBox.y + 'px', width: currentBox.w + 'px', height: currentBox.h + 'px' }"
                        ></div>
                   </div>
               </div>
               
               <!-- Splitter Toolbar (Moved Below) -->
               <div v-if="showSplitter" class="absolute bottom-4 left-0 right-0 flex gap-2 justify-center z-30 px-4 pointer-events-auto">
                    <button @click="cropBoxes = []" class="bg-gray-800/80 text-white px-4 py-2 rounded-lg text-sm hover:bg-gray-700 backdrop-blur">重置</button>
                    <button @click="downloadCrops" class="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-bold shadow hover:bg-green-700 flex items-center gap-1" :disabled="cropBoxes.length===0">
                        <span>📦</span> 下载 ZIP
                    </button>
                    <button @click="sendCropsToBatch" class="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-bold shadow hover:bg-blue-700 flex items-center gap-1" :disabled="cropBoxes.length===0">
                        <span>➡️</span> 发送到批量工坊
                    </button>
               </div>
            </div>

            <!-- Right: Info Panel -->
            <div class="w-full md:w-96 p-8 flex flex-col bg-white dark:bg-gray-900 overflow-y-auto">
               <h3 class="text-2xl font-bold mb-4">详情</h3>
               <p class="text-gray-600 bg-gray-50 p-4 rounded-xl mb-4 text-sm">{{ selectedImage.prompt }}</p>
               
               <div class="space-y-3">
                   <button @click="copyPrompt" class="w-full py-3 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200 rounded-xl font-bold">复制提示词</button>
                   <button @click="showSplitter = !showSplitter" class="w-full py-3 bg-black text-white rounded-xl font-bold flex items-center justify-center gap-2">
                       <span>{{ showSplitter ? '🔙 返回预览' : '✂️ 场景切分 (Split Tool)' }}</span>
                   </button>
               </div>
               
               <div v-if="showSplitter" class="mt-4 p-4 bg-yellow-50 text-yellow-800 rounded-xl text-xs">
                   <p class="font-bold mb-1">使用说明:</p>
                   <ul class="list-disc list-inside space-y-1">
                       <li>在左侧图片上<b>拖拽</b>框选每个场景。</li>
                       <li>可框选多个区域。</li>
                       <li>点击下方绿色按钮一键打包下载。</li>
                   </ul>
               </div>
            </div>
         </div>
      </div>
    </Transition>

    <!-- 弹窗：需要 API Key -->
    <Transition name="fade">
      <div v-if="showAccessKeyModal" class="fixed inset-0 z-[300] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
         <div class="bg-white dark:bg-gray-800 rounded-2xl p-8 w-full max-w-sm shadow-2xl animate-scale-in space-y-4 text-center">
            <h3 class="text-xl font-bold">需配置密钥</h3>
            <p class="text-xs text-gray-500">您的 Pro 额度已用完或您是普通用户，请输入 Key 继续使用。</p>
            <input type="password" v-model="userModelKeyInput" placeholder="sk-..." class="w-full px-4 py-3 bg-gray-50 dark:bg-gray-700 rounded-xl outline-none" />
            <input type="text" v-model="userModelBaseUrlInput" placeholder="https://..." class="w-full px-4 py-3 bg-gray-50 dark:bg-gray-700 rounded-xl outline-none" />
            <button @click="handleSaveAccessKey" class="w-full py-3 bg-black text-white rounded-xl font-bold">保存并重试</button>
            <button @click="showAccessKeyModal = false" class="text-gray-400 text-xs hover:underline">取消</button>
         </div>
      </div>
    </Transition>

    <!-- 弹窗：编辑任务提示词 -->
    <Transition name="fade">
      <div v-if="editingTask" class="fixed inset-0 z-[300] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" @click.self="cancelEditTask">
         <div class="bg-white dark:bg-gray-800 rounded-2xl p-6 w-full max-w-lg shadow-2xl animate-scale-in space-y-4">
            <h3 class="text-lg font-bold">编辑任务 (Edit Task)</h3>
            
            <!-- Reference Images Preview -->
            <div v-if="editingTask?.reference_image_urls?.length" class="space-y-1">
                <label class="text-[10px] font-bold text-gray-400 uppercase">Reference Images</label>
                <div class="flex gap-2 overflow-x-auto p-2 bg-gray-50 dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-700">
                    <div v-for="(url, idx) in editingTask.reference_image_urls" :key="idx" class="relative w-16 h-16 flex-shrink-0 rounded-lg overflow-hidden border border-gray-200">
                        <img :src="url" class="w-full h-full object-cover" />
                    </div>
                </div>
            </div>

            <!-- Settings Row -->
            <div class="grid grid-cols-3 gap-2">
                <div class="space-y-1">
                    <label class="text-[10px] font-bold text-gray-400 uppercase">Subject</label>
                    <select v-model="editTaskSettings.subject" class="w-full px-2 py-1.5 bg-gray-50 dark:bg-gray-700 rounded-lg text-sm border-none outline-none">
                        <option v-for="opt in subjectOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                    </select>
                </div>
                <div class="space-y-1">
                    <label class="text-[10px] font-bold text-gray-400 uppercase">Ratio</label>
                    <select v-model="editTaskSettings.aspectRatio" class="w-full px-2 py-1.5 bg-gray-50 dark:bg-gray-700 rounded-lg text-sm border-none outline-none">
                        <option v-for="opt in ratioOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                    </select>
                </div>
                <div class="space-y-1">
                    <label class="text-[10px] font-bold text-gray-400 uppercase">Quality</label>
                    <select v-model="editTaskSettings.quality" class="w-full px-2 py-1.5 bg-gray-50 dark:bg-gray-700 rounded-lg text-sm border-none outline-none">
                        <option v-for="opt in qualityOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                    </select>
                </div>
            </div>

            <div class="space-y-1">
                <div class="flex justify-between items-center">
                    <label class="text-[10px] font-bold text-gray-400 uppercase">Prompt</label>
                    <button @click="optimizeEditPrompt" class="text-[10px] text-purple-600 hover:text-purple-800 font-bold flex items-center gap-1" :disabled="optimizing">
                        <span v-if="optimizing" class="animate-spin">⏳</span>
                        <span v-else>🪄 魔法润色</span>
                    </button>
                </div>
                <textarea v-model="editPromptText" class="w-full h-32 p-3 bg-gray-50 dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 outline-none text-sm resize-none"></textarea>
            </div>

            <div class="flex justify-end gap-2">
                <button @click="cancelEditTask" class="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-600 rounded-lg text-sm font-bold">取消</button>
                <button @click="saveEditTask" class="px-4 py-2 bg-black text-white rounded-lg text-sm font-bold">保存</button>
            </div>
         </div>
      </div>
    </Transition>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive, watch } from 'vue'
import { NPopselect, useMessage, NUpload } from 'naive-ui'
import axios from 'axios'
import { useAuthStore } from '../stores/auth'
import DigitalHumanPanel from '../components/DigitalHumanPanel.vue'

const authStore = useAuthStore()
const message = useMessage()
const currentTab = ref('single')

// --- Auth Logic moved to Store, local state for form only ---
const authLoading = ref(false)
const loginForm = reactive({ username: '', password: '' })

// --- App State ---
const inputText = ref('') 
const modificationInput = ref('')
const batchInputText = ref('') 
const processing = ref(false)
const optimizing = ref(false)
const singleTasks = ref([]) 
const currentDisplayImage = ref(null) 
const batchQueue = ref([])
const refImageUrls = ref([])
const batchRefImageUrls = ref([])

// --- Gallery State ---
const galleryImages = ref([])
const galleryFilter = ref('all')
const showFeaturedOnly = ref(false)
const showMyImages = ref(false)
const showModal = ref(false)
const selectedImage = ref(null)

// --- BYOK State ---
const showAccessKeyModal = ref(false)
const userModelKeyInput = ref(localStorage.getItem('user_model_key') || '')
const userModelBaseUrlInput = ref(localStorage.getItem('user_model_base_url') || '')

// --- Admin State ---
const usersList = ref([])
const showCreateUserModal = ref(false)
const newUserForm = reactive({ username: '', password: '' })

const fetchUsers = async () => {
    try {
        const res = await axios.get('/api/admin/users')
        usersList.value = res.data.map(u => ({ ...u, tempLimit: u.quota_limit }))
    } catch(e) { message.error("Failed to fetch users") }
}

const handleCreateUser = async () => {
    if (!newUserForm.username || !newUserForm.password) return
    try {
        await axios.post('/api/auth/register', { ...newUserForm })
        message.success("User created")
        showCreateUserModal.value = false
        newUserForm.username = ''
        newUserForm.password = ''
        fetchUsers()
    } catch(e) {
        message.error(e.response?.data?.detail || "Creation failed")
    }
}

const handleUpdateUser = async (u) => {
    if (u.tempLimit === u.quota_limit) return
    try {
        await axios.post('/api/admin/update_user', {
            user_id: u.id,
            is_pro: Boolean(u.is_pro), // Ensure boolean
            quota_limit: parseInt(u.tempLimit)
        })
        u.quota_limit = parseInt(u.tempLimit)
        message.success("Quota updated")
    } catch(e) { message.error("Update failed") }
}

const toggleUserPro = async (u) => {
    const newStatus = !u.is_pro
    try {
        await axios.post('/api/admin/update_user', {
            user_id: u.id,
            is_pro: newStatus,
            quota_limit: u.quota_limit // Keep existing limit or reset? Keep for now.
        })
        u.is_pro = newStatus
        message.success(`User is now ${newStatus ? 'PRO' : 'Standard'}`)
    } catch(e) { message.error("Update failed") }
}

// --- Settings ---
const settings = ref({ 
    subject: 'general', 
    grade: 'general', 
    aspectRatio: '1:1', 
    style: 'vivid', 
    quality: 'standard',
    model: 'gemini-3-pro-image-preview' // Default model
})

// --- Options ---
const modelOptions = [
    { label: 'Gemini 3 Pro', value: 'gemini-3-pro-image-preview' },
    { label: 'Z-Image Turbo', value: 'z-image-turbo' },
    { label: 'GPT Image 1.5', value: 'gpt-image-1.5-all' }
]

const subjectOptions = [
  { label: '通用', value: 'general', icon: '🌐' },
  { label: '信息科技与AI', value: 'it_ai', icon: '🤖' },
  { label: '数学', value: 'math', icon: '📐' },
  { label: '物理', value: 'physics', icon: '🧪' },
  { label: '化学', value: 'chemistry', icon: '⚗️' },
  { label: '语文', value: 'chinese', icon: '📖' },
  { label: '英语', value: 'english', icon: '🔡' },
  { label: '史地生政/心理', value: 'humanities_psych', icon: '🧠' },
  { label: '音体美', value: 'arts_pe', icon: '🎨' },
  { label: '教材绘图', value: 'textbook', icon: '📚' }
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
  { label: '标准 (1K)', value: 'standard' },
  { label: '高质 (2K)', value: '2k' },
  { label: '超清 (4K)', value: '4k' }
]

// --- Computed ---
const getSubjectLabel = (val) => subjectOptions.find(o => o.value === val)?.label || val
const getGradeLabel = (val) => gradeOptions.find(o => o.value === val)?.label || val
const getQualityLabel = (val) => qualityOptions.find(o => o.value === val)?.label || val
const latestSingleTask = computed(() => singleTasks.value[singleTasks.value.length - 1] || null)
const reversedBatchQueue = computed(() => [...batchQueue.value].reverse())
const recentHistory = computed(() => galleryImages.value.filter(i => i.is_mine).slice(0, 10))

const filteredGallery = computed(() => {
  let imgs = galleryImages.value
  if (galleryFilter.value !== 'all') {
    imgs = imgs.filter(img => img.subject === galleryFilter.value)
  }
  if (showMyImages.value) {
      imgs = imgs.filter(img => img.is_mine)
  }
  if (showFeaturedOnly.value) {
      imgs = imgs.filter(img => img.featured)
  }
  return imgs
})

// --- Auth Logic Handlers ---
const handleAuthAction = async () => {
    if (!loginForm.username || !loginForm.password) return message.warning("Please fill in fields")
    authLoading.value = true
    try {
        await authStore.login(loginForm.username, loginForm.password)
        message.success("Welcome back!")
        fetchHistory()
    } catch (e) {
        message.error(e.response?.data?.detail || "Auth Failed")
    } finally {
        authLoading.value = false
    }
}

const handleGuestAccess = () => {
    authStore.enableGuestMode()
    message.info("Guest Mode Enabled. Please configure API Key.")
    showAccessKeyModal.value = true
}

// --- Watch for login state changes to fetch data ---
watch(() => authStore.isLoggedIn, (newVal) => {
    if (newVal) fetchHistory()
})

// --- Axios Interceptor ---
axios.interceptors.request.use(config => {
    const token = localStorage.getItem('token')
    if (token) config.headers['Authorization'] = `Bearer ${token}`
    
    // Add custom key if present
    const key = localStorage.getItem('user_model_key')
    const base = localStorage.getItem('user_model_base_url')
    if (key) config.headers['x-model-key'] = key
    if (base) config.headers['x-model-base-url'] = base
    
    return config
})

axios.interceptors.response.use(res => res, error => {
    if (error.response) {
        if (error.response.status === 401 && error.config.url.includes('/api/auth/me')) {
            authStore.logout()
        }
        else if ((error.response.status === 403 || error.response.status === 429) && !error.config.url.includes('auth')) {
             message.warning("Access Denied or Quota Exceeded. Please check API Key.")
             showAccessKeyModal.value = true
        }
    }
    return Promise.reject(error)
})

// --- Key Management ---
const handleSaveAccessKey = () => {
    localStorage.setItem('user_model_key', userModelKeyInput.value.trim())
    if (userModelBaseUrlInput.value.trim()) {
        localStorage.setItem('user_model_base_url', userModelBaseUrlInput.value.trim())
    } else {
        localStorage.removeItem('user_model_base_url')
    }
    showAccessKeyModal.value = false
    message.success("Configuration Saved")
}

// --- Gallery & Gen Logic (Simplified from original) ---
const fetchHistory = async () => {
    if (!authStore.isLoggedIn) return
    try {
        const res = await axios.get('/api/gallery')
        galleryImages.value = res.data
        if (!currentDisplayImage.value && galleryImages.value.length > 0) {
            handleHistorySelect(galleryImages.value.find(i => i.is_mine) || galleryImages.value[0])
        }
    } catch(e) {}
}

const handleHistorySelect = (img) => {
    currentDisplayImage.value = img
}

const handleGenerateSingle = async () => {
  if (!inputText.value.trim()) return
  const newTask = { id: Date.now(), prompt: inputText.value, status: 'pending', resultUrl: null, settings: { ...settings.value } }
  singleTasks.value.push(newTask)
  processing.value = true
  await executeTask(newTask)
  processing.value = false
  // Update quota display
  authStore.checkAuth()
}

const executeTask = async (task) => {
  task.status = 'processing'
  try {
     const mapAspectToSize = (ratio, model) => {
        // GPT Image 1.5 specific resolutions
        if (model === 'gpt-image-1.5') {
            if (ratio === '16:9') return '1536x1024'
            if (ratio === '9:16') return '1024x1536'
            return '1024x1024'
        }
        // Default (DALL-E 3, Gemini, Jimeng)
        if (ratio === '16:9') return '1792x1024'
        if (ratio === '9:16') return '1024x1792'
        return '1024x1024'
     }
     
     const res = await axios.post('/api/generate/single', {
        prompt: task.prompt,
        size: mapAspectToSize(task.settings.aspectRatio, task.settings.model),
        quality: task.settings.quality,
        style: task.settings.style,
        subject: task.settings.subject,
        grade: task.settings.grade,
        model: task.settings.model, 
        reference_image_urls: task.reference_image_urls || refImageUrls.value
     })
     task.status = 'done'
     task.resultUrl = res.data.url
     currentDisplayImage.value = { ...res.data, is_mine: true, featured: false, prompt: task.prompt } // simplify
     message.success("Generated!")
     fetchHistory()
  } catch (e) {
     task.status = 'failed'
     task.statusMsg = 'Failed'
     // Interceptor handles 403/429
  }
}

// --- Other Handlers (Optimize, Modify, Upload, Batch, Admin) ---
const handleOptimizePrompt = async () => {
    optimizing.value = true
    try {
        const res = await axios.post('/api/optimize_prompt', { 
            prompt: inputText.value, 
            subject: settings.value.subject,
            model: settings.value.model
        })
        inputText.value = res.data.optimized_prompt
    } catch(e) { message.error("Optimize failed") } 
    finally { optimizing.value = false }
}

const handleUploadFinishWithStore = ({ file, event }) => {
    try {
        const res = JSON.parse(event.target.response)
        if (res.success) {
            file.url = res.url
            refImageUrls.value.push(res.url)
            message.success('Uploaded')
        }
    } catch(e) {}
}

const handleBatchRefUpload = ({ file, event }) => {
    try {
        const res = JSON.parse(event.target.response)
        if (res.success) {
            batchRefImageUrls.value.push(res.url)
            message.success('Batch Ref Uploaded')
        }
    } catch(e) {}
}

const handleRemoveWithStore = ({ file }) => {
    if (file.url) refImageUrls.value = refImageUrls.value.filter(u => u !== file.url)
}

const openImage = (img) => {
    selectedImage.value = img
    showModal.value = true
}
const closeModal = () => { showModal.value = false }
const copyPrompt = () => {
    navigator.clipboard.writeText(selectedImage.value.prompt)
    message.success("Copied")
}

const toggleFeature = async (img) => {
    try {
        const res = await axios.post('/api/admin/toggle_feature', { filename: img.id, featured: !img.featured })
        img.featured = res.data.featured
        message.success("Updated")
    } catch(e) { message.error("Admin only") }
}

const handleJsonUpload = (event) => {
  const file = event.target.files[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const tasks = JSON.parse(e.target.result)
      if (!Array.isArray(tasks)) throw new Error('Root must be an array')
      // Capture current refs for this batch import
      const currentBatchRefs = [...batchRefImageUrls.value]

      const newTasks = tasks.map(t => ({
        id: Date.now() + Math.random().toString(),
        prompt: t.prompt,
        status: 'draft', 
        resultUrl: null,
        settings: {
          subject: t.subject || settings.value.subject,
          grade: t.grade || settings.value.grade,
          aspectRatio: t.aspectRatio || settings.value.aspectRatio,
          style: t.style || settings.value.style,
          quality: t.quality || settings.value.quality
        },
        reference_image_urls: currentBatchRefs // Apply global refs to JSON tasks
      }))
      
      batchQueue.value.push(...newTasks)
      
      // Optionally clear refs after import to avoid confusion for next batch?
      // Better to keep them visible until user clears, or clear them?
      // The button "Clear" is manual.
      // Let's NOT clear them here, so user can import another JSON with same refs if they want.
      // But wait, handleGenerateBatch clears them. Consistency?
      // Let's clear them to match handleGenerateBatch behavior.
      batchRefImageUrls.value = [] 
      
      message.success(`Imported ${newTasks.length} tasks. Click 'Start' to begin.`)
      // Do not auto-start
    } catch (err) { message.error('JSON Error') }
  }
  reader.readAsText(file)
  event.target.value = ''
}

const downloadTemplate = () => {
  const template = [
    { prompt: "Example: Heart anatomy", subject: "textbook", aspectRatio: "1:1", quality: "standard" },
    { prompt: "Example: Solar system", subject: "science", aspectRatio: "16:9", quality: "4k" }
  ]
  const blob = new Blob([JSON.stringify(template, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'template.json'
  a.click()
}

const handleGenerateBatch = async () => {
  const text = batchInputText.value.trim()
  if (!text) return
  const prompts = text.split('\n').map(p => p.trim()).filter(p => p.length > 0)
  
  // Capture current refs for this batch
  const currentBatchRefs = [...batchRefImageUrls.value]
  
  const newTasks = prompts.map(p => ({ 
      id: Date.now() + Math.random().toString(), 
      prompt: p, 
      status: 'draft', 
      resultUrl: null, 
      settings: { ...settings.value },
      reference_image_urls: currentBatchRefs // Attach refs to task
  }))
  
  batchQueue.value.push(...newTasks)
  batchInputText.value = ''
  batchRefImageUrls.value = [] // Clear after adding
  message.success(`${newTasks.length} tasks added to queue. Click 'Start' to begin.`)
}

const processBatchQueue = async () => {
  if (processing.value) return
  processing.value = true
  
  while (true) {
    if (paused.value) {
        break
    }
    const nextTask = batchQueue.value.find(t => t.status === 'pending')
    if (!nextTask) break
    
    await executeTask(nextTask)
    
    // Check pause again before waiting
    if (paused.value) break
    
    const hasMore = batchQueue.value.some(t => t.status === 'pending')
    if (nextTask.status === 'done' && hasMore) await new Promise(r => setTimeout(r, 1000))
  }
  processing.value = false
}

const paused = ref(false)

const startBatchProcessing = () => {
    paused.value = false
    // Convert all drafts to pending
    batchQueue.value.forEach(t => {
        if (t.status === 'draft') t.status = 'pending'
    })
    processBatchQueue()
}

// --- Prompt Editing Logic ---
const editingTask = ref(null)
const editPromptText = ref('')
const editTaskSettings = reactive({ subject: 'general', aspectRatio: '1:1', quality: 'standard' })

const openEditTask = (task) => {
    editingTask.value = task
    editPromptText.value = task.prompt
    // Copy settings
    editTaskSettings.subject = task.settings.subject || 'general'
    editTaskSettings.aspectRatio = task.settings.aspectRatio || '1:1'
    editTaskSettings.quality = task.settings.quality || 'standard'
}

const optimizeEditPrompt = async () => {
    if (!editPromptText.value.trim()) return
    optimizing.value = true
    try {
        const res = await axios.post('/api/optimize_prompt', { 
            prompt: editPromptText.value, 
            subject: editTaskSettings.subject,
            model: editingTask.value?.settings?.model || settings.value.model // Use task model or global fallback
        })
        editPromptText.value = res.data.optimized_prompt
        message.success('Prompt Optimized')
    } catch(e) { 
        message.error("Optimize failed") 
    } finally { 
        optimizing.value = false 
    }
}

const saveEditTask = () => {
    if (editingTask.value) {
        editingTask.value.prompt = editPromptText.value
        // Save settings back
        editingTask.value.settings.subject = editTaskSettings.subject
        editingTask.value.settings.aspectRatio = editTaskSettings.aspectRatio
        editingTask.value.settings.quality = editTaskSettings.quality
        
        editingTask.value = null
        editPromptText.value = ''
        message.success('Task updated')
    }
}

const cancelEditTask = () => {
    editingTask.value = null
    editPromptText.value = ''
}

const pauseBatchProcessing = () => {
    paused.value = true
    message.warning("Batch processing paused")
}

const downloadBatchResults = async () => {
    const doneTasks = batchQueue.value.filter(t => t.status === 'done' && t.resultUrl)
    if (doneTasks.length === 0) return
    message.loading('Packing...')
    try {
        const filenames = doneTasks.map(t => t.resultUrl.split('/').pop())
        const response = await axios.post('/api/download/batch', { filenames }, { responseType: 'blob' })
        const url = window.URL.createObjectURL(new Blob([response.data]))
        const link = document.createElement('a')
        link.href = url
        link.setAttribute('download', `Batch_${Date.now()}.zip`)
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
    } catch (err) { message.error('Download failed') }
}

const handleModify = async () => {
  const currentTask = currentDisplayImage.value
  if (!currentTask || !currentTask.url || !modificationInput.value.trim()) return
  const modPrompt = modificationInput.value.trim()
  modificationInput.value = ''
  processing.value = true
  const newTask = { id: Date.now(), prompt: `Modify: ${modPrompt}`, status: 'processing', resultUrl: null, settings: { ...settings.value } }
  singleTasks.value.push(newTask)
  try {
    const res = await axios.post('/api/generate/modify', { prompt: modPrompt, original_image_url: currentTask.url })
    newTask.status = 'done'
    newTask.resultUrl = res.data.url
    currentDisplayImage.value = { ...res.data, is_mine: true, prompt: newTask.prompt, featured: false }
    message.success('Modified')
    fetchHistory()
  } catch(e) { 
      newTask.status = 'failed'
      message.error("Modify Failed")
  } finally {
      processing.value = false
  }
}

// --- Splitter Tool Logic ---
// Updated with Batch Integration
const showSplitter = ref(false)
const cropBoxes = ref([])
const isDrawing = ref(false)
const startPos = ref({ x: 0, y: 0 })
const currentBox = ref(null)
const imageRef = ref(null)

const startCrop = (e) => {
    e.preventDefault()
    if (!imageRef.value) return
    const rect = imageRef.value.getBoundingClientRect()
    isDrawing.value = true
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    startPos.value = { x, y }
    currentBox.value = { x, y, w: 0, h: 0 }
}

const moveCrop = (e) => {
    if (!isDrawing.value || !imageRef.value) return
    const rect = imageRef.value.getBoundingClientRect()
    const currentX = e.clientX - rect.left
    const currentY = e.clientY - rect.top
    
    const width = currentX - startPos.value.x
    const height = currentY - startPos.value.y
    
    currentBox.value = {
        x: width > 0 ? startPos.value.x : currentX,
        y: height > 0 ? startPos.value.y : currentY,
        w: Math.abs(width),
        h: Math.abs(height)
    }
}

const endCrop = () => {
    if (!isDrawing.value) return
    isDrawing.value = false
    if (currentBox.value && currentBox.value.w > 10 && currentBox.value.h > 10) {
        cropBoxes.value.push({ ...currentBox.value })
    }
    currentBox.value = null
}

const removeCrop = (index) => {
    cropBoxes.value.splice(index, 1)
}

const downloadCrops = async () => {
    if (cropBoxes.value.length === 0) return
    // ... existing logic ...
    const realCrops = getRealCrops() // Refactor this out to reuse
    
    message.loading('Processing crops...')
    try {
        const res = await axios.post('/api/tools/crop_and_zip', {
            image_url: selectedImage.value.url,
            crops: realCrops
        }, { responseType: 'blob' })
        
        const url = window.URL.createObjectURL(new Blob([res.data]))
        const link = document.createElement('a')
        link.href = url
        link.setAttribute('download', `scenes_${Date.now()}.zip`)
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        message.success('Download started')
    } catch (e) {
        message.error('Crop failed')
    }
}

// Helper
const getRealCrops = () => {
    if (!imageRef.value) return []
    const naturalWidth = imageRef.value.naturalWidth
    const displayWidth = imageRef.value.width
    const scale = naturalWidth / displayWidth
    return cropBoxes.value.map(box => ({
        x: Math.round(box.x * scale),
        y: Math.round(box.y * scale),
        w: Math.round(box.w * scale),
        h: Math.round(box.h * scale)
    }))
}

const sendCropsToBatch = async () => {
    if (cropBoxes.value.length === 0) return
    const realCrops = getRealCrops()
    
    message.loading('Preparing batch tasks...')
    try {
        const res = await axios.post('/api/tools/crop_to_urls', {
            image_url: selectedImage.value.url,
            crops: realCrops
        })
        
        if (res.data.success) {
            const urls = res.data.urls
            const newTasks = urls.map((url, idx) => ({
                id: Date.now() + Math.random().toString(),
                prompt: `Scene ${idx + 1}: `, // Placeholder
                status: 'draft',
                resultUrl: null,
                settings: { ...settings.value }, // Inherit current global settings
                reference_image_urls: [url] // Unique ref per task
            }))
            
            batchQueue.value.push(...newTasks)
            
            // Navigate
            currentTab.value = 'batch'
            showModal.value = false
            resetSplitter()
            message.success(`Created ${newTasks.length} batch tasks from scenes!`)
        }
    } catch (e) {
        message.error('Failed to send to batch')
    }
}

const resetSplitter = () => {
    cropBoxes.value = []
    showSplitter.value = false
}

// Reset splitter when modal closes
watch(showModal, (val) => {
    if (!val) resetSplitter()
})

onMounted(() => {
    // Auth check is now in App.vue, but we still want to ensure history is fetched if already logged in
    if (authStore.isLoggedIn) fetchHistory()
})
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.list-enter-active, .list-leave-active { transition: all 0.5s ease; }
.list-enter-from { opacity: 0; transform: translateY(20px); }
</style>