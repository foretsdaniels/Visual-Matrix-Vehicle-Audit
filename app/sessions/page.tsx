import Link from "next/link"
import { getAllSessions } from "@/lib/store"
import { SessionList } from "@/components/session-list"

export default function SessionsPage() {
  const sessions = getAllSessions()

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-foreground">Audit Sessions</h1>
        <p className="text-muted-foreground">
          View and manage your recent parking audit sessions.
        </p>
      </div>

      {sessions.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-muted-foreground mb-4">No sessions found.</p>
          <Link
            href="/"
            className="inline-flex items-center justify-center px-6 py-3 rounded-lg bg-primary text-primary-foreground font-medium min-h-[44px]"
          >
            Generate Your First Audit
          </Link>
        </div>
      ) : (
        <SessionList initialSessions={sessions} />
      )}
    </div>
  )
}
