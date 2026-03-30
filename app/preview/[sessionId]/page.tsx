import { notFound } from "next/navigation"
import Link from "next/link"
import { getSession } from "@/lib/store"
import { buildPreviewLines } from "@/lib/parser"
import { StatTile } from "@/components/stat-tile"
import { LabelPreview } from "@/components/label-preview"
import { FileText, Printer, LayoutDashboard, ArrowLeft } from "lucide-react"

interface PageProps {
  params: Promise<{ sessionId: string }>
}

export default async function PreviewPage({ params }: PageProps) {
  const { sessionId } = await params
  const session = getSession(sessionId)

  if (!session) {
    notFound()
  }

  const previewLines = buildPreviewLines(session.entries, session.hasDepartures)

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-foreground">Audit Preview</h1>
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

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-3">
        <button className="flex items-center gap-2 px-4 py-3 rounded-lg bg-primary text-primary-foreground font-medium min-h-[44px]">
          <FileText className="w-5 h-5" />
          Download PDF Report
        </button>
        <button className="flex items-center gap-2 px-4 py-3 rounded-lg bg-secondary text-secondary-foreground font-medium min-h-[44px]">
          <Printer className="w-5 h-5" />
          Download ZPL Labels
        </button>
        <Link
          href={`/dashboard?sessionId=${session.id}`}
          className="flex items-center gap-2 px-4 py-3 rounded-lg border border-border text-foreground font-medium min-h-[44px]"
        >
          <LayoutDashboard className="w-5 h-5" />
          View Dashboard
        </Link>
        <Link
          href="/"
          className="flex items-center gap-2 px-4 py-3 rounded-lg text-muted-foreground hover:text-foreground min-h-[44px]"
        >
          <ArrowLeft className="w-5 h-5" />
          New Audit
        </Link>
      </div>

      {/* Label Preview */}
      <div className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Label Preview</h2>
          <p className="text-sm text-muted-foreground">
            Exact lines that will appear on the ZPL labels.
            {!session.hasDepartures && (
              <em className="ml-1">No DUE OUT/STAYOVER - departures file not uploaded.</em>
            )}
          </p>
        </div>
        <LabelPreview
          lines={previewLines}
          scopeLabel={session.scopeLabel}
          propertyName="Hotel Property"
        />
      </div>
    </div>
  )
}
