import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api'

export const useAuthStore = defineStore('auth', () => {
  const adminKey = ref(localStorage.getItem('admin_key') || '')

  async function login(password: string) {
    const res = await api.post('/admin/login', { password })
    if (res.data.ok) {
      adminKey.value = res.data.admin_key
      localStorage.setItem('admin_key', res.data.admin_key)
      return true
    }
    return false
  }

  async function verify() {
    const key = localStorage.getItem('admin_key')
    if (!key) return false
    try {
      await api.get('/admin/verify')
      adminKey.value = key
      return true
    } catch {
      logout()
      return false
    }
  }

  function logout() {
    adminKey.value = ''
    localStorage.removeItem('admin_key')
  }

  return { adminKey, login, verify, logout }
})