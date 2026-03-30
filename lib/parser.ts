import * as XLSX from "xlsx"
import type { VehicleRecord, RoomEntry, ScopeType, PreviewLine } from "./types"
import { ALWAYS_INCLUDE, SCOPE_LABELS } from "./types"

function clean(val: unknown): string {
  if (val === null || val === undefined) return ""
  const s = String(val).trim()
  if (["nan", "none", "n/a", "-"].includes(s.toLowerCase())) return ""
  return s
}

function normalizeRoom(val: unknown): number | null {
  const s = clean(val)
  const digits = s.replace(/[^\d]/g, "")
  if (!digits) return null
  const num = parseInt(digits, 10)
  return isNaN(num) ? null : num
}

const REQUIRED_HEADER_TOKENS = ["room", "plate", "state"]

function buildColMap(headerVals: string[]): Record<string, number> {
  const colMap: Record<string, number> = {}
  headerVals.forEach((v, i) => {
    if (!v) return
    const lower = v.toLowerCase()
    if (lower.includes("room") && colMap["room"] === undefined) colMap["room"] = i
    if (lower.includes("plate") && colMap["plate"] === undefined) colMap["plate"] = i
    if (lower.includes("state") && colMap["state"] === undefined) colMap["state"] = i
    if ((lower.includes("make") || lower.includes("model") || lower.includes("vehicle")) && colMap["makeModel"] === undefined) {
      colMap["makeModel"] = i
    }
    if (lower.includes("year") && colMap["year"] === undefined) colMap["year"] = i
    if (lower.includes("comment") && colMap["comment"] === undefined) colMap["comment"] = i
  })
  return colMap
}

export function parseInhouseExcel(data: ArrayBuffer): VehicleRecord[] {
  const workbook = XLSX.read(data, { type: "array" })
  const sheet = workbook.Sheets[workbook.SheetNames[0]]
  const rows: unknown[][] = XLSX.utils.sheet_to_json(sheet, { header: 1 })

  // Find header row
  let headerRowIdx = -1
  let colMap: Record<string, number> = {}

  for (let i = 0; i < Math.min(50, rows.length); i++) {
    const row = rows[i]
    if (!row) continue
    const vals = row.map((cell) => clean(cell).toLowerCase())
    const matched = REQUIRED_HEADER_TOKENS.filter((tok) =>
      vals.some((v) => v.includes(tok))
    )
    if (matched.length === REQUIRED_HEADER_TOKENS.length) {
      colMap = buildColMap(vals)
      headerRowIdx = i
      break
    }
  }

  if (headerRowIdx === -1) {
    throw new Error("Could not detect header row with required columns (Room, Plate, State)")
  }

  const records: VehicleRecord[] = []
  let blankStreak = 0

  for (let i = headerRowIdx + 1; i < rows.length; i++) {
    const row = rows[i]
    if (!row || row.every((cell) => !clean(cell))) {
      blankStreak++
      if (blankStreak >= 3) break
      continue
    }
    blankStreak = 0

    const get = (key: string): string => {
      const idx = colMap[key]
      if (idx === undefined || idx >= row.length) return ""
      return clean(row[idx])
    }

    const roomNum = normalizeRoom(get("room"))
    if (roomNum === null) continue

    records.push({
      roomNumber: roomNum,
      plate: get("plate"),
      state: get("state"),
      makeModel: get("makeModel"),
      year: get("year"),
      comment: get("comment"),
    })
  }

  return records
}

export function parseDeparturesExcel(data: ArrayBuffer): Set<number> {
  try {
    const workbook = XLSX.read(data, { type: "array" })
    const sheet = workbook.Sheets[workbook.SheetNames[0]]
    const rows: unknown[][] = XLSX.utils.sheet_to_json(sheet, { header: 1 })

    // Find header row with "room"
    let headerRowIdx = -1
    let roomColIdx = -1

    for (let i = 0; i < Math.min(50, rows.length); i++) {
      const row = rows[i]
      if (!row) continue
      const vals = row.map((cell) => clean(cell).toLowerCase())
      const roomIdx = vals.findIndex((v) => v.includes("room"))
      if (roomIdx !== -1) {
        headerRowIdx = i
        roomColIdx = roomIdx
        break
      }
    }

    if (headerRowIdx === -1 || roomColIdx === -1) {
      return new Set()
    }

    const dueOutRooms = new Set<number>()
    for (let i = headerRowIdx + 1; i < rows.length; i++) {
      const row = rows[i]
      if (!row || row.every((cell) => !clean(cell))) continue

      const roomVal = row[roomColIdx]
      const roomNum = normalizeRoom(roomVal)
      if (roomNum !== null) {
        dueOutRooms.add(roomNum)
      }
    }

    return dueOutRooms
  } catch {
    return new Set()
  }
}

