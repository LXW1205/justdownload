"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { TerminalWindow } from "@/components/terminal-window"
import { UrlInputPanel } from "@/components/url-input-panel"
import { OptionsPanel } from "@/components/options-panel"
import { VideoInfoPanel } from "@/components/video-info-panel"
import { TerminalOutput, type LogLine } from "@/components/terminal-output"
import type { VideoInfo } from "@/lib/types"

// Single-container app. All endpoints are same-origin Next.js routes.
export default function HomePage() {
  const [cookiesLoaded, setCookiesLoaded] = useState(false)

  const [url, setUrl] = useState("")
  const [info, setInfo] = useState<VideoInfo | null>(null)
  const [selectedFormat, setSelectedFormat] = useState<string>("best")
  const [fetching, setFetching] = useState(false)

  const [lines, setLines] = useState<LogLine[]>([])
  const [percent, setPercent] = useState<number | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [downloadHref, setDownloadHref] = useState<string | null>(null)
  const [downloadFilename, setDownloadFilename] = useState<string | null>(null)

  const lineId = useRef(0)
  const abortRef = useRef<AbortController | null>(null)

  const pushLine = useCallback((kind: LogLine["kind"], text: string) => {
    lineId.current += 1
    setLines((prev) => [...prev, { id: lineId.current, kind, text }])
  }, [])

  // Probe whether cookies.txt was mounted in via docker-compose.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch("/api/status")
        const data = await res.json()
        if (cancelled) return
        setCookiesLoaded(Boolean(data.cookiesLoaded))
        pushLine("system", "container ready")
        if (data.cookiesLoaded) {
          pushLine("success", "auto-detected cookies.txt at /app/cookies.txt")
        } else {
          pushLine("system", "no cookies.txt mounted (optional)")
        }
      } catch (e: any) {
        pushLine("error", `status check failed: ${e?.message ?? e}`)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [pushLine])

  const handleFetch = useCallback(
    async (nextUrl: string) => {
      setFetching(true)
      setUrl(nextUrl)
      setInfo(null)
      setSelectedFormat("best")
      setDownloadHref(null)
      setDownloadFilename(null)
      setPercent(null)
      pushLine("system", `fetching info for: ${nextUrl}`)
      try {
        const res = await fetch("/api/fetch-info", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: nextUrl }),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.error ?? "fetch failed")
        setInfo(data.info as VideoInfo)
        pushLine("success", `loaded "${data.info.title}" (${data.info.formats.length} formats)`)
        if (data.cookiesUsed) pushLine("system", "using mounted cookies.txt for this request")
      } catch (e: any) {
        pushLine("error", `ERROR: ${e?.message ?? e}`)
      } finally {
        setFetching(false)
      }
    },
    [pushLine],
  )

  const handleDownload = useCallback(async () => {
    if (!info || !url) return
    setDownloading(true)
    setPercent(0)
    setDownloadHref(null)
    setDownloadFilename(null)
    pushLine("system", `starting download: format=${selectedFormat === "best" ? "auto" : selectedFormat}`)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const res = await fetch("/api/download", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ url, formatId: selectedFormat }),
        signal: controller.signal,
      })
      if (!res.ok || !res.body) {
        const txt = await res.text().catch(() => "")
        throw new Error(txt || `download failed: ${res.status}`)
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let idx
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const rawEvent = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          handleSseEvent(rawEvent)
        }
      }
    } catch (e: any) {
      if (e?.name === "AbortError") {
        pushLine("system", "download cancelled")
      } else {
        pushLine("error", `ERROR: ${e?.message ?? e}`)
      }
    } finally {
      setDownloading(false)
      abortRef.current = null
    }

    function handleSseEvent(raw: string) {
      const evLines = raw.split("\n")
      let event = "message"
      let data = ""
      for (const l of evLines) {
        if (l.startsWith("event:")) event = l.slice(6).trim()
        else if (l.startsWith("data:")) data += l.slice(5).trim()
      }
      let parsed: any = null
      try {
        parsed = data ? JSON.parse(data) : null
      } catch {
        parsed = data
      }

      switch (event) {
        case "status":
          pushLine("system", parsed?.line ?? String(parsed))
          break
        case "stdout":
          pushLine("stdout", parsed?.line ?? String(parsed))
          break
        case "stderr":
          pushLine("stderr", parsed?.line ?? String(parsed))
          break
        case "progress":
          if (typeof parsed?.percent === "number") setPercent(parsed.percent)
          if (parsed?.line) pushLine("progress", parsed.line)
          break
        case "file":
          if (parsed?.filename) {
            setDownloadFilename(parsed.filename)
            setDownloadHref(`/api/file/${encodeURIComponent(parsed.filename)}`)
          }
          break
        case "error":
          pushLine("error", `ERROR: ${parsed?.message ?? parsed}`)
          break
        case "done":
          if (parsed?.ok) {
            setPercent(100)
            pushLine("success", "download complete — saved to ./downloads on host")
          }
          break
      }
    }
  }, [info, url, selectedFormat, pushLine])

  return (
    <main className="relative mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-6 px-4 py-8 sm:py-12">
      <header className="flex flex-col gap-2">
        <div className="flex items-center gap-3">
          <span
            aria-hidden
            className="inline-block h-2 w-2 rounded-full bg-primary shadow-[0_0_10px_2px_rgba(255,92,141,0.7)]"
          />
          <h1 className="text-balance text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            just<span className="text-primary">download</span>
          </h1>
        </div>
        <p className="text-sm text-secondary">
          <span className="text-primary">$</span> a terminal-styled YouTube downloader, powered by{" "}
          <span className="text-foreground">yt-dlp</span>.
        </p>
      </header>

      <TerminalWindow title="justdownload" subtitle="input" glow>
        <UrlInputPanel onFetch={handleFetch} isLoading={fetching} disabled={downloading} />
        <div className="mt-4">
          <OptionsPanel cookiesLoaded={cookiesLoaded} />
        </div>
      </TerminalWindow>

      {info && (
        <TerminalWindow title="justdownload" subtitle={`video — ${info.id}`}>
          <VideoInfoPanel
            info={info}
            selectedFormat={selectedFormat}
            onSelectFormat={setSelectedFormat}
            onDownload={handleDownload}
            isDownloading={downloading}
          />
        </TerminalWindow>
      )}

      <TerminalWindow title="justdownload" subtitle="stdout">
        <TerminalOutput
          lines={lines}
          percent={percent}
          active={downloading || fetching}
          downloadHref={downloadHref}
          downloadFilename={downloadFilename}
        />
      </TerminalWindow>

      <footer className="pt-2 text-center text-[11px] uppercase tracking-[0.3em] text-secondary/60">
        <span className="text-primary">$</span> exit 0
      </footer>
    </main>
  )
}
