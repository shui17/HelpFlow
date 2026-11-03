import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as api from '../api/auth.js'
import { getToken, setToken, removeToken } from '../utils/token.js'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(getToken())
  const currentUser = ref(null)
  const initialized = ref(false)
  let pending
  const isAuthenticated = computed(() => Boolean(token.value && currentUser.value))
  const role = computed(() => currentUser.value?.role)
  function logout() { token.value = null; currentUser.value = null; removeToken(); initialized.value = true }
  async function fetchCurrentUser() { currentUser.value = await api.getCurrentUser(); return currentUser.value }
  async function login(payload) {
    const result = await api.login(payload)
    token.value = result.access_token
    setToken(token.value)
    try { await fetchCurrentUser(); initialized.value = true } catch (error) { logout(); throw error }
  }
  async function initialize() {
    if (initialized.value) return
    if (!pending) pending = (async () => {
      try {
        if (token.value) await fetchCurrentUser()
        initialized.value = true
      } catch (error) {
        if ([401, 403].includes(error.response?.status)) logout()
        else throw error
      } finally { pending = null }
    })()
    await pending
  }
  async function changePassword(payload) { await api.changePassword(payload); logout() }
  return { token, currentUser, initialized, isAuthenticated, role, login, logout, initialize, fetchCurrentUser, changePassword, register: api.register }
})
