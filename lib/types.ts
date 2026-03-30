export interface VehicleRecord {
  roomNumber: number
  plate: string
  state: string
  makeModel: string
  year: string
  comment: string
}

export interface RoomEntry {
  roomNumber: number
  vehicles: VehicleRecord[]
  status: "DUE_OUT" | "STAYOVER" | null
}

export interface AuditSession {
  id: string
  scope: string
  scopeLabel: string
  totalRooms: number
  roomsWithVehicles: number
  notInSystem: number
  dueOuts: number
  stayovers: number
  hasDepartures: boolean
  createdAt: string
  entries: RoomEntry[]
}

export interface PreviewLine {
  indent: number
  text: string
}

export type ScopeType = "100_200" | "300_400" | "full"

export const SCOPE_LABELS: Record<ScopeType, string> = {
  "100_200": "100/200s",
  "300_400": "300/400s",
  "full": "Full List",
}

export const ALWAYS_INCLUDE = [501, 502]
