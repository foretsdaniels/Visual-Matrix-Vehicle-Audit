interface StatTileProps {
  label: string
  value: number
  variant?: "default" | "success" | "warning" | "destructive" | "info"
}

const variants = {
  default: "bg-card border-border",
  success: "bg-[hsl(var(--success))]/10 border-[hsl(var(--success))]/20",
  warning: "bg-[hsl(var(--warning))]/10 border-[hsl(var(--warning))]/20",
  destructive: "bg-destructive/10 border-destructive/20",
  info: "bg-[hsl(var(--info))]/10 border-[hsl(var(--info))]/20",
}

const textVariants = {
  default: "text-foreground",
  success: "text-[hsl(var(--success))]",
  warning: "text-[hsl(var(--warning))]",
  destructive: "text-destructive",
  info: "text-[hsl(var(--info))]",
}

export function StatTile({ label, value, variant = "default" }: StatTileProps) {
  return (
    <div className={`p-4 rounded-xl border ${variants[variant]}`}>
      <div className={`text-2xl font-bold ${textVariants[variant]}`}>{value}</div>
      <div className="text-sm text-muted-foreground">{label}</div>
    </div>
  )
}
