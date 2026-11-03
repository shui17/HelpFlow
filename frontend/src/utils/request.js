import axios from 'axios'
import { getToken, removeToken } from './token.js'

let unauthorized = () => {}
export const onUnauthorized = (handler) => { unauthorized = handler }
const request = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1', timeout: 15000, headers: { 'Content-Type': 'application/json' } })
request.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
request.interceptors.response.use((response) => response.data.data, (error) => {
  // 仅处理携带当前会话 Token 的失败，登录失败不能清除其它会话。
  const sentToken = error.config?.headers?.Authorization
  if (error.response?.status === 401 && sentToken && sentToken === `Bearer ${getToken()}`) {
    removeToken()
    unauthorized()
  }
  return Promise.reject(error)
})
export default request
