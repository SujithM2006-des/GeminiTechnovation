import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Inbox, AlertTriangle, X, CheckCircle2, ShieldAlert, UserX, UserCheck, HelpCircle } from 'lucide-react'
import type { IdentityStatus, RiskLevel } from './types'
import { SAFETY_DISCLAIMER, safetyMeasures } from './safety'

export const DISCLAIMER_1 = 'Body area, risk and injury notes are AI estimates, NOT a confirmed diagnosis.'
export const DISCLAIMER_2 = 'This system is intended for screening and decision support only. Final clinical assessment must be performed by a qualified medical professional.'

export const btn = 'inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed'
export const btnP = `${btn} bg-[#0b1f3a] text-white hover:bg-[#16325c]`
export const btnS = `${btn} border border-slate-300 bg-white text-slate-700 hover:bg-slate-50`
export const btnD = `${btn} bg-red-600 text-white hover:bg-red-700`
export const inp = 'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm'
/** Same as inp but without w-full (for filter bars) */
export const inpAuto = 'rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm'

export const Card = ({ children, className = '' }: { children: ReactNode; className?: string }) => (
  <div className={`rounded-2xl border border-slate-200 bg-white p-5 shadow-sm ${className}`}>{children}</div>
)

const tones = {
  green: 'bg-green-100 text-green-800',
  amber: 'bg-amber-100 text-amber-800',
  red: 'bg-red-100 text-red-800',
  blue: 'bg-blue-100 text-blue-800',
  violet: 'bg-violet-100 text-violet-800',
  orange: 'bg-orange-100 text-orange-800',
  gray: 'bg-slate-100 text-slate-700',
}
export type Tone = keyof typeof tones

