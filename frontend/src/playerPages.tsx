/* =====================================================================
   PLAYER DASHBOARD
   A player login (created by the admin in Users -> Create user -> Player) only sees
   their own data: profile, previous injury history, current injury events and report.
   The backend filters every list to that one player.
   ===================================================================== */
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { CalendarDays, CheckCircle2, Download, ExternalLink, FileText, HeartPulse, Lock, Shield } from 'lucide-react'
import { useAuth } from './auth'
import { getMe } from './api/services'
import { normalizeApiError } from './api/client'
import { useAssessments, useEvents, useInjuryHistory } from './queries'
import type { InjuryEvent } from './types'
import type { AssessmentDto } from './api/dto'
import { Badge, Card, EmptyState, ErrorState, Na, PageHeader, RiskBadge, SafetyMeasures, Skeleton, btnS } from './ui'
import { EventLine, PossibleInjuries, PreviousInjuries, ReportsPage, ROLE_ACCESS, STATUS_TONE, btnSm, fmtDate, fmtVideo, kpiLabel } from './pages'

/** The logged-in player's account (name, jersey, team, coach). */
const useMe = () => {
  const { user } = useAuth()
  return useQuery({ queryKey: ['me'], queryFn: getMe, enabled: !!user && !user.dev })
}

const newestFirst = (a: InjuryEvent, b: InjuryEvent) => +new Date(b.timestamp) - +new Date(a.timestamp)

/** Assessment outcome per event (players get the status only, never the clinical notes). */
const useReviewByEvent = () => {
  const a = useAssessments()
  const map = new Map<number, AssessmentDto>()
  for (const r of a.data ?? []) map.set(r.event_id, r)
  return map
}

/** One fall: clip on the left, possible injuries, rest, safety measures and review status on the right. */
function FallCard({ e, review }: { e: InjuryEvent; review?: AssessmentDto }) {
  return (
    <div className="grid gap-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      <div>
        {e.clipUrl ? (
          <video className="aspect-video w-full rounded-xl bg-black" src={e.clipUrl} controls preload="metadata" />
        ) : (
          <div className="grid aspect-video place-items-center rounded-xl bg-slate-100 text-sm text-slate-500">{e.source === 'manual' ? 'Logged by staff — no video' : 'No clip saved for this event'}</div>
        )}
      </div>
      <div className="flex min-w-0 flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="blue">{e.eventType}</Badge>
          <RiskBadge level={e.risk} />
          <span className="text-sm font-semibold text-slate-600">{e.region ?? 'Body area not recorded'}</span>
          <span className="ml-auto">{review ? <Badge tone={STATUS_TONE[review.status] ?? 'gray'}>{review.status}</Badge> : <Badge tone={e.resolved ? 'green' : 'gray'}>{e.resolved ? 'Reviewed' : 'Waiting for medical review'}</Badge>}</span>
        </div>
        <PossibleInjuries e={e} />
        <SafetyMeasures eventType={e.eventType} region={e.region} risk={e.risk} />
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
          <dt className="text-slate-500">Match</dt><dd className="truncate" title={e.matchName ?? ''}>{e.matchName ?? 'No match'}</dd>
          <dt className="text-slate-500">Time in video</dt><dd><Na v={fmtVideo(e.videoTimeSec)} /></dd>
          <dt className="text-slate-500">Recorded</dt><dd>{fmtDate(e.timestamp)}</dd>
          {review && <><dt className="text-slate-500">Medical review</dt><dd>{review.status} · {fmtDate(review.saved_at)}</dd></>}
        </dl>
        <div className="mt-auto flex flex-wrap gap-2">
          <Link to={`/events/${e.id}`} className={btnSm}><ExternalLink size={14} />Open event</Link>
          {e.clipUrl && <a href={e.clipUrl} download className={btnSm}><Download size={14} />Download clip</a>}
        </div>
      </div>
    </div>
  )
}

function FallList({ list, loading, error, retry, emptyTitle, emptyText }: { list: InjuryEvent[]; loading: boolean; error: unknown; retry: () => void; emptyTitle: string; emptyText: string }) {
  const reviews = useReviewByEvent()
  if (loading) return <Card><div className="space-y-2"><Skeleton /><Skeleton /></div></Card>
  if (error) return <Card><ErrorState title="Unable to load your injury events" text={normalizeApiError(error)} onRetry={retry} /></Card>
  if (!list.length) return <Card><EmptyState title={emptyTitle} text={emptyText} /></Card>
  return <div className="space-y-3">{list.map((e) => <FallCard key={e.id} e={e} review={reviews.get(e.id)} />)}</div>
}

