import axios, { AxiosError } from 'axios'

// Backend address. Defaults to the local FastAPI server; override with VITE_API_BASE_URL in .env.
const envBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim()
export const API_BASE = envBase ? envBase.replace(/\/$/, '') : 'http://127.0.0.1:8000'
export const isConnected = true

// Token + user are kept in localStorage so a page refresh keeps you logged in.
const TOKEN_KEY = 'access_token'
export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

// Developer preview (no login, no data): API calls are switched off.
let dev = false
export const devMode = { get: () => dev, set: (v: boolean) => { dev = v } }

export const api = axios.create({ baseURL: API_BASE, timeout: 15000 })

api.interceptors.request.use((c) => {
  const t = tokenStore.get()
  if (t) c.headers.Authorization = `Bearer ${t}`
  return c
})

// Expired or invalid session (tokens last 8 hours) -> back to the login page
let onUnauthorized: (() => void) | null = null
export const setUnauthorizedHandler = (fn: () => void) => { onUnauthorized = fn }

api.interceptors.response.use(
  (r) => r,
  (e: AxiosError) => {
    const isLogin = e.config?.url?.includes('/auth/login')
    if (e.response?.status === 401 && !isLogin && onUnauthorized) onUnauthorized()
    return Promise.reject(e)
  },
)

export function normalizeApiError(e: unknown): string {
  if (!(e instanceof AxiosError)) return e instanceof Error ? e.message : 'Something went wrong.'
  if (!e.response) return `Can't reach the backend at ${API_BASE}. Is it running?`
  const s = e.response.status
  const d = (e.response.data as { detail?: unknown })?.detail
  if (typeof d === 'string' && s !== 401) return d
  if (s === 401) return 'Invalid username or password, or your session has expired.'
  if (s === 403) return 'You are not authorized to do this.'
  if (s === 404) return 'The requested resource was not found.'
  if (s === 422) return 'Some fields are invalid.'
  if (s >= 500) return 'Something went wrong on the server. Please try again.'
  return 'Request failed.'
}