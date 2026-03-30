"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import type { AuditSession } from "@/lib/types"
import { Eye, LayoutDashboard, Trash2, Calendar, Hash } from "lucide-react"

interface SessionListProps {
  initialSessions: AuditSession[]
}

export function SessionList({ initialSessions }: SessionListProps) {
  const [sessions, setSessions] = useState(initialSessions)
  const router = useRouter()

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this session?")) return

    try {
      const response = await fetch(`/api/sessions/${id}`, { method: "DELETE" })
      if (response.ok) {
        setSessions((prev) => prev.filter((s) => s.id !== id))
      }
    } catch (error) {
      console.error("Failed to delete session:", error)
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    })
  }

  return (
    <div className="space-y-3">
      {sessions.map((session) => (
        <div
          key={session.id}
          className="p-4 rounded-xl border border-border bg-card"
        >
          <div className="flex flex-col sm:flex-row sm:items-center gap-4">
            {/* Session Info */}
            <div className="flex-1 space-y-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-foreground">{session.scopeLabel}</span>
                <code className="px-2 py-0.5 bg-muted rounded text-xs text-muted-foreground">
                  {session.id.slice(0, 8)}
                </code>
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Hash className="w-4 h-4" />
                  {session.totalRooms} rooms
                </span>
                <span className="flex items-center gap-1">
                  <Calendar className="w-4 h-4" />
                  {formatDate(session.createdAt)}
                </span>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="px-2 py-1 rounded-full bg-[hsl(var(--success))]/10 text-[hsl(var(--success))]">
                  {session.roomsWithVehicles} with info
                </span>
                <span className="px-2 py-1 rounded-full bg-[hsl(var(--warning))]/10 text-[hsl(var(--warning))]">
                  {session.notInSystem} not in VM
                </span>
                {session.hasDepartures && (
                  <>
                    <span className="px-2 py-1 rounded-full bg-destructive/10 text-destructive">
                      {session.dueOuts} due out
                    </span>
                    <span className="px-2 py-1 rounded-full bg-[hsl(var(--info))]/10 text-[hsl(var(--info))]">
                      {session.stayovers} stayover
                    </span>
                  </>
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              <Link
                href={`/preview/${session.id}`}
                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium min-h-[44px]"
              >
                <Eye className="w-4 h-4" />
                <span className="hidden sm:inline">Preview</span>
              </Link>
              <Link
                href={`/dashboard?sessionId=${session.id}`}
                className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border text-foreground text-sm font-medium min-h-[44px]"
              >
                <LayoutDashboard className="w-4 h-4" />
                <span className="hidden sm:inline">Dashboard</span>
              </Link>
              <button
                onClick={() => handleDelete(session.id)}
                className="flex items-center justify-center w-11 h-11 rounded-lg border border-border text-muted-foreground hover:text-destructive hover:border-destructive transition-colors"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
