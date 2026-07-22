/** axios 封装 - 自动注入 X-Admin-Key */
import axios, { type AxiosInstance, type AxiosResponse } from 'axios'
import { createDiscreteApi } from 'naive-ui'

const { message } = createDiscreteApi(['message'])

const api: AxiosInstance = axios.create({
  // 开发时指向本地后端；生产用相对路径（同源）
  baseURL: import.meta.env.VITE_API_BASE || '',
  withCredentials: false,
  timeout: 30000,
})

// 请求拦截：注入 admin key
api.interceptors.request.use((config) => {
  const key = localStorage.getItem('admin_key')
  if (key) {
    config.headers['X-Admin-Key'] = key
  }
  return config
})

// 响应拦截：401 → 跳转登录
api.interceptors.response.use(
  (res: AxiosResponse) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('admin_key')
      message.error('会话过期，请重新登录')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api