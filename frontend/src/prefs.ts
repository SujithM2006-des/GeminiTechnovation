import { useSyncExternalStore } from 'react'
import type { RiskLevel } from './types'

/**
 * Personal settings (Settings page → Preferences / Notifications), saved in this browser per username.
 * Nothing is set until a user saves their settings, so the defaults keep every page exactly as before.
 */
export interface Prefs {
  /** '' = this computer's normal format */
  timeFormat: '' | '12h' | '24h'
  /** Risk levels shown in Alerts and the notification bell */
  alertRisks: RiskLevel[]
}

export const DEFAULT_PREFS: Prefs = { timeFormat: '', alertRisks: ['HIGH', 'MEDIUM', 'LOW'] }

const KEY = 'athleteguard_prefs'
const USER_KEY = 'athleteguard_user'
const EVENT = 'athleteguard-prefs'

const readAll = (): Record<string, Prefs> => {
  try { return JSON.parse(localStorage.getItem(KEY) ?? '{}') as Record<string, Prefs> } catch { return {} }
}

const currentUsername = (): string | null => {
  try { return (JSON.parse(localStorage.getItem(USER_KEY) ?? 'null') as { name?: string } | null)?.name ?? null } catch { return null }
}

export function getPrefs(username: string | null = currentUsername()): Prefs {
  const saved = username ? readAll()[username] : undefined
  return { ...DEFAULT_PREFS, ...(saved ?? {}) }
}

export function savePrefs(username: string, p: Prefs) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...readAll(), [username]: p }))
  } catch {
    /* storage full or blocked: settings simply aren't remembered */
  }
  window.dispatchEvent(new Event(EVENT))
}

/** Options for toLocaleString(); undefined = unchanged default format */
export const dateOptions = (): Intl.DateTimeFormatOptions | undefined => {
  const t = getPrefs().timeFormat
  return t ? { hour12: t === '12h' } : undefined
}

const subscribe = (fn: () => void) => {
  window.addEventListener(EVENT, fn)
  window.addEventListener('storage', fn)
  return () => { window.removeEventListener(EVENT, fn); window.removeEventListener('storage', fn) }
}

/** Re-renders when the settings are saved */
export function usePrefs(username: string | null | undefined): Prefs {
  const raw = useSyncExternalStore(subscribe, () => JSON.stringify(getPrefs(username ?? null)))
  return JSON.parse(raw) as Prefs
}