// Endpoints of the AthleteGuard FastAPI backend (backend/main.py).
export const EP = {
  login: '/auth/login',
  events: '/events',
  manualEvent: '/events/manual',
  assign: (id: number) => `/events/${id}/assign`,
  players: '/players',
  teams: '/teams',
  matches: '/matches',
  clearEvents: '/admin/players/clear',
  users: '/admin/users',
  user: (id: number) => `/admin/users/${id}`,
  system: '/admin/system',
}