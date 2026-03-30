import { NextRequest, NextResponse } from "next/server"
import { saveSession } from "@/lib/store"
import type { AuditSession, RoomEntry } from "@/lib/types"

interface GenerateRequest {
  scope: string
  scopeLabel: string
  entries: RoomEntry[]
  hasDepartures: boolean
  totalRooms: number
  roomsWithVehicles: number
  notInSystem: number
  dueOuts: number
  stayovers: number
}

export async function POST(request: NextRequest) {
  try {
    const data: GenerateRequest = await request.json()

    if (!data.entries || data.entries.length === 0) {
      return NextResponse.json(
        { error: "No entries provided" },
        { status: 400 }
      )
    }

    const sessionId = crypto.randomUUID()

    const session: AuditSession = {
      id: sessionId,
      scope: data.scope,
      scopeLabel: data.scopeLabel,
      totalRooms: data.totalRooms,
      roomsWithVehicles: data.roomsWithVehicles,
      notInSystem: data.notInSystem,
      dueOuts: data.dueOuts,
      stayovers: data.stayovers,
      hasDepartures: data.hasDepartures,
      createdAt: new Date().toISOString(),
      entries: data.entries,
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
