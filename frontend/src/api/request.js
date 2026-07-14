import axios from 'axios'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 响应拦截器：统一错误处理
request.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    console.error('[API Error]', msg)
    return Promise.reject(new Error(msg))
  }
)

export default request
