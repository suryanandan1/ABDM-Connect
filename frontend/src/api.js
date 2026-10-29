import axios from 'axios'

// The token lives in sessionStorage: it is gone when the browser tab is closed.
const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api/v1' })

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Expired or revoked token: go back to the login page (but not for a failed login itself).
    if (error.response?.status === 401 && !error.config.url.includes('/auth/login')) {
      sessionStorage.removeItem('token')
      window.location.href = '/login?expired=1'
    }
    return Promise.reject(error)
  },
)

// Turn any API error into a readable sentence.
export function errorText(error) {
  const detail = error.response?.data?.detail
  if (!error.response) return 'Cannot reach the server. Is the backend running on port 8000?'
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (typeof d === 'string' ? d : `${d.loc.slice(1).join(' → ')}: ${d.msg}`))
      .join('\n')
  }
  return `Request failed (${error.response.status})`
}

export default api
