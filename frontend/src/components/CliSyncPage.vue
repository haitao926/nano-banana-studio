<template>
  <div class="min-h-screen bg-[radial-gradient(circle_at_top,_#f8fafc,_#e2e8f0_55%,_#cbd5e1)] text-slate-900">
    <div class="mx-auto flex min-h-screen max-w-3xl items-center px-6 py-12">
      <section class="w-full rounded-[28px] border border-white/60 bg-white/85 p-8 shadow-[0_24px_80px_-32px_rgba(15,23,42,0.35)] backdrop-blur-xl">
        <p class="text-xs font-black uppercase tracking-[0.28em] text-slate-500">CLI Sync</p>
        <h1 class="mt-3 text-3xl font-black tracking-tight text-slate-950">把当前浏览器登录态授权给 CLI</h1>
        <p class="mt-3 text-sm leading-7 text-slate-600">
          这一步不会让你重新输入密码。确认后，系统会基于当前网页登录态为 CLI 签发一份独立会话。
        </p>

        <div class="mt-8 rounded-3xl border border-slate-200 bg-slate-50/80 p-5">
          <div class="flex flex-wrap items-center gap-3">
            <span class="rounded-full bg-slate-900 px-3 py-1 text-xs font-bold text-white">Code</span>
            <code class="text-lg font-black tracking-[0.2em] text-indigo-700">{{ displayUserCode }}</code>
          </div>
          <p class="mt-3 text-sm text-slate-500">CLI 正在等待这个浏览器确认授权。</p>
        </div>

        <div class="mt-8 space-y-4">
          <div v-if="loading" class="rounded-2xl border border-slate-200 bg-white px-4 py-4 text-sm text-slate-600">
            正在确认当前登录态...
          </div>

          <div v-else-if="!authStore.isLoggedIn" class="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-800">
            当前浏览器还没有有效登录态，请先在这个页面所属站点登录，再回来刷新本页。
          </div>

          <div v-else-if="approved" class="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-800">
            已授权给 CLI。回到终端，`nbs auth sync-web` 会自动完成本地会话写入。
          </div>

          <div v-else-if="errorMessage" class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-800">
            {{ errorMessage }}
          </div>
        </div>

        <div class="mt-8 flex flex-wrap gap-3">
          <button
            class="rounded-2xl bg-slate-950 px-5 py-3 text-sm font-black text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
            :disabled="!authStore.isLoggedIn || !canApprove || submitting || approved"
            @click="approve"
          >
            {{ submitting ? '授权中...' : approved ? '已授权' : '确认授权 CLI' }}
          </button>
          <button
            class="rounded-2xl border border-slate-300 bg-white px-5 py-3 text-sm font-bold text-slate-700 transition hover:border-slate-400 hover:text-slate-950"
            @click="refreshAuthState"
          >
            刷新登录态
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const loading = ref(true)
const submitting = ref(false)
const approved = ref(false)
const errorMessage = ref('')

const params = new URLSearchParams(window.location.search)
const deviceCode = (params.get('device_code') || '').trim()
const userCode = (params.get('user_code') || '').trim().toUpperCase()

const canApprove = computed(() => Boolean(deviceCode || userCode))
const displayUserCode = computed(() => userCode || '缺少授权码')

async function refreshAuthState() {
  loading.value = true
  errorMessage.value = ''
  try {
    await authStore.checkAuth()
    if (authStore.isLoggedIn) {
      await authStore.refreshProfile({ retry: true })
    }
  } catch (_) {
    // auth store already tracks state; surface a simpler message in UI.
  } finally {
    loading.value = false
  }
}

async function approve() {
  if (!canApprove.value || submitting.value) return
  submitting.value = true
  errorMessage.value = ''
  try {
    await api.post('/api/auth/cli/device/approve', {
      device_code: deviceCode || undefined,
      user_code: userCode || undefined
    })
    approved.value = true
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || '授权失败，请稍后重试。'
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  void refreshAuthState()
})
</script>