function roomInScope(roomNumber: number, scope: ScopeType): boolean {
  if (ALWAYS_INCLUDE.includes(roomNumber) && (scope === "100_200" || scope === "300_400")) {
    return true
  }
  if (scope === "100_200") return roomNumber >= 100 && roomNumber <= 299
  if (scope === "300_400") return roomNumber >= 300 && roomNumber <= 499
  return true // full
}

export function buildRoomEntries(
  records: VehicleRecord[],
  scope: ScopeType,
  dueOutRooms: Set<number> | null
): RoomEntry[] {
  // Group by room
  const grouped = new Map<number, VehicleRecord[]>()
  for (const rec of records) {
    if (!grouped.has(rec.roomNumber)) {
      grouped.set(rec.roomNumber, [])
    }
    grouped.get(rec.roomNumber)!.push(rec)
  }

  const entries: RoomEntry[] = []
  for (const [roomNumber, vehicles] of grouped) {
    if (!roomInScope(roomNumber, scope)) continue

    let status: RoomEntry["status"] = null
    if (dueOutRooms !== null) {
      status = dueOutRooms.has(roomNumber) ? "DUE_OUT" : "STAYOVER"
    }

    entries.push({ roomNumber, vehicles, status })
  }

  entries.sort((a, b) => a.roomNumber - b.roomNumber)
  return entries
}

function hasVehicleInfo(v: VehicleRecord): boolean {
  return Boolean(v.plate || v.state || v.makeModel)
}

function entryHasVehicleInfo(entry: RoomEntry): boolean {
  return entry.vehicles.some(hasVehicleInfo)
}

function vehicleParts(v: VehicleRecord): string[] {
  const parts: string[] = []
  const idPart = [v.state, v.plate].filter(Boolean).join(" ")
  if (idPart) parts.push(idPart)
  
  let desc = v.makeModel
  if (desc && v.year) desc = `${desc} ${v.year}`
  else if (v.year && !desc) desc = v.year
  if (desc) parts.push(desc)
  
  return parts
}

export function buildPreviewLines(entries: RoomEntry[], hasDepartures: boolean): PreviewLine[] {
  const lines: PreviewLine[] = []

  for (const entry of entries) {
    if (hasDepartures) {
      const statusStr = entry.status || "STAYOVER"
      lines.push({ indent: 0, text: `ROOM ${entry.roomNumber} \u2014 ${statusStr}` })
      
      if (!entryHasVehicleInfo(entry)) {
        lines.push({ indent: 1, text: "Not In VM System" })
      } else {
        for (const v of entry.vehicles) {
          if (!hasVehicleInfo(v)) continue
          const parts = vehicleParts(v)
          lines.push({ indent: 1, text: parts.length ? parts.join(" \u2014 ") : "Unknown" })
        }
      }
    } else {
      if (!entryHasVehicleInfo(entry)) {
        lines.push({ indent: 0, text: `ROOM ${entry.roomNumber} \u2014 Not In VM System` })
      } else if (entry.vehicles.length === 1) {
        const v = entry.vehicles[0]
        const parts = [`ROOM ${entry.roomNumber}`, ...vehicleParts(v)]
        lines.push({ indent: 0, text: parts.join(" \u2014 ") })
      } else {
        lines.push({ indent: 0, text: `ROOM ${entry.roomNumber}` })
        for (const v of entry.vehicles) {
          if (!hasVehicleInfo(v)) continue
          const parts = vehicleParts(v)
          lines.push({ indent: 1, text: parts.length ? parts.join(" \u2014 ") : "Unknown" })
        }
      }
    }
  }

  return lines
}

export function computeCounts(entries: RoomEntry[]): {
  totalRooms: number
  roomsWithVehicles: number
  notInSystem: number
  dueOuts: number
  stayovers: number
} {
  const totalRooms = entries.length
  const roomsWithVehicles = entries.filter(entryHasVehicleInfo).length
  const notInSystem = totalRooms - roomsWithVehicles
  const dueOuts = entries.filter((e) => e.status === "DUE_OUT").length
  const stayovers = entries.filter((e) => e.status === "STAYOVER").length

  return { totalRooms, roomsWithVehicles, notInSystem, dueOuts, stayovers }
}

export function getScopeLabel(scope: ScopeType): string {
  return SCOPE_LABELS[scope] || scope
}
