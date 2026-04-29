import type React from "react"
import { cn } from "@/lib/utils"

type Props = {
  title?: string
  subtitle?: string
  className?: string
  children: React.ReactNode
  glow?: boolean
}

export function TerminalWindow({ title = "justdownload", subtitle, className, children, glow = false }: Props) {
  return (
    <section
      className={cn(
        "relative rounded-md border border-primary/60 bg-[var(--terminal-bg)] overflow-hidden scanlines",
        glow && "glow-border",
        className,
      )}
    >
      {/* title bar */}
      <header className="flex items-center justify-between gap-3 border-b border-primary/40 bg-black/20 px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="block h-2.5 w-2.5 rounded-full bg-[#ff5c8d]" aria-hidden />
          <span className="block h-2.5 w-2.5 rounded-full bg-[#ffc0d3]" aria-hidden />
          <span className="block h-2.5 w-2.5 rounded-full bg-[#fdeff4]/60" aria-hidden />
        </div>
        <div className="flex-1 text-center text-xs uppercase tracking-[0.2em] text-secondary truncate">
          {title}
          {subtitle ? <span className="text-foreground/50"> — {subtitle}</span> : null}
        </div>
        <div className="text-[10px] uppercase tracking-widest text-secondary/70">v1.0</div>
      </header>
      <div className="relative p-4 sm:p-5">{children}</div>
    </section>
  )
}
