import { cn } from "@/lib/utils"

type Props = {
  cookiesLoaded: boolean
}

// Read-only status row. cookies.txt is mounted into the container at runtime
// (./cookies.txt → /app/cookies.txt), so there is nothing to upload from here.
export function OptionsPanel({ cookiesLoaded }: Props) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-primary/40 bg-black/20 px-3 py-2">
      <span className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-secondary">
        <span className="text-primary">$</span>
        <span>cookies.txt</span>
      </span>
      <span
        className={cn(
          "font-mono text-[11px]",
          cookiesLoaded ? "text-emerald-300" : "text-secondary/60",
        )}
      >
        {cookiesLoaded
          ? "✓ detected — /app/cookies.txt"
          : "✗ not mounted — drop cookies.txt next to docker-compose.yml"}
      </span>
    </div>
  )
}
