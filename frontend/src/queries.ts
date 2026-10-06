import { useQuery } from '@tanstack/react-query'
import { getEvents, getMatches, getPlayers, getTeams } from './api/services'
import { devMode } from './api/client'

// In developer preview there is no login, so nothing is fetched.
const on = () => !devMode.get()

// Live data: events refresh every 3 s (same as the old dashboard), teams every 5 s, matches every 10 s.
export const useEvents = (matchId?: number | null) =>
  useQuery({ queryKey: ['events', matchId ?? 'all'], queryFn: () => getEvents(matchId), refetchInterval: 3000, enabled: on() })

export const useTeams = () => useQuery({ queryKey: ['teams'], queryFn: getTeams, refetchInterval: 5000, enabled: on() })

export const useMatches = () => useQuery({ queryKey: ['matches'], queryFn: getMatches, refetchInterval: 10000, enabled: on() })

/** Both teams, every role (needed to identify an Unidentified fall). Loaded once. */
export const usePlayers = () => useQuery({ queryKey: ['players'], queryFn: getPlayers, staleTime: Infinity, enabled: on() })