/** axios 封装 - 自动注入 X-Admin-Key */
import axios, { type AxiosInstance, type AxiosResponse } from 'axios'
import { createDiscreteApi } from 'naive-ui'

const { message } = createDiscreteApi(['message'])

// ── health API ──
export const healthAPI = {
  overview: () => api.get('/admin/health/overview'),
  platforms: () => api.get('/admin/health/platforms'),
  rateLimit: (providerId: number) => api.get(`/admin/health/rate-limit/${providerId}`),
}

// ── rates API ──
export const ratesAPI = {
  list: () => api.get('/admin/rates'),
  update: (id: number, data: any) => api.put(`/admin/rates/${id}`, data),
  models: () => api.get('/admin/rates/models'),
  updateModel: (model: string, data: any) => api.put(`/admin/rates/models/${encodeURIComponent(model)}`, data),
}
export const platformsAPI = {
  list: () => api.get('/admin/platforms'),
  get: (id: number) => api.get(`/admin/platforms/${id}`),
  create: (data: any) => api.post('/admin/platforms', data),
  update: (id: number, data: any) => api.put(`/admin/platforms/${id}`, data),
  delete: (id: number) => api.delete(`/admin/platforms/${id}`),
  listKeys: (platformId: number) => api.get(`/admin/platforms/${platformId}/keys`),
  addKey: (platformId: number, data: any) => api.post(`/admin/platforms/${platformId}/keys`, data),
  updateKey: (platformId: number, keyId: number, data: any) => api.put(`/admin/platforms/${platformId}/keys/${keyId}`, data),
  deleteKey: (platformId: number, keyId: number) => api.delete(`/admin/platforms/${platformId}/keys/${keyId}`),
}

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