/* ---------- Dashboard ---------- */
export function PlayerDashboard() {
  const { user } = useAuth()
  const me = useMe()
  const ev = useEvents()
  const h = useInjuryHistory()
  const dev = !!user?.dev

  const all = [...(ev.data ?? [])].sort(newestFirst)
  const current = all.filter((e) => !e.resolved)
  const restFrom = current.find((e) => e.aiInjury?.rest) ?? all.find((e) => e.aiInjury?.rest)
  const name = me.data?.playerName ?? user?.name ?? 'Player'

  const KPI: [string, number | string | null, string?][] = [
    ['Current injury events', ev.data ? current.length : null, current.length ? 'text-red-700' : ''],
    ['Expected rest', ev.data ? restFrom?.aiInjury?.rest ?? '—' : null, 'text-amber-600'],
    ['Previous injuries', h.data ? h.data.length : null],
    ['High-risk falls', ev.data ? all.filter((e) => e.risk === 'HIGH').length : null, 'text-red-700'],
  ]

  return (
    <>
      <PageHeader back={false} title="Player dashboard" crumbs={[{ label: 'Dashboard' }]} actions={<Link to="/player/reports" className={btnS}><FileText size={16} />My report</Link>} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {KPI.map(([k, v, t]) => <Card key={k}><p className={kpiLabel}>{k}</p>{ev.isLoading ? <Skeleton className="mt-2 h-8 w-12" /> : <p className={`mt-1 truncate font-bold ${typeof v === 'string' ? 'text-2xl' : 'text-3xl'} ${t ?? ''}`} title={typeof v === 'string' ? v : undefined}><Na v={v} /></p>}</Card>)}
      </div>
      <p className="mt-2 text-xs text-slate-500">{dev ? 'Metrics are shown only when real backend data is available.' : `Welcome, ${name}. You see only your own injury data.`}</p>

      <div className="mt-5">
        <Card>
          <div className="flex items-center justify-between"><h2 className="font-semibold">Current injury events</h2>{all.length > 0 && <Link to="/player/events" className={btnSm}>View all</Link>}</div>
          {ev.isError ? <ErrorState title="Unable to load your injury events" text={normalizeApiError(ev.error)} onRetry={() => ev.refetch()} />
            : ev.isLoading ? <div className="mt-3 space-y-2"><Skeleton /><Skeleton /></div>
            : current.length === 0 ? <EmptyState title="No current injury events" text="Falls detected in a match video that are not reviewed yet appear here." />
            : <ul className="mt-2 divide-y divide-slate-100">{current.slice(0, 6).map((e) => <EventLine key={e.id} e={e} />)}</ul>}
        </Card>
      </div>

      <div className="mt-4">
        <Card>
          {me.data?.playerId ? <PreviousInjuries playerId={me.data.playerId} name={name} />
            : <><h2 className="flex items-center gap-2 font-semibold"><HeartPulse size={18} className="text-rose-600" />Previous injury history</h2><p className="mt-2 text-sm text-slate-500">{dev ? 'Log in with a player account to see your injury history.' : me.isLoading ? 'Loading…' : 'This login is not linked to a player yet. Ask your administrator.'}</p></>}
          <div className="mt-3"><Link to="/player/history" className={btnSm}>Open full history</Link></div>
        </Card>
      </div>
    </>
  )
}

