import type { AuditSession } from "./types"

// In-memory store for sessions (for demo purposes - in production use a database)
const sessions: Map<string, AuditSession> = new Map()

export function saveSession(session: AuditSession): void {
  sessions.set(session.id, session)
}

export function getSession(id: string): AuditSession | undefined {
  return sessions.get(id)
}

export function getAllSessions(): AuditSession[] {
  return Array.from(sessions.values()).sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  )
}

export function deleteSession(id: string): boolean {
  return sessions.delete(id)
}

export function getLatestSession(): AuditSession | undefined {
  const all = getAllSessions()
  return all.length > 0 ? all[0] : undefined
}
