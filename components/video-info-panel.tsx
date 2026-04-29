"use client"

import Image from "next/image"
import type { VideoInfo, FormatEntry } from "@/lib/types"
import { cn } from "@/lib/utils"
import { formatBytes } from "@/lib/ascii"

type Props = {
  info: VideoInfo
  selectedFormat: string
  onSelectFormat: (id: string) => void
  onDownload: () => void
  isDownloading: boolean
}

export function VideoInfoPanel({ info, selectedFormat, onSelectFormat, onDownload, isDownloading }: Props) {
  return (
    <div className="space-y-5">
      <div className="grid gap-5 md:grid-cols-[200px_1fr]">
        <div className="relative overflow-hidden rounded-md border border-primary glow-border">
          {info.thumbnail ? (
            <Image
              src={info.thumbnail || "/placeholder.svg"}
              alt={info.title}
              width={400}
              height={225}
              unoptimized
              className="h-auto w-full object-cover"
            />
          ) : (
            <div className="flex aspect-video w-full items-center justify-center bg-black/40 text-secondary text-xs">
              no thumbnail
            </div>
          )}
        </div>

        <div className="space-y-2">
          <p className="text-xs uppercase tracking-widest text-secondary">$ video.info</p>
          <h2 className="text-pretty text-lg font-bold leading-snug text-foreground">{info.title}</h2>
          <ul className="space-y-1 text-sm text-secondary">
            <li>
              <span className="text-primary">→</span> channel:{" "}
              <span className="text-foreground">{info.channel}</span>
            </li>
            <li>
              <span className="text-primary">→</span> duration:{" "}
              <span className="text-foreground">{info.durationString}</span>
            </li>
            <li>
              <span className="text-primary">→</span> uploaded:{" "}
              <span className="text-foreground">{info.uploadDate || "unknown"}</span>
            </li>
            <li>
              <span className="text-primary">→</span> formats:{" "}
              <span className="text-foreground">{info.formats.length}</span>
            </li>
          </ul>
        </div>
      </div>

      <FormatSelector
        formats={info.formats}
        value={selectedFormat}
        onChange={onSelectFormat}
        disabled={isDownloading}
      />

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onDownload}
          disabled={isDownloading}
          className={cn(
            "inline-flex items-center justify-center gap-2 rounded-md border border-primary bg-primary px-5 py-2.5",
            "text-sm font-bold uppercase tracking-[0.18em] text-primary-foreground",
            "transition-all hover:bg-primary/90 active:translate-y-px",
            "disabled:cursor-not-allowed disabled:opacity-50",
            "shadow-[0_0_22px_-4px_rgba(255,92,141,0.8)]",
            !isDownloading && "glow-border-pulse",
          )}
        >
          {isDownloading ? "> [DOWNLOADING...]" : "> [DOWNLOAD]"}
        </button>
        <a
          href={info.webpageUrl}
          target="_blank"
          rel="noreferrer"
          className="text-xs uppercase tracking-widest text-secondary hover:text-foreground"
        >
          {"→ open on youtube"}
        </a>
      </div>
    </div>
  )
}

function FormatSelector({
  formats,
  value,
  onChange,
  disabled,
}: {
  formats: FormatEntry[]
  value: string
  onChange: (id: string) => void
  disabled?: boolean
}) {
  return (
    <div className="space-y-2">
      <label htmlFor="fmt" className="block text-xs uppercase tracking-[0.2em] text-secondary">
        $ select.format
      </label>
      <div className="relative rounded-md border border-primary/60 bg-black/30">
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-primary">{">"}</span>
        <select
          id="fmt"
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          className={cn(
            "w-full appearance-none bg-transparent py-2 pl-7 pr-9 font-mono text-sm text-foreground outline-none",
            "disabled:cursor-not-allowed disabled:opacity-60",
          )}
        >
          <option value="best" className="bg-[var(--terminal-bg)] text-foreground">
            ★ Best Quality (Auto)
          </option>
          {formats.map((f) => (
            <option key={f.format_id} value={f.format_id} className="bg-[var(--terminal-bg)] text-foreground">
              {f.label}
              {f.filesize ? ` ~${formatBytes(f.filesize)}` : ""}
            </option>
          ))}
        </select>
        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-primary">▾</span>
      </div>
    </div>
  )
}
