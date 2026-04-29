"use client"

import { useEffect, useRef } from "react"
import { cn } from "@/lib/utils"
import { asciiBar } from "@/lib/ascii"

export type LogLine = {
  id: number
  kind: "system" | "stdout" | "stderr" | "error" | "success" | "progress"
  text: string
}

type Props = {
  lines: LogLine[]
  percent: number | null
  active: boolean
  downloadHref?: string | null
  downloadFilename?: string | null
}

export function TerminalOutput({ lines, percent, active, downloadHref, downloadFilename }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [lines, percent])

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-[0.2em] text-secondary">$ stream.output</p>
        <span className={cn("text-[10px] uppercase tracking-widest", active ? "text-emerald-300" : "text-secondary/60")}>
          {active ? "● live" : "○ idle"}
        </span>
      </div>

      <div
        ref={scrollRef}
        className="terminal-scroll h-72 overflow-y-auto rounded-md border border-primary/40 bg-black/40 p-3 text-xs leading-relaxed"
      >
        {lines.length === 0 ? (
          <p className="text-secondary/60">
            <span className={cn(active ? "text-primary" : "text-secondary/60")}>$</span>{" "}
            <span className={cn(active ? "caret-blink" : "")}>awaiting command</span>
          </p>
        ) : (
          <ul className="space-y-0.5 font-mono">
            {lines.map((line) => (
              <li key={line.id} className={cn("term-line", colorFor(line.kind))}>
                <span className="select-none mr-2 text-secondary/60">{prefixFor(line.kind)}</span>
                <span className="whitespace-pre-wrap break-words">{line.text}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {percent !== null && (
        <div className="rounded-md border border-primary/40 bg-black/30 px-3 py-2 font-mono text-sm">
          <div className="flex items-center justify-between gap-3">
            <span className="text-secondary text-xs uppercase tracking-widest">progress</span>
            <span className="text-primary">{percent.toFixed(0)}%</span>
          </div>
          <pre className="mt-1 whitespace-pre text-foreground text-sm">{asciiBar(percent, 28)}</pre>
        </div>
      )}

      {downloadHref && downloadFilename && (
        <a
          href={downloadHref}
          download={downloadFilename}
          className={cn(
            "inline-flex items-center gap-2 rounded-md border border-primary bg-primary px-4 py-2",
            "text-xs font-bold uppercase tracking-[0.2em] text-primary-foreground",
            "shadow-[0_0_18px_-4px_rgba(255,92,141,0.8)] hover:bg-primary/90",
          )}
        >
          {"> [SAVE FILE] "} <span className="font-normal normal-case tracking-normal opacity-80">{downloadFilename}</span>
        </a>
      )}
    </div>
  )
}

function prefixFor(kind: LogLine["kind"]): string {
  switch (kind) {
    case "system":
      return "$"
    case "stdout":
      return "→"
    case "stderr":
      return "→"
    case "error":
      return "✗"
    case "success":
      return "✓"
    case "progress":
      return "→"
  }
}

function colorFor(kind: LogLine["kind"]): string {
  switch (kind) {
    case "system":
      return "text-secondary"
    case "stdout":
      return "text-foreground"
    case "stderr":
      return "text-secondary/80"
    case "error":
      return "text-rose-300"
    case "success":
      return "text-emerald-300"
    case "progress":
      return "text-primary"
  }
}
