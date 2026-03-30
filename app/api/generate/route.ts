import { NextRequest, NextResponse } from "next/server"
import { parseInhouseExcel, parseDeparturesExcel, buildRoomEntries, computeCounts, getScopeLabel } from "@/lib/parser"
import { saveSession } from "@/lib/store"
import type { ScopeType, AuditSession } from "@/lib/types"

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData()
    
    const inhouseFile = formData.get("inhouseFile") as File | null
    const departuresFile = formData.get("departuresFile") as File | null
    const scope = (formData.get("scope") as ScopeType) || "100_200"
    
    if (!inhouseFile) {
      return NextResponse.json({ error: "In-house file is required" }, { status: 400 })
    }

    // Parse in-house file
    const inhouseBuffer = await inhouseFile.arrayBuffer()
    let vehicleRecords
    try {
      vehicleRecords = parseInhouseExcel(inhouseBuffer)
    } catch (e) {
      return NextResponse.json(
        { error: `Error parsing in-house file: ${e instanceof Error ? e.message : "Unknown error"}` },
        { status: 400 }
      )
    }

    // Parse departures file if provided
    let dueOutRooms: Set<number> | null = null
    if (departuresFile && departuresFile.size > 0) {
      const departuresBuffer = await departuresFile.arrayBuffer()
      dueOutRooms = parseDeparturesExcel(departuresBuffer)
    }

    // Build room entries
    const entries = buildRoomEntries(vehicleRecords, scope, dueOutRooms)

    if (entries.length === 0) {
      return NextResponse.json(
        { error: `No rooms found for scope '${getScopeLabel(scope)}'. Check your in-house file.` },
        { status: 400 }
      )
    }

    const counts = computeCounts(entries)
    const sessionId = crypto.randomUUID()

    const session: AuditSession = {
      id: sessionId,
      scope,
      scopeLabel: getScopeLabel(scope),
      totalRooms: counts.totalRooms,
      roomsWithVehicles: counts.roomsWithVehicles,
      notInSystem: counts.notInSystem,
      dueOuts: counts.dueOuts,
      stayovers: counts.stayovers,
      hasDepartures: dueOutRooms !== null,
      createdAt: new Date().toISOString(),
      entries,
    }

    saveSession(session)

    return NextResponse.json({ sessionId, success: true })
  } catch (error) {
    console.error("Generate error:", error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to generate audit" },
      { status: 500 }
    )
  }
}