export const Badge = ({ tone = 'gray', children, title }: { tone?: Tone; children: ReactNode; title?: string }) => (
  <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${tones[tone]}`}>
    {children}
  </span>
)

export const RiskBadge = ({ level }: { level: RiskLevel | null }) =>
  level ? (
    <Badge tone={level === 'HIGH' ? 'red' : level === 'MEDIUM' ? 'amber' : 'green'}>
      {level === 'HIGH' && <ShieldAlert size={12} />}
      {level}
    </Badge>
  ) : (
    <Badge>Unrated</Badge>
  )

/** Confirmed / Uncertain / Unknown. `label` replaces the default text, e.g. "Jersey number · 94%". */
export const IdentityBadge = ({ s, label, title }: { s: IdentityStatus; label?: string | null; title?: string }) =>
  s === 'CONFIRMED' ? (
    <Badge tone="green" title={title}><UserCheck size={12} />{label || 'Confirmed'}</Badge>
  ) : s === 'UNCERTAIN' ? (
    <Badge tone="amber" title={title}><HelpCircle size={12} />{label || 'Uncertain'}</Badge>
  ) : (
    <Badge tone="orange" title={title}><UserX size={12} />Unidentified</Badge>
  )

export const EmptyState = ({ title, text, action }: { title: string; text?: string; action?: ReactNode }) => (
  <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
    <Inbox className="text-slate-400" size={32} />
    <p className="font-semibold">{title}</p>
    {text && <p className="max-w-md text-sm text-slate-500">{text}</p>}
    {action}
  </div>
)

export const ErrorState = ({ title, text, onRetry }: { title: string; text?: string; onRetry?: () => void }) => (
  <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
    <AlertTriangle className="text-red-500" size={32} />
    <p className="font-semibold">{title}</p>
    {text && <p className="text-sm text-slate-500">{text}</p>}
    {onRetry && <button className={btnS} onClick={onRetry}>Try again</button>}
  </div>
)

export const Skeleton = ({ className = 'h-4 w-full' }: { className?: string }) => (
  <div className={`animate-pulse rounded bg-slate-200 ${className}`} />
)

export const Disclaimer = () => (
  <div role="note" className="rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
    <p className="font-semibold">{DISCLAIMER_1}</p>
    <p className="mt-1">{DISCLAIMER_2}</p>
  </div>
)

export const Na = ({ v }: { v?: string | number | null }) => <>{v === null || v === undefined || v === '' ? '—' : v}</>

export const Field = ({ label, err, children }: { label: string; err?: string; children: ReactNode }) => (
  <label className="block text-sm">
    <span className="mb-1 block font-medium">{label}</span>
    {children}
    {err && <span role="alert" className="mt-1 block text-xs text-red-600">{err}</span>}
  </label>
)

const SAFETY_TONE: Record<RiskLevel, { box: string; head: string }> = {
  HIGH: { box: 'border-red-200 bg-red-50', head: 'text-red-800' },
  MEDIUM: { box: 'border-amber-200 bg-amber-50', head: 'text-amber-800' },
  LOW: { box: 'border-green-200 bg-green-50', head: 'text-green-800' },
}

/** Recommended first-aid / referral steps for one event (same text as the WhatsApp alert). */
export function SafetyMeasures({ eventType, region, risk }: { eventType: string; region: string | null; risk: RiskLevel | null }) {
  const steps = safetyMeasures(eventType, region, risk)
  if (!steps.length) return null
  const t = SAFETY_TONE[risk ?? 'LOW']
  return (
    <div className={`rounded-xl border p-3 text-sm text-slate-800 ${t.box}`}>
      <p className={`text-xs font-semibold uppercase tracking-wide ${t.head}`}>Recommended safety measures</p>
      <ul className="mt-1 list-disc space-y-0.5 pl-5">
        {steps.map((s) => <li key={s}>{s}</li>)}
      </ul>
      <p className="mt-1 text-xs text-slate-500">{SAFETY_DISCLAIMER}</p>
    </div>
  )
}

export function PageHeader({ title, crumbs = [], actions, back = true }: { title: string; crumbs?: { label: string; to?: string }[]; actions?: ReactNode; back?: boolean }) {
  const nav = useNavigate()
  return (
    <div className="mb-5">
      <nav aria-label="Breadcrumb" className="mb-1 flex flex-wrap items-center gap-1 text-xs text-slate-500">
        <Link to="/" className="hover:underline">Home</Link>
        {crumbs.map((c) => (
          <span key={c.label} className="flex gap-1">
            / {c.to ? <Link to={c.to} className="hover:underline">{c.label}</Link> : <span aria-current="page">{c.label}</span>}
          </span>
        ))}
      </nav>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {back && <button aria-label="Back" className={btnS + ' !px-2'} onClick={() => nav(-1)}><ArrowLeft size={16} /></button>}
          <h1 className="text-2xl font-bold">{title}</h1>
        </div>
        <div className="flex flex-wrap gap-2">{actions}</div>
      </div>
    </div>
  )
}

export function Modal({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4" role="dialog" aria-modal="true" aria-label={title} onClick={onClose}>
      <div className="max-h-[90vh] w-full max-w-lg overflow-auto rounded-2xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button aria-label="Close" onClick={onClose}><X size={18} /></button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function Confirm({ open, title, text, confirmLabel, onConfirm, onClose }: { open: boolean; title: string; text: string; confirmLabel: string; onConfirm: () => void; onClose: () => void }) {
  return (
    <Modal open={open} title={title} onClose={onClose}>
      <p className="text-sm text-slate-600">{text}</p>
      <div className="mt-5 flex justify-end gap-2">
        <button className={btnS} onClick={onClose}>Cancel</button>
        <button className={btnD} onClick={() => { onConfirm(); onClose() }}>{confirmLabel}</button>
      </div>
    </Modal>
  )
}

type T = { id: number; msg: string; err?: boolean }
const TC = createContext<(m: string, err?: boolean) => void>(() => {})
export const useToast = () => useContext(TC)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [ts, setTs] = useState<T[]>([])
  const push = useCallback((msg: string, err?: boolean) => {
    const id = Date.now() + Math.random()
    setTs((t) => [...t, { id, msg, err }])
    setTimeout(() => setTs((t) => t.filter((x) => x.id !== id)), 4000)
  }, [])
  return (
    <TC.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-[60] space-y-2" aria-live="polite">
        {ts.map((t) => (
          <div key={t.id} className={`flex items-center gap-2 rounded-lg px-4 py-3 text-sm text-white shadow-lg ${t.err ? 'bg-red-600' : 'bg-[#0b1f3a]'}`}>
            {!t.err && <CheckCircle2 size={16} />}
            {t.msg}
          </div>
        ))}
      </div>
    </TC.Provider>
  )
}