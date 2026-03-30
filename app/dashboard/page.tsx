import Link from "next/link"
import { getLatestSession, getSession } from "@/lib/store"
import { StatTile } from "@/components/stat-tile"
import { DashboardTable } from "@/components/dashboard-table"

interface PageProps {
  searchParams: Promise<{ sessionId?: string }>
}

export default async function DashboardPage({ searchParams }: PageProps) {
  const { sessionId } = await searchParams
  const session = sessionId ? getSession(sessionId) : getLatestSession()

  if (!session) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-foreground">Live Dashboard</h1>
          <p className="text-muted-foreground">
            No sessions found. <Link href="/" className="text-primary hover:underline">Generate an audit first.</Link>
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-foreground">Live Dashboard</h1>
        <p className="text-muted-foreground">
          Session <code className="px-2 py-1 bg-muted rounded text-sm">{session.id.slice(0, 8)}</code>
          {" "}&mdash; Scope: <strong>{session.scopeLabel}</strong>
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <StatTile label="Total Rooms" value={session.totalRooms} />
        <StatTile label="With Vehicle Info" value={session.roomsWithVehicles} variant="success" />
        <StatTile label="Not In VM System" value={session.notInSystem} variant="warning" />
        {session.hasDepartures && (
          <>
            <StatTile label="Due Outs" value={session.dueOuts} variant="destructive" />
            <StatTile label="Stayovers" value={session.stayovers} variant="info" />
          </>
        )}
      </div>

      {/* Data Table */}
      <DashboardTable session={session} />
    </div>
  )
}
