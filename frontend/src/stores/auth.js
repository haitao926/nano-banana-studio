import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'
import { useMessage } from 'naive-ui'

export const useAuthStore = defineStore('auth', () => {
    const user = ref({ username: '', is_pro: false, quota_remaining: 0, quota_limit: 0 })
    const isLoggedIn = ref(false)
    const isGuest = ref(false)
    const token = ref(localStorage.getItem('token') || '')

    async function checkAuth() {
        if (!token.value) return
        try {
            const res = await axios.get('/api/auth/me', { 
                headers: { Authorization: `Bearer ${token.value}` } 
            })
            user.value = res.data
            isLoggedIn.value = true
            isGuest.value = false
        } catch (e) {
            logout()
        }
    }

    function enableGuestMode() {
        isGuest.value = true
        user.value = { username: 'Guest', is_pro: false, quota_remaining: 0, quota_limit: 0 }
    }

    async function login(username, password) {
        const formData = new FormData()
        formData.append('username', username)
        formData.append('password', password)
        const res = await axios.post('/api/auth/login', formData)
        token.value = res.data.access_token
        localStorage.setItem('token', token.value)
        isGuest.value = false
        await checkAuth()
    }

    async function register(username, password) {
        await axios.post('/api/auth/register', { username, password })
    }

    function logout() {
        token.value = ''
        localStorage.removeItem('token')
        isLoggedIn.value = false
        isGuest.value = false
        user.value = { username: '', is_pro: false, quota_remaining: 0, quota_limit: 0 }
    }

    return {
        user,
        isLoggedIn,
        isGuest,
        token,
        checkAuth,
        enableGuestMode,
        login,
        register,
        logout
    }
})
