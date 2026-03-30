"use client"

import { useState, useMemo } from "react"
import type { AuditSession, RoomEntry, VehicleRecord } from "@/lib/types"
import { Search, X } from "lucide-react"

interface DashboardTableProps {
  session: AuditSession
}

interface FlattenedRow {
  roomNumber: number
  status: string | null
  plate: string
  state: string
  makeModel: string
  year: string
  comment: string
  hasVehicleInfo: boolean
}

function flattenEntries(entries: RoomEntry[]): FlattenedRow[] {
  const rows: FlattenedRow[] = []
  for (const entry of entries) {
    if (entry.vehicles.length === 0) {
      rows.push({
        roomNumber: entry.roomNumber,
        status: entry.status,
        plate: "",
        state: "",
        makeModel: "",
        year: "",
        comment: "",
        hasVehicleInfo: false,
      })
    } else {
      for (const v of entry.vehicles) {
        const hasInfo = Boolean(v.plate || v.state || v.makeModel)
        rows.push({
          roomNumber: entry.roomNumber,
          status: entry.status,
          plate: v.plate,
          state: v.state,
          makeModel: v.makeModel,
          year: v.year,
          comment: v.comment,
          hasVehicleInfo: hasInfo,
        })
      }
    }
  }
  return rows
}

export function DashboardTable({ session }: DashboardTableProps) {
  const [search, setSearch] = useState("")
  const [filterNotInSys, setFilterNotInSys] = useState(false)
  const [filterDueOut, setFilterDueOut] = useState(false)
  const [filterStayover, setFilterStayover] = useState(false)

  const allRows = useMemo(() => flattenEntries(session.entries), [session.entries])

  const filteredRows = useMemo(() => {
    return allRows.filter((row) => {
      // Search filter
      if (search) {
        const searchLower = search.toLowerCase()
        const matchesSearch =
          String(row.roomNumber).includes(search) ||
          row.plate.toLowerCase().includes(searchLower) ||
          row.state.toLowerCase().includes(searchLower) ||
          row.makeModel.toLowerCase().includes(searchLower)
        if (!matchesSearch) return false
      }

      // Not in system filter
      if (filterNotInSys && row.hasVehicleInfo) return false

      // Status filters
      if (filterDueOut && row.status !== "DUE_OUT") return false
      if (filterStayover && row.status !== "STAYOVER") return false

      return true
    })
  }, [allRows, search, filterNotInSys, filterDueOut, filterStayover])

  const clearFilters = () => {
    setSearch("")
    setFilterNotInSys(false)
    setFilterDueOut(false)
    setFilterStayover(false)
  }

  const hasActiveFilters = search || filterNotInSys || filterDueOut || filterStayover

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search room or plate..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-3 rounded-lg border border-border bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary min-h-[44px]"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <label className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border cursor-pointer min-h-[44px]">
            <input
              type="checkbox"
              checked={filterNotInSys}
              onChange={(e) => setFilterNotInSys(e.target.checked)}
              className="w-4 h-4 rounded border-border"
            />
            <span className="text-sm text-foreground">Not In VM</span>
          </label>
          {session.hasDepartures && (
            <>
              <label className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border cursor-pointer min-h-[44px]">
                <input
                  type="checkbox"
                  checked={filterDueOut}
                  onChange={(e) => setFilterDueOut(e.target.checked)}
                  className="w-4 h-4 rounded border-border"
                />
                <span className="text-sm text-foreground">Due Outs</span>
              </label>
              <label className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border cursor-pointer min-h-[44px]">
                <input
                  type="checkbox"
                  checked={filterStayover}
                  onChange={(e) => setFilterStayover(e.target.checked)}
                  className="w-4 h-4 rounded border-border"
                />
                <span className="text-sm text-foreground">Stayovers</span>
              </label>
            </>
          )}
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground min-h-[44px]"
            >
              <X className="w-4 h-4" />
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Row count */}
      <p className="text-sm text-muted-foreground">
        Showing {filteredRows.length} of {allRows.length} records
      </p>

      {/* Table */}
      <div className="border border-border rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-foreground">Room</th>
                {session.hasDepartures && (
                  <th className="px-4 py-3 text-left font-semibold text-foreground">Status</th>
                )}
                <th className="px-4 py-3 text-left font-semibold text-foreground">State</th>
                <th className="px-4 py-3 text-left font-semibold text-foreground">Plate</th>
                <th className="px-4 py-3 text-left font-semibold text-foreground hidden sm:table-cell">Make/Model</th>
                <th className="px-4 py-3 text-left font-semibold text-foreground hidden md:table-cell">Year</th>
                <th className="px-4 py-3 text-left font-semibold text-foreground">Vehicle Data</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredRows.length === 0 ? (
                <tr>
                  <td colSpan={session.hasDepartures ? 7 : 6} className="px-4 py-8 text-center text-muted-foreground">
                    No records found
                  </td>
                </tr>
              ) : (
                filteredRows.map((row, idx) => (
                  <tr key={idx} className="hover:bg-muted/50">
                    <td className="px-4 py-3 font-medium text-foreground">{row.roomNumber}</td>
                    {session.hasDepartures && (
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${
                            row.status === "DUE_OUT"
                              ? "bg-destructive/10 text-destructive"
                              : "bg-[hsl(var(--info))]/10 text-[hsl(var(--info))]"
                          }`}
                        >
                          {row.status === "DUE_OUT" ? "Due Out" : "Stayover"}
                        </span>
                      </td>
                    )}
                    <td className="px-4 py-3 text-muted-foreground">{row.state || "-"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{row.plate || "-"}</td>
                    <td className="px-4 py-3 text-muted-foreground hidden sm:table-cell">{row.makeModel || "-"}</td>
                    <td className="px-4 py-3 text-muted-foreground hidden md:table-cell">{row.year || "-"}</td>
                    <td className="px-4 py-3">
                      {row.hasVehicleInfo ? (
                        <span className="inline-flex px-2 py-1 rounded-full text-xs font-medium bg-[hsl(var(--success))]/10 text-[hsl(var(--success))]">
                          Yes
                        </span>
                      ) : (
                        <span className="inline-flex px-2 py-1 rounded-full text-xs font-medium bg-[hsl(var(--warning))]/10 text-[hsl(var(--warning))]">
                          No
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
