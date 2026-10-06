import { api } from '../client'
import { EP } from '../endpoints'
import type { EventDto, LoginDto, MatchDto, PlayerDto, SystemDto, TeamDto, UserDto } from '../dto'
import { toEvent, toMatch, toPlayer, toTeam, toUser, type AppUser } from '../mappers'
import type { InjuryEvent, Match, Player, RiskLevel, Role, Team } from '../../types'

export async function login(username: string, password: string): Promise<LoginDto> {
  return (await api.post<LoginDto>(EP.login, { username, password })).data
}

/** Medical/admin get every event; coaches get their team's events plus Unidentified ones. */
export async function getEvents(matchId?: number | null): Promise<InjuryEvent[]> {
  const r = await api.get<EventDto[]>(EP.events, { params: matchId ? { match_id: matchId } : {} })
  return r.data.map(toEvent)
}

export async function getPlayers(): Promise<Player[]> {
  return (await api.get<PlayerDto[]>(EP.players)).data.map(toPlayer)
}

/** Admin/medical: both teams. Coach: own team only. */
export async function getTeams(): Promise<Team[]> {
  return (await api.get<TeamDto[]>(EP.teams)).data.map(toTeam)
}

export async function getMatches(): Promise<Match[]> {
  return (await api.get<MatchDto[]>(EP.matches)).data.map(toMatch)
}

/** Any role for an Unidentified event; only medical/admin can change an identified one. */
export async function assignPlayer(eventId: number, playerId: number): Promise<InjuryEvent | null> {
  const r = await api.patch<{ event?: EventDto }>(EP.assign(eventId), { player_id: playerId })
  return r.data.event ? toEvent(r.data.event) : null
}

/** Medical only. */
export async function logManualEvent(v: { playerId: number; eventType: string; note: string; risk: RiskLevel; matchId: number | null }) {
  await api.post(EP.manualEvent, { player_id: v.playerId, event_type: v.eventType, note: v.note, risk: v.risk, match_session_id: v.matchId })
}

/** Admin only. Players and teams are kept. */
export async function clearAllEvents(): Promise<number> {
  return (await api.delete<{ deleted_events: number }>(EP.clearEvents)).data.deleted_events
}

/** Admin only: every login account. */
export async function getUsers(): Promise<AppUser[]> {
  return (await api.get<UserDto[]>(EP.users)).data.map(toUser)
}

/** Admin only. Username is plain text (e.g. "coach3"); a coach needs a team. */
export async function createUser(v: { username: string; password: string; role: Role; teamId: number | null }): Promise<AppUser> {
  const r = await api.post<{ user: UserDto }>(EP.users, { username: v.username, password: v.password, role: v.role.toLowerCase(), team_id: v.role === 'COACH' ? v.teamId : null })
  return toUser(r.data.user)
}

/** Admin only. You cannot delete yourself or the last admin. */
export async function deleteUser(id: number): Promise<void> {
  await api.delete(EP.user(id))
}

/** Admin only: backend, database, detector, identification and medical knowledge base status. */
export async function getSystemStatus(): Promise<SystemDto> {
  return (await api.get<SystemDto>(EP.system)).data
}