/* ---------- Profile ---------- */
export function PlayerProfile() {
  const { user } = useAuth()
  const me = useMe()
  const ev = useEvents()
  const h = useInjuryHistory()
  if (!user) return null

  const d = me.data
  const name = d?.playerName ?? user.name
  const events = ev.data ?? []

  const Info = ({ label, value }: { label: string; value: ReactNode }) => (
    <div className="flex items-center justify-between gap-4 border-b border-slate-100 py-3.5 last:border-0">
      <dt className="text-sm text-slate-500">{label}</dt>
      <dd className="flex items-center gap-2 text-right text-sm font-semibold text-slate-800">{value}<Lock size={13} className="shrink-0 text-slate-300" aria-label="Set by the administrator" /></dd>
    </div>
  )
  const Stat = ({ label, value, tone = '' }: { label: string; value: ReactNode; tone?: string }) => (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4"><p className="text-xs text-slate-500">{label}</p><p className={`mt-1 text-2xl font-bold ${tone}`}>{value}</p></div>
  )

  return (
    <>
      <PageHeader title="Profile" crumbs={[{ label: 'Profile' }]} />

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="h-28 bg-gradient-to-r from-[#0b1f3a] via-[#16325c] to-sky-600" />
        <div className="flex flex-wrap items-end gap-5 px-6 pb-6">
          <span className="-mt-12 grid h-24 w-24 shrink-0 place-items-center rounded-2xl border-4 border-white bg-sky-500 text-3xl font-bold text-white shadow-md">{d?.jersey !== null && d?.jersey !== undefined ? `#${d.jersey}` : (name[0] || '?').toUpperCase()}</span>
          <div className="min-w-0 flex-1 pt-3">
            <h2 className="truncate text-2xl font-bold">{name}</h2>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-slate-500">
              <Badge tone="violet">Player</Badge>
              <span className="flex items-center gap-1"><Shield size={14} />{me.isLoading ? 'Loading team…' : d?.teamName ?? 'No team'}</span>
              <span className="flex items-center gap-1"><CheckCircle2 size={14} className="text-green-600" />Active account</span>
            </div>
          </div>
          <p className="flex items-center gap-1.5 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500"><Lock size={13} />Managed by the administrator</p>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="font-semibold">Player details</h2>
          <p className="text-xs text-slate-500">These details are set by the administrator and cannot be changed here.</p>
          {me.isError && <p role="alert" className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-800">{normalizeApiError(me.error)}</p>}
          <dl className="mt-2">
            <Info label="Player" value={d?.playerName ?? '—'} />
            <Info label="Jersey number" value={d?.jersey !== null && d?.jersey !== undefined ? `#${d.jersey}` : '—'} />
            <Info label="Team" value={d?.teamName ?? '—'} />
            <Info label="Coach" value={d?.coaches.length ? d.coaches.join(', ') : '—'} />
            <Info label="Username" value={d?.username ?? user.name} />
            <Info label="Account status" value={<span className="text-green-700">Active</span>} />
          </dl>
        </Card>

        <Card>
          <h2 className="font-semibold">What you can do</h2>
          <p className="text-xs text-slate-500">Access given to player logins.</p>
          <ul className="mt-3 space-y-2.5">
            {ROLE_ACCESS.PLAYER.map((t) => <li key={t} className="flex items-start gap-2 text-sm text-slate-700"><CheckCircle2 size={16} className="mt-0.5 shrink-0 text-green-600" />{t}</li>)}
          </ul>
          <p className="mt-4 rounded-lg bg-slate-50 p-3 text-xs text-slate-500">Something wrong in your details or need a new password? Contact your administrator.</p>
        </Card>
      </div>

      <Card className="mt-4">
        <h2 className="font-semibold">Your injuries at a glance</h2>
        <div className="mt-3 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Detected falls" value={ev.isLoading ? '…' : events.length} />
          <Stat label="Current injury events" value={ev.isLoading ? '…' : events.filter((e) => !e.resolved).length} tone="text-red-700" />
          <Stat label="Reviewed by medical staff" value={ev.isLoading ? '…' : events.filter((e) => e.resolved).length} tone="text-green-700" />
          <Stat label="Previous injuries" value={h.isLoading ? '…' : (h.data ?? []).length} tone="text-amber-600" />
        </div>
      </Card>
    </>
  )
}

/* ---------- History: previous injuries + falls already reviewed ---------- */
export function PlayerHistoryPage() {
  const { user } = useAuth()
  const me = useMe()
  const ev = useEvents()
  const past = (ev.data ?? []).filter((e) => e.resolved).sort(newestFirst)
  const name = me.data?.playerName ?? user?.name ?? 'Player'

  return (
    <>
      <PageHeader title="Injury history" crumbs={[{ label: 'History' }]} />
      <Card>
        {me.data?.playerId ? <PreviousInjuries playerId={me.data.playerId} name={name} />
          : <p className="text-sm text-slate-500">{user?.dev ? 'Log in with a player account to see your injury history.' : me.isLoading ? 'Loading…' : 'This login is not linked to a player yet. Ask your administrator.'}</p>}
      </Card>
      <h2 className="mb-3 mt-6 flex items-center gap-2 font-semibold"><CalendarDays size={18} className="text-sky-600" />Past detected falls <span className="text-sm font-normal text-slate-500">· reviewed by medical staff</span></h2>
      <FallList list={past} loading={ev.isLoading} error={ev.isError ? ev.error : null} retry={() => ev.refetch()} emptyTitle="No past falls" emptyText="Falls appear here once medical staff have reviewed them." />
    </>
  )
}

/* ---------- Events: current (not yet reviewed) injury events ---------- */
export function PlayerEvents() {
  const ev = useEvents()
  const current = (ev.data ?? []).filter((e) => !e.resolved).sort(newestFirst)
  return (
    <>
      <PageHeader title="My injury events" crumbs={[{ label: 'Events' }]} />
      <p className="mb-3 text-sm text-slate-500">Falls detected in match videos that are still waiting for, or under, medical review. Reviewed falls move to History.</p>
      <FallList list={current} loading={ev.isLoading} error={ev.isError ? ev.error : null} retry={() => ev.refetch()} emptyTitle="No current injury events" emptyText="You have no falls waiting for medical review." />
    </>
  )
}

/* ---------- Reports: the same report page, filled with this player's events only ---------- */
export function PlayerReports() {
  return <ReportsPage />
}