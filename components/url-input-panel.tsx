"use client"

import type React from "react"
import { useState } from "react"
import { cn } from "@/lib/utils"

type Props = {
  onFetch: (url: string) => void
  isLoading: boolean
  disabled?: boolean
}

export function UrlInputPanel({ onFetch, isLoading, disabled }: Props) {
  const [url, setUrl] = useState("")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = url.trim()
    if (!trimmed) return
    onFetch(trimmed)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <label htmlFor="yt-url" className="block text-xs uppercase tracking-[0.2em] text-secondary">
        $ input.url
      </label>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-stretch">
        <div className="flex flex-1 items-center gap-2 rounded-md border border-primary/50 bg-black/30 px-3 py-2 focus-within:glow-border">
          <span className="select-none text-primary">{">"}</span>
          <input
            id="yt-url"
            type="url"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            placeholder="paste youtube url here_"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={disabled}
            className={cn(
              "w-full bg-transparent font-mono text-sm text-foreground outline-none",
              "placeholder:text-secondary/50",
            )}
          />
        </div>
        <button
          type="submit"
          disabled={isLoading || disabled || !url.trim()}
          className={cn(
            "inline-flex items-center justify-center gap-2 rounded-md border border-primary bg-primary px-4 py-2",
            "text-sm font-bold uppercase tracking-[0.18em] text-primary-foreground",
            "transition-all hover:bg-primary/90 active:translate-y-px",
            "disabled:cursor-not-allowed disabled:opacity-50",
            "shadow-[0_0_18px_-4px_rgba(255,92,141,0.7)]",
          )}
        >
          {isLoading ? (
            <>
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-primary-foreground" />
              {"> [FETCHING...]"}
            </>
          ) : (
            <span>{"> [FETCH INFO]"}</span>
          )}
        </button>
      </div>
      <p className="text-xs text-secondary/70">
        <span className="text-primary">→</span> tip: press{" "}
        <kbd className="rounded border border-primary/40 bg-black/30 px-1 text-[10px] text-secondary">enter</kbd> to
        run.
      </p>
    </form>
  )
}
