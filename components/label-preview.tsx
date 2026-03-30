import type { PreviewLine } from "@/lib/types"

interface LabelPreviewProps {
  lines: PreviewLine[]
  scopeLabel: string
  propertyName?: string
}

export function LabelPreview({ lines, scopeLabel, propertyName }: LabelPreviewProps) {
  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      <div className="bg-muted p-4 border-b border-border">
        <div className="font-bold text-foreground">Parking Audit</div>
        {propertyName && <div className="text-sm text-muted-foreground">{propertyName}</div>}
        <div className="text-sm text-muted-foreground">Scope: {scopeLabel}</div>
      </div>
      <div className="p-4 max-h-96 overflow-y-auto font-mono text-sm">
        {lines.length === 0 ? (
          <div className="text-muted-foreground italic">No entries for this scope.</div>
        ) : (
          <div className="space-y-0.5">
            {lines.map((line, idx) => (
              <div
                key={idx}
                className={`${line.indent ? "pl-6 text-muted-foreground" : "font-semibold text-foreground"}`}
              >
                {line.text}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
