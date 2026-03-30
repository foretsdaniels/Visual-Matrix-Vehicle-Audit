"use client"

import { useState, useRef, type ChangeEvent, type FormEvent } from "react"
import { useRouter } from "next/navigation"
import { FileSpreadsheet, Calendar, Loader2, Upload } from "lucide-react"
import type { ScopeType } from "@/lib/types"
import {
  parseInhouseExcel,
  parseDeparturesExcel,
  buildRoomEntries,
  computeCounts,
  getScopeLabel,
} from "@/lib/client-parser"

const SCOPES: { value: ScopeType; label: string; description: string }[] = [
  { value: "100_200", label: "100/200s", description: "Rooms 100-299 + 501, 502" },
  { value: "300_400", label: "300/400s", description: "Rooms 300-499 + 501, 502" },
  { value: "full", label: "Full List", description: "All rooms in the file" },
]

export function UploadForm() {
  const router = useRouter()
  const [inhouseFile, setInhouseFile] = useState<File | null>(null)
  const [departuresFile, setDeparturesFile] = useState<File | null>(null)
  const [scope, setScope] = useState<ScopeType>("100_200")
  const [allowMultiLabel, setAllowMultiLabel] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const inhouseRef = useRef<HTMLInputElement>(null)
  const departuresRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (
    e: ChangeEvent<HTMLInputElement>,
    setter: (file: File | null) => void
  ) => {
    const file = e.target.files?.[0] || null
    setter(file)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!inhouseFile) {
      setError("Please select an in-house guests file")
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      // Parse files on the client side
      const inhouseBuffer = await inhouseFile.arrayBuffer()
      let vehicleRecords
      try {
        vehicleRecords = parseInhouseExcel(inhouseBuffer)
      } catch (parseError) {
        throw new Error(
          `Error parsing in-house file: ${parseError instanceof Error ? parseError.message : "Unknown error"}`
        )
      }

      // Parse departures if provided
      let dueOutRooms: Set<number> | null = null
      if (departuresFile && departuresFile.size > 0) {
        const departuresBuffer = await departuresFile.arrayBuffer()
        dueOutRooms = parseDeparturesExcel(departuresBuffer)
      }

      // Build entries
      const entries = buildRoomEntries(vehicleRecords, scope, dueOutRooms)

      if (entries.length === 0) {
        throw new Error(
          `No rooms found for scope '${getScopeLabel(scope)}'. Check your in-house file.`
        )
      }

      const counts = computeCounts(entries)

      // Send parsed data to API
      const response = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scope,
          scopeLabel: getScopeLabel(scope),
          entries,
          hasDepartures: dueOutRooms !== null,
          ...counts,
        }),
      })

      const result = await response.json()

      if (!response.ok) {
        throw new Error(result.error || "Failed to generate audit")
      }

      router.push(`/preview/${result.sessionId}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="p-4 rounded-lg bg-destructive/10 text-destructive border border-destructive/20">
          {error}
        </div>
      )}

      {/* In-House File */}
      <div className="space-y-3">
        <div className="flex items-baseline gap-2">
          <h2 className="font-semibold text-foreground">1. In-House Guests File</h2>
          <span className="text-destructive text-sm">*</span>
        </div>
        <p className="text-sm text-muted-foreground">
          Visual Matrix &quot;Parking Lot List&quot; export (.xlsx or .xls)
        </p>
        <div
          className={`relative border-2 border-dashed rounded-xl p-6 transition-colors cursor-pointer ${
            inhouseFile
              ? "border-primary bg-primary/5"
              : "border-border hover:border-muted-foreground"
          }`}
          onClick={() => inhouseRef.current?.click()}
        >
          <input
            ref={inhouseRef}
            type="file"
            accept=".xlsx,.xls"
            onChange={(e) => handleFileChange(e, setInhouseFile)}
            className="sr-only"
          />
          <div className="flex flex-col items-center gap-3 text-center">
            <div
              className={`w-12 h-12 rounded-full flex items-center justify-center ${
                inhouseFile ? "bg-primary" : "bg-muted"
              }`}
            >
              <FileSpreadsheet
                className={`w-6 h-6 ${
                  inhouseFile ? "text-primary-foreground" : "text-muted-foreground"
                }`}
              />
            </div>
            <div>
              {inhouseFile ? (
                <p className="font-medium text-foreground">{inhouseFile.name}</p>
              ) : (
                <p className="text-muted-foreground">
                  Tap to choose file or drag and drop
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Departures File */}
      <div className="space-y-3">
        <div className="flex items-baseline gap-2">
          <h2 className="font-semibold text-foreground">2. Departures File</h2>
          <span className="text-muted-foreground text-sm">(Optional)</span>
        </div>
        <p className="text-sm text-muted-foreground">
          Upload to tag rooms as DUE OUT vs STAYOVER (.xlsx)
        </p>
        <div
          className={`relative border-2 border-dashed rounded-xl p-6 transition-colors cursor-pointer ${
            departuresFile
              ? "border-primary bg-primary/5"
              : "border-border hover:border-muted-foreground"
          }`}
          onClick={() => departuresRef.current?.click()}
        >
          <input
            ref={departuresRef}
            type="file"
            accept=".xlsx"
            onChange={(e) => handleFileChange(e, setDeparturesFile)}
            className="sr-only"
          />
          <div className="flex flex-col items-center gap-3 text-center">
            <div
              className={`w-12 h-12 rounded-full flex items-center justify-center ${
                departuresFile ? "bg-primary" : "bg-muted"
              }`}
            >
              <Calendar
                className={`w-6 h-6 ${
                  departuresFile ? "text-primary-foreground" : "text-muted-foreground"
                }`}
              />
            </div>
            <div>
              {departuresFile ? (
                <p className="font-medium text-foreground">{departuresFile.name}</p>
              ) : (
                <p className="text-muted-foreground">
                  Tap to choose departures file (optional)
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Scope Selection */}
      <div className="space-y-3">
        <h2 className="font-semibold text-foreground">3. Scope</h2>
        <p className="text-sm text-muted-foreground">
          Select which rooms to include in this audit
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {SCOPES.map((s) => (
            <label
              key={s.value}
              className={`relative flex flex-col p-4 rounded-xl border-2 cursor-pointer transition-colors min-h-[44px] ${
                scope === s.value
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-muted-foreground"
              }`}
            >
              <input
                type="radio"
                name="scope"
                value={s.value}
                checked={scope === s.value}
                onChange={(e) => setScope(e.target.value as ScopeType)}
                className="sr-only"
              />
              <span className="font-semibold text-foreground">{s.label}</span>
              <span className="text-sm text-muted-foreground">{s.description}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Label Options */}
      <div className="space-y-3">
        <h2 className="font-semibold text-foreground">4. Label Options</h2>
        <label className="flex items-center gap-3 cursor-pointer min-h-[44px]">
          <div className="relative">
            <input
              type="checkbox"
              checked={allowMultiLabel}
              onChange={(e) => setAllowMultiLabel(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-muted rounded-full peer peer-checked:bg-primary transition-colors" />
            <div className="absolute left-0.5 top-0.5 w-5 h-5 bg-background rounded-full shadow transition-transform peer-checked:translate-x-5" />
          </div>
          <div className="flex-1">
            <span className="text-foreground">Allow multi-label split</span>
            <span className="block text-sm text-muted-foreground">
              Recommended - splits long lists across multiple labels
            </span>
          </div>
        </label>
      </div>

      {/* Submit Button */}
      <button
        type="submit"
        disabled={isSubmitting || !inhouseFile}
        className="w-full flex items-center justify-center gap-2 px-6 py-4 rounded-xl bg-primary text-primary-foreground font-semibold text-lg disabled:opacity-50 disabled:cursor-not-allowed transition-opacity min-h-[56px]"
      >
        {isSubmitting ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            Generating...
          </>
        ) : (
          <>
            <Upload className="w-5 h-5" />
            Generate Audit
          </>
        )}
      </button>
    </form>
  )
}
