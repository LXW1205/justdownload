"use client"

import { useRef, useState } from "react"
import { cn } from "@/lib/utils"

type Props = {
  cookiesLoaded: boolean
  cookiesFilename?: string
  onUpload: (file: File) => Promise<void> | void
  onClear: () => Promise<void> | void
  busy?: boolean
}

export function OptionsPanel({ cookiesLoaded, cookiesFilename, onUpload, onClear, busy }: Props) {
  const [open, setOpen] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const handlePick = () => fileRef.current?.click()

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) await onUpload(f)
    if (fileRef.current) fileRef.current.value = ""
  }

  return (
    <div className="rounded-md border border-primary/40 bg-black/20">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={cn(
          "flex w-full items-center justify-between gap-3 px-3 py-2 text-left",
          "text-xs uppercase tracking-[0.2em] text-secondary hover:text-foreground transition-colors",
        )}
      >
        <span className="flex items-center gap-2">
          <span className="text-primary">{open ? "▾" : "▸"}</span>
          <span>$ [OPTIONS]</span>
        </span>
        <span
          className={cn(
            "font-mono text-[11px]",
            cookiesLoaded ? "text-emerald-300" : "text-secondary/60",
          )}
        >
          {cookiesLoaded ? "✓ cookies loaded" : "✗ no cookies"}
        </span>
      </button>

      {open && (
        <div className="border-t border-primary/30 px-3 py-3 space-y-3 text-sm">
          <div className="space-y-1">
            <p className="text-xs uppercase tracking-widest text-secondary">cookies.txt</p>
            <p className="text-xs text-secondary/70">
              <span className="text-primary">→</span> required for some age-restricted or members-only videos.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <input
              ref={fileRef}
              type="file"
              accept=".txt,text/plain"
              className="hidden"
              onChange={handleChange}
            />
            <button
              type="button"
              onClick={handlePick}
              disabled={busy}
              className={cn(
                "inline-flex items-center gap-2 rounded-md border border-primary/60 bg-transparent px-3 py-1.5",
                "text-xs uppercase tracking-widest text-foreground hover:bg-primary/10 disabled:opacity-50",
              )}
            >
              {"> [UPLOAD COOKIES]"}
            </button>
            {cookiesLoaded && (
              <button
                type="button"
                onClick={() => onClear()}
                disabled={busy}
                className={cn(
                  "inline-flex items-center gap-2 rounded-md border border-secondary/40 bg-transparent px-3 py-1.5",
                  "text-xs uppercase tracking-widest text-secondary hover:bg-secondary/10 disabled:opacity-50",
                )}
              >
                {"> [CLEAR]"}
              </button>
            )}
            {cookiesFilename && (
              <span className="text-xs text-secondary/80 truncate max-w-[14rem]">
                <span className="text-primary">→</span> {cookiesFilename}